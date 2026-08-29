"""Opt-in local capture of STT inputs for building a labeled dataset."""

from __future__ import annotations

import json
import logging
import uuid
import wave
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from app.stt.models import TranscriptionResult

logger = logging.getLogger(__name__)


class STTSampleCapture:
    def __init__(self, enabled: bool, directory: str, max_files: int, language: str | None, model: str, device: str, compute_type: str) -> None:
        if max_files < 1:
            raise ValueError("max_files must be positive")
        self.enabled = enabled
        self.directory = Path(directory)
        self.max_files = max_files
        self.language = language
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self.manifest = self.directory / "manifest.jsonl"

    def capture(self, audio: bytes, result: TranscriptionResult) -> None:
        if not self.enabled:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            existing = list(self.directory.glob("*.wav"))
            if len(existing) >= self.max_files:
                logger.warning("stt_sample_capture_limit_reached directory=%s max_files=%s", self.directory, self.max_files)
                return
            now = datetime.now(timezone.utc)
            sample_id = uuid.uuid4().hex[:6]
            filename = f"{now.strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{sample_id}.wav"
            audio_path = self.directory / filename
            audio_path.write_bytes(audio)
            duration_ms = round((result.duration_seconds or self._duration_seconds(audio)) * 1000)
            record = {
                "id": sample_id,
                "audio_file": filename,
                "created_at": now.isoformat(),
                "duration_ms": duration_ms,
                "language": result.language or self.language,
                "raw_transcript": result.text,
                "expected_transcript": None,
                "model": self.model,
                "device": self.device,
                "compute_type": self.compute_type,
            }
            try:
                with self.manifest.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception:
                audio_path.unlink(missing_ok=True)
                raise
        except Exception as exc:
            logger.warning("stt_sample_capture_failed error_type=%s", type(exc).__name__)

    @staticmethod
    def _duration_seconds(audio: bytes) -> float:
        with wave.open(BytesIO(audio), "rb") as wav:
            return wav.getnframes() / wav.getframerate()
