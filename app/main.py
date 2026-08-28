from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.chat import router as chat_router
from app.api.routes.stt import router as stt_router
from app.api.routes.tts import router as tts_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import JarvisError
from app.core.logging import configure_logging
from app.api.dependencies import get_stt_service, get_tts_service
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    for enabled, name, factory in ((settings.stt_preload, "stt", get_stt_service), (settings.tts_preload, "tts", get_tts_service)):
        if enabled:
            try:
                await factory().preload()
                logger.info("voice_model_preloaded component=%s", name)
            except Exception:
                logger.warning("voice_model_preload_failed component=%s", name)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.exception_handler(JarvisError)
async def handle_jarvis_error(_: Request, exc: JarvisError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.app_version}


app.include_router(health_router)
app.include_router(chat_router)
app.include_router(stt_router)
app.include_router(tts_router)
