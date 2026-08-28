from fastapi import APIRouter, Depends, HTTPException, Response
import time
from app.core.config import get_settings

from app.api.auth import require_client_auth
from app.api.dependencies import get_tts_service
from app.schemas.tts import TTSRequest
from app.tts.exceptions import TTSEnabledError, TTSTextValidationError, TTSTimeoutError, TTSProviderError

router = APIRouter(prefix="/api", tags=["tts"])


@router.post("/tts/synthesize", dependencies=[Depends(require_client_auth)])
async def synthesize(request: TTSRequest) -> Response:
    try:
        started = time.perf_counter()
        result = await get_tts_service().synthesize(request.text, request.language, request.speaker, request.speed, request.presentation_hint, request.voice_profile_id)
        headers = {"X-TTS-Provider": result.provider, "X-Audio-Duration": str(result.duration_seconds), "X-Sample-Rate": str(result.sample_rate)}
        if get_settings().voice_latency_metrics:
            headers["Server-Timing"] = f"tts;dur={round((time.perf_counter() - started) * 1000)}"
        return Response(content=result.audio_bytes, media_type=result.media_type, headers=headers)
    except TTSEnabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSTextValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TTSTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
