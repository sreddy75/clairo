"""Feedback API router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (  # noqa: F401
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ClerkUser, PracticeUserDep, TenantId, get_db
from app.modules.feedback.enums import SubmissionStatus, SubmissionType
from app.modules.feedback.schemas import (
    BriefConfirmRequest,
    CommentCreate,
    CommentResponse,
    ConversationResponse,
    ConversationTurnResponse,
    FeedbackStats,
    MessageCreate,
    MessageResponse,
    StatusUpdate,
    SubmissionDetailResponse,
    SubmissionListResponse,
    SubmissionResponse,
    VoiceConversationTurnResponse,
)
from app.modules.feedback.service import FeedbackService

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    db: DbSession,
    tenant_id: TenantId,
    user: ClerkUser,
    type: SubmissionType = Form(...),
    audio: UploadFile = File(...),
) -> SubmissionResponse:
    service = FeedbackService(db)
    submission = await service.create_submission(
        tenant_id=tenant_id,
        submitter_id=UUID(user.sub.replace("user_", "").ljust(32, "0")[:32])
        if not _is_uuid(user.sub)
        else UUID(user.sub),
        submitter_name=user.email or user.sub,
        submission_type=type.value,
        audio_file=audio,
    )
    await db.commit()
    return SubmissionResponse.from_model(submission)


@router.get("/stats", response_model=FeedbackStats)
async def get_stats(
    db: DbSession,
    tenant_id: TenantId,
    user: ClerkUser,
    practice_user: PracticeUserDep,
) -> FeedbackStats:
    service = FeedbackService(db)
    submitter_id = None if practice_user.is_admin else _user_uuid(user.sub)
    stats = await service.get_stats(tenant_id, submitter_id)
    return FeedbackStats(**stats)


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    db: DbSession,
    tenant_id: TenantId,
    user: ClerkUser,
    practice_user: PracticeUserDep,
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    type_filter: SubmissionType | None = Query(None, alias="type"),
    mine_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SubmissionListResponse:
    service = FeedbackService(db)
    submitter_id = None
    if mine_only or not practice_user.is_admin:
        submitter_id = _user_uuid(user.sub)

    items, total = await service.list_submissions(
        tenant_id=tenant_id,
        status=status_filter.value if status_filter else None,
        submission_type=type_filter.value if type_filter else None,
        submitter_id=submitter_id,
        limit=limit,
        offset=offset,
    )
    return SubmissionListResponse(
        items=[SubmissionResponse.from_model(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
) -> SubmissionDetailResponse:
    service = FeedbackService(db)
    submission = await service.get_submission(submission_id, tenant_id)
    message_count = await service.get_message_count(submission_id)
    comment_count = await service.get_comment_count(submission_id)
    return SubmissionDetailResponse.from_model(
        submission, message_count=message_count, comment_count=comment_count
    )


@router.patch("/{submission_id}/status", response_model=SubmissionResponse)
async def update_status(
    submission_id: UUID,
    data: StatusUpdate,
    db: DbSession,
    tenant_id: TenantId,
    practice_user: PracticeUserDep,
) -> SubmissionResponse:
    if not practice_user.is_admin:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")

    service = FeedbackService(db)
    submission = await service.update_status(submission_id, tenant_id, data.status.value)
    await db.commit()
    return SubmissionResponse.from_model(submission)


@router.get("/{submission_id}/conversation", response_model=ConversationResponse)
async def get_conversation(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
) -> ConversationResponse:
    service = FeedbackService(db)
    messages = await service.get_conversation(submission_id, tenant_id)
    return ConversationResponse(messages=[MessageResponse.from_model(m) for m in messages])


@router.post(
    "/{submission_id}/conversation/message",
    response_model=ConversationTurnResponse,
)
async def send_message(
    submission_id: UUID,
    data: MessageCreate,
    db: DbSession,
    tenant_id: TenantId,
) -> ConversationTurnResponse:
    service = FeedbackService(db)
    result = await service.send_message(submission_id, tenant_id, data.content, data.content_type)
    await db.commit()
    return ConversationTurnResponse(
        user_message=MessageResponse.from_model(result["user_message"]),
        assistant_message=MessageResponse.from_model(result["assistant_message"]),
        brief_ready=result["brief_ready"],
        brief_data=result["brief_data"],
        brief_markdown=result["brief_markdown"],
    )


@router.post(
    "/{submission_id}/conversation/voice",
    response_model=VoiceConversationTurnResponse,
)
async def send_voice_message(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
    audio: UploadFile = File(...),
) -> VoiceConversationTurnResponse:
    service = FeedbackService(db)
    result = await service.send_voice_message(submission_id, tenant_id, audio)
    await db.commit()
    return VoiceConversationTurnResponse(
        user_message=MessageResponse.from_model(result["user_message"]),
        assistant_message=MessageResponse.from_model(result["assistant_message"]),
        brief_ready=result["brief_ready"],
        brief_data=result["brief_data"],
        brief_markdown=result["brief_markdown"],
        transcript=result["transcript"],
    )


@router.post("/{submission_id}/confirm", response_model=SubmissionResponse)
async def confirm_brief(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
    data: BriefConfirmRequest | None = None,
) -> SubmissionResponse:
    service = FeedbackService(db)
    revisions = data.revisions if data else None
    submission = await service.confirm_brief(submission_id, tenant_id, revisions)
    await db.commit()
    return SubmissionResponse.from_model(submission)


@router.get("/{submission_id}/export")
async def export_brief(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
) -> Response:
    service = FeedbackService(db)
    submission = await service.get_submission(submission_id, tenant_id)

    from app.modules.feedback.exceptions import BriefNotReadyError

    if not submission.brief_markdown:
        raise BriefNotReadyError(submission_id)

    return Response(
        content=submission.brief_markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="feedback-{submission_id}-brief.md"'
        },
    )


@router.get("/{submission_id}/comments")
async def list_comments(
    submission_id: UUID,
    db: DbSession,
    tenant_id: TenantId,
    practice_user: PracticeUserDep,
) -> dict:
    if not practice_user.is_admin:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")

    service = FeedbackService(db)
    comments = await service.list_comments(submission_id, tenant_id)
    return {
        "items": [CommentResponse.from_model(c) for c in comments],
        "total": len(comments),
    }


@router.post(
    "/{submission_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    submission_id: UUID,
    data: CommentCreate,
    db: DbSession,
    tenant_id: TenantId,
    user: ClerkUser,
    practice_user: PracticeUserDep,
) -> CommentResponse:
    if not practice_user.is_admin:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")

    service = FeedbackService(db)
    comment = await service.add_comment(
        submission_id=submission_id,
        tenant_id=tenant_id,
        author_id=_user_uuid(user.sub),
        author_name=user.email or user.sub,
        content=data.content,
    )
    await db.commit()
    return CommentResponse.from_model(comment)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _user_uuid(clerk_id: str) -> UUID:
    """Convert a Clerk user ID to a deterministic UUID."""
    import hashlib

    h = hashlib.sha256(clerk_id.encode()).hexdigest()[:32]
    return UUID(h)
