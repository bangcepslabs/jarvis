from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import time
from app.core.config import get_settings

from app.api.auth import require_client_auth
from app.api.dependencies import get_stt_service
from app.stt.exceptions import AudioTooLargeError, STTDisabledError, STTProviderError, STTTimeoutError
from app.stt.service import STTService

router = APIRouter(prefix="/api", tags=["stt"])


@router.post("/stt/transcribe", dependencies=[Depends(require_client_auth)])
async def transcribe(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        service = get_stt_service()
        audio = await file.read()
        started = time.perf_counter()
        result = await service.transcribe(audio, file.filename)
        payload = result.model_dump(exclude={"segments"})
        if get_settings().voice_latency_metrics:
            payload["_timing"] = {"stt_total_ms": round((time.perf_counter() - started) * 1000)}
        return payload
    except AudioTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except STTDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except STTTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except STTProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
