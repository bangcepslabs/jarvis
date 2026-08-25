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


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(get_settings())
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
