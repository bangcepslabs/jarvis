from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import logging
import time
from app.core.config import get_settings

from app.api.auth import require_client_auth
from app.api.dependencies import get_stt_service
from app.stt.exceptions import AudioTooLargeError, STTDisabledError, STTProviderError, STTTimeoutError
from app.stt.service import STTService

router = APIRouter(prefix="/api", tags=["stt"])
logger = logging.getLogger(__name__)


@router.post("/stt/transcribe", dependencies=[Depends(require_client_auth)])
async def transcribe(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        service = get_stt_service()
        audio = await file.read()
        started = time.perf_counter()
        result = await service.transcribe(audio, file.filename)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        audio_duration_ms = round((result.duration_seconds or 0) * 1000)
        timing = {
            "audio_duration_ms": audio_duration_ms,
            "server_stt_total_ms": elapsed_ms,
            **(result.timings_ms or {}),
        }
        logger.info(
            "stt_result language=%s chars=%s empty=%s audio_duration_ms=%s timings=%s",
            result.language or "unknown",
            len(result.text.strip()),
            not bool(result.text.strip()),
            audio_duration_ms,
            timing,
        )
        payload = result.model_dump(exclude={"segments", "timings_ms"})
        if get_settings().voice_latency_metrics:
            payload["_timing"] = timing
        return payload
    except AudioTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except STTDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except STTTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except STTProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
