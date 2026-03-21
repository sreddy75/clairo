"""Whisper API transcription service for voice feedback."""

import logging
from pathlib import Path

from fastapi import UploadFile
from openai import OpenAI

from app.config import get_settings
from app.modules.feedback.exceptions import InvalidAudioError

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".webm"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB


class TranscriptionService:
    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.openai.api_key.get_secret_value()
        if not api_key:
            raise InvalidAudioError("OpenAI API key not configured for transcription")
        self.client = OpenAI(api_key=api_key)

    async def transcribe(self, audio_file: UploadFile) -> tuple[str, int]:
        """Transcribe an audio file using OpenAI Whisper API.

        Returns:
            tuple of (transcript_text, estimated_duration_seconds)
        """
        if not audio_file.filename:
            raise InvalidAudioError("Audio file must have a filename")

        ext = Path(audio_file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidAudioError(
                f"Unsupported audio format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        content = await audio_file.read()
        if len(content) > MAX_FILE_SIZE:
            raise InvalidAudioError(
                f"Audio file too large ({len(content) / 1024 / 1024:.1f}MB). Maximum: 25MB"
            )

        if len(content) < 1024:
            raise InvalidAudioError("Audio file too small — recording may be empty or corrupted")

        await audio_file.seek(0)

        logger.info(
            "Transcribing audio file: %s (%.1f KB)",
            audio_file.filename,
            len(content) / 1024,
        )

        transcription = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=(audio_file.filename, content, audio_file.content_type or "audio/webm"),
            response_format="verbose_json",
        )

        transcript_text = transcription.text.strip()
        duration_seconds = int(transcription.duration or 0)

        if not transcript_text:
            raise InvalidAudioError(
                "Could not transcribe audio — recording may contain only silence or noise"
            )

        logger.info(
            "Transcription complete: %d chars, %ds duration",
            len(transcript_text),
            duration_seconds,
        )

        return transcript_text, duration_seconds
