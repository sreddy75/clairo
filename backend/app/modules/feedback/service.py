"""Business logic for the feedback module."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from uuid import UUID

import anthropic
from fastapi import UploadFile
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MinioSettings, get_settings
from app.modules.feedback.enums import (
    ContentType,
    MessageRole,
    SubmissionStatus,
    SubmissionType,
)
from app.modules.feedback.exceptions import (
    BriefNotReadyError,
    ConversationCompleteError,
    SubmissionNotFoundError,
)
from app.modules.feedback.models import (
    FeedbackComment,
    FeedbackMessage,
    FeedbackSubmission,
)
from app.modules.feedback.prompts import (
    BRIEF_GENERATION_PROMPT,
    get_system_prompt,
    render_brief_markdown,
)
from app.modules.feedback.repository import FeedbackRepository
from app.modules.feedback.transcription import TranscriptionService

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FeedbackRepository(session)

        settings = get_settings()
        api_key = settings.anthropic.api_key.get_secret_value()
        self.claude = anthropic.Anthropic(api_key=api_key)
        self.claude_model = settings.anthropic.model

        minio_settings = MinioSettings()
        self.minio = Minio(
            minio_settings.endpoint,
            access_key=minio_settings.access_key,
            secret_key=minio_settings.secret_key.get_secret_value(),
            secure=minio_settings.use_ssl,
        )
        self.bucket = minio_settings.bucket

    async def create_submission(
        self,
        tenant_id: UUID,
        submitter_id: UUID,
        submitter_name: str,
        submission_type: str,
        audio_file: UploadFile,
    ) -> FeedbackSubmission:
        """Create a new feedback submission from a voice memo."""
        transcription_service = TranscriptionService()
        transcript, duration = await transcription_service.transcribe(audio_file)

        submission = FeedbackSubmission(
            tenant_id=tenant_id,
            submitter_id=submitter_id,
            submitter_name=submitter_name,
            type=submission_type,
            status=SubmissionStatus.DRAFT.value,
        )
        submission = await self.repo.create_submission(submission)

        ext = Path(audio_file.filename or "audio.webm").suffix.lower()
        object_key = f"feedback/{tenant_id}/{submission.id}/audio{ext}"

        audio_content = await audio_file.read()
        self.minio.put_object(
            self.bucket,
            object_key,
            io.BytesIO(audio_content),
            len(audio_content),
            content_type=audio_file.content_type or "audio/webm",
        )

        submission.audio_file_key = object_key
        submission.audio_duration_seconds = duration
        submission.transcript = transcript
        submission = await self.repo.update_submission(submission)

        system_prompt = get_system_prompt(submission_type)
        await self.repo.create_message(
            FeedbackMessage(
                submission_id=submission.id,
                role=MessageRole.SYSTEM.value,
                content=system_prompt,
                content_type=ContentType.TEXT.value,
            )
        )

        await self.repo.create_message(
            FeedbackMessage(
                submission_id=submission.id,
                role=MessageRole.USER.value,
                content=transcript,
                content_type=ContentType.TRANSCRIPT.value,
            )
        )

        assistant_response = await self._call_claude(submission.id)
        await self.repo.create_message(
            FeedbackMessage(
                submission_id=submission.id,
                role=MessageRole.ASSISTANT.value,
                content=assistant_response,
                content_type=ContentType.TEXT.value,
            )
        )

        return submission

    async def send_message(
        self,
        submission_id: UUID,
        tenant_id: UUID,
        content: str,
        content_type: str = ContentType.TEXT.value,
    ) -> dict:
        """Send a user message and get AI response."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)
        if submission.conversation_complete:
            raise ConversationCompleteError(submission_id)

        user_msg = await self.repo.create_message(
            FeedbackMessage(
                submission_id=submission_id,
                role=MessageRole.USER.value,
                content=content,
                content_type=content_type,
            )
        )

        assistant_text = await self._call_claude(submission_id)

        brief_ready = False
        brief_data = None
        brief_markdown = None

        if self._looks_like_brief_ready(assistant_text):
            brief_ready, brief_data, brief_markdown = await self._try_generate_brief(
                submission_id, submission.type
            )
            if brief_ready:
                assistant_text = (
                    "I have enough detail to write up the brief. "
                    "Here's what I've put together — please review it."
                )

        assistant_msg = await self.repo.create_message(
            FeedbackMessage(
                submission_id=submission_id,
                role=MessageRole.ASSISTANT.value,
                content=assistant_text,
                content_type=ContentType.TEXT.value,
            )
        )

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "brief_ready": brief_ready,
            "brief_data": brief_data,
            "brief_markdown": brief_markdown,
        }

    async def send_voice_message(
        self,
        submission_id: UUID,
        tenant_id: UUID,
        audio_file: UploadFile,
    ) -> dict:
        """Transcribe a voice follow-up and process as a message."""
        transcription_service = TranscriptionService()
        transcript, _ = await transcription_service.transcribe(audio_file)

        result = await self.send_message(
            submission_id, tenant_id, transcript, ContentType.TRANSCRIPT.value
        )
        result["transcript"] = transcript
        return result

    async def confirm_brief(
        self,
        submission_id: UUID,
        tenant_id: UUID,
        revisions: str | None = None,
    ) -> FeedbackSubmission:
        """Confirm the generated brief and move submission to 'new' status."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)

        if revisions:
            await self.repo.create_message(
                FeedbackMessage(
                    submission_id=submission_id,
                    role=MessageRole.USER.value,
                    content=f"Please revise the brief with these changes: {revisions}",
                    content_type=ContentType.TEXT.value,
                )
            )
            _, brief_data, brief_markdown = await self._try_generate_brief(
                submission_id, submission.type
            )
            if brief_data:
                assistant_text = "I've revised the brief based on your feedback."
            else:
                assistant_text = "I had trouble regenerating the brief. Please try again."
                brief_data = submission.brief_data
                brief_markdown = submission.brief_markdown

            await self.repo.create_message(
                FeedbackMessage(
                    submission_id=submission_id,
                    role=MessageRole.ASSISTANT.value,
                    content=assistant_text,
                    content_type=ContentType.TEXT.value,
                )
            )
        else:
            brief_data = submission.brief_data
            brief_markdown = submission.brief_markdown

        if not brief_data:
            _, brief_data, brief_markdown = await self._try_generate_brief(
                submission_id, submission.type
            )

        if not brief_data:
            raise BriefNotReadyError(submission_id)

        submission.brief_data = brief_data
        submission.brief_markdown = brief_markdown
        submission.title = brief_data.get("title", "Untitled")
        if submission.type == SubmissionType.BUG_ENHANCEMENT.value:
            submission.severity = brief_data.get("severity")
        submission.status = SubmissionStatus.NEW.value
        submission.conversation_complete = True

        return await self.repo.update_submission(submission)

    async def get_conversation(self, submission_id: UUID, tenant_id: UUID) -> list[FeedbackMessage]:
        """Get conversation messages for a submission."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)
        messages = await self.repo.list_messages(submission_id)
        return [m for m in messages if m.role != MessageRole.SYSTEM.value]

    async def list_submissions(
        self,
        tenant_id: UUID,
        status: str | None = None,
        submission_type: str | None = None,
        submitter_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FeedbackSubmission], int]:
        """List submissions with filters."""
        return await self.repo.list_submissions(
            tenant_id=tenant_id,
            status=status,
            submission_type=submission_type,
            submitter_id=submitter_id,
            limit=limit,
            offset=offset,
        )

    async def get_submission(self, submission_id: UUID, tenant_id: UUID) -> FeedbackSubmission:
        """Get a single submission."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)
        return submission

    async def update_status(
        self, submission_id: UUID, tenant_id: UUID, new_status: str
    ) -> FeedbackSubmission:
        """Update submission status."""
        submission = await self.repo.update_status(submission_id, tenant_id, new_status)
        if not submission:
            raise SubmissionNotFoundError(submission_id)
        return submission

    async def get_stats(self, tenant_id: UUID, submitter_id: UUID | None = None) -> dict:
        """Get submission statistics."""
        return await self.repo.get_stats(tenant_id, submitter_id)

    async def add_comment(
        self,
        submission_id: UUID,
        tenant_id: UUID,
        author_id: UUID,
        author_name: str,
        content: str,
    ) -> FeedbackComment:
        """Add a team comment to a submission."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)

        comment = FeedbackComment(
            submission_id=submission_id,
            author_id=author_id,
            author_name=author_name,
            content=content,
        )
        return await self.repo.create_comment(comment)

    async def list_comments(self, submission_id: UUID, tenant_id: UUID) -> list[FeedbackComment]:
        """List comments for a submission."""
        submission = await self.repo.get_submission(submission_id, tenant_id)
        if not submission:
            raise SubmissionNotFoundError(submission_id)
        return await self.repo.list_comments(submission_id)

    async def get_message_count(self, submission_id: UUID) -> int:
        return await self.repo.count_messages(submission_id)

    async def get_comment_count(self, submission_id: UUID) -> int:
        return await self.repo.count_comments(submission_id)

    async def _call_claude(self, submission_id: UUID) -> str:
        """Call Claude with the full conversation history."""
        messages = await self.repo.list_messages(submission_id)

        system_prompt = ""
        api_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM.value:
                system_prompt = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        response = self.claude.messages.create(
            model=self.claude_model,
            max_tokens=2048,
            system=system_prompt,
            messages=api_messages,
        )

        return response.content[0].text

    def _looks_like_brief_ready(self, text: str) -> bool:
        """Heuristic check if the assistant is signaling brief readiness."""
        indicators = [
            "enough detail",
            "write up the brief",
            "generate the brief",
            "generate it for you",
            "write up the report",
            "generate the report",
            "let me put together",
            "here's the brief",
        ]
        lower = text.lower()
        return any(indicator in lower for indicator in indicators)

    async def _try_generate_brief(
        self, submission_id: UUID, submission_type: str
    ) -> tuple[bool, dict | None, str | None]:
        """Attempt to generate a structured brief from the conversation."""
        messages = await self.repo.list_messages(submission_id)

        system_prompt = ""
        api_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM.value:
                system_prompt = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        api_messages.append({"role": "user", "content": BRIEF_GENERATION_PROMPT})

        response = self.claude.messages.create(
            model=self.claude_model,
            max_tokens=2048,
            system=system_prompt,
            messages=api_messages,
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        try:
            brief_data = json.loads(raw)
            brief_markdown = render_brief_markdown(brief_data, submission_type)
            return True, brief_data, brief_markdown
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse brief JSON: %s", e)
            return False, None, None
