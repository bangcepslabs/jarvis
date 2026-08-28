from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.auth import require_client_auth
from app.api.dependencies import get_tts_service
from app.schemas.tts import TTSRequest
from app.tts.exceptions import TTSEnabledError, TTSTextValidationError, TTSTimeoutError, TTSProviderError

router = APIRouter(prefix="/api", tags=["tts"])


@router.post("/tts/synthesize", dependencies=[Depends(require_client_auth)])
async def synthesize(request: TTSRequest) -> Response:
    try:
        result = await get_tts_service().synthesize(request.text, request.language, request.speaker, request.speed, request.presentation_hint, request.voice_profile_id)
        return Response(content=result.audio_bytes, media_type=result.media_type, headers={"X-TTS-Provider": result.provider, "X-Audio-Duration": str(result.duration_seconds), "X-Sample-Rate": str(result.sample_rate)})
    except TTSEnabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSTextValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TTSTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
