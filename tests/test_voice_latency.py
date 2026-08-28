import pytest

from app.stt.service import STTService
from app.tts.service import TTSService


class Preloadable:
    def __init__(self):
        self.preloaded = False

    async def preload(self):
        self.preloaded = True


@pytest.mark.asyncio
async def test_stt_and_tts_preload_are_optional_provider_capabilities():
    stt = Preloadable()
    tts = Preloadable()
    await STTService(stt).preload()
    await TTSService(tts).preload()
    assert stt.preloaded and tts.preloaded
