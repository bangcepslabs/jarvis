from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: str = "ko"
    speaker: int = Field(default=0, ge=0)
    speed: float = Field(default=1.0, gt=0)
