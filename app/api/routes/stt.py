from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.dependencies import get_stt_service
from app.stt.exceptions import AudioTooLargeError, STTDisabledError, STTProviderError, STTTimeoutError
from app.stt.service import STTService

router = APIRouter(prefix="/api", tags=["stt"])


@router.post("/stt/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        service = get_stt_service()
        audio = await file.read()
        result = await service.transcribe(audio, file.filename)
        return result.model_dump(exclude={"segments"})
    except AudioTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except STTDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except STTTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except STTProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
