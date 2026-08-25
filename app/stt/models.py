from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    text: str = ""
    language: str | None = None
    language_probability: float | None = None
    duration_seconds: float | None = None
    speech_detected: bool = True
    segments: list[TranscriptSegment] | None = None
