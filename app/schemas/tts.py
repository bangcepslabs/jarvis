from pydantic import BaseModel, Field
from app.agent.models import PresentationHint


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: str = "ko"
    speaker: int | None = Field(default=None, ge=0)
    speed: float | None = Field(default=None, gt=0)
    presentation_hint: PresentationHint | None = None
    voice_profile_id: str | None = Field(default=None, min_length=1, max_length=100)
