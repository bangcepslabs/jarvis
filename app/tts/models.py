from pydantic import BaseModel


class SynthesisResult(BaseModel):
    audio_bytes: bytes
    media_type: str = "audio/wav"
    sample_rate: int
    duration_seconds: float
    provider: str
