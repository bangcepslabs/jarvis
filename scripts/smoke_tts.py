"""Production TTS endpoint smoke using the official local Supertonic artifact."""
import os
import time
import wave
from pathlib import Path

os.environ["TTS_ENABLED"] = "true"
os.environ["TTS_PROVIDER"] = "sherpa_onnx"
os.environ["TTS_MODEL_DIR"] = str(Path("data/models/tts/supertonic-3").resolve())
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies import get_tts_service

client = TestClient(app)
get_tts_service.cache_clear()
texts = ["안녕하세요. 저는 자비스입니다.", "오늘 부산 날씨를 알려드릴게요.", "Docker 컨테이너와 FastAPI 서버가 정상적으로 실행 중입니다."]

def call(text):
    started = time.perf_counter()
    response = client.post("/api/tts/synthesize", json={"text": text, "language": "ko", "speaker": 0, "speed": 1.0})
    return response, time.perf_counter() - started

first, cold = call(texts[0])
service = get_tts_service()
provider = service._provider
loaded_cold = getattr(provider, "_tts", None) is not None
second, warm = call(texts[0])
loaded_warm = getattr(provider, "_tts", None) is not None
extras = [call(text)[0] for text in texts[1:]]

print(f"first_http={first.status_code} second_http={second.status_code} extra_http={[r.status_code for r in extras]}")
print(f"cold_start_seconds={cold:.3f} warm_synthesis_seconds={warm:.3f} model_load_success={loaded_cold} model_reused={loaded_cold and loaded_warm}")
for label, response in (("first", first), ("second", second), ("mixed", extras[-1])):
    output = Path("tmp") / f"jarvis_tts_validation_{label}.wav"
    output.write_bytes(response.content)
    with wave.open(str(output), "rb") as wav:
        duration = wav.getnframes() / wav.getframerate()
        valid = wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() > 0 and output.stat().st_size > 44
    print(f"{label}_content_type={response.headers.get('content-type')} provider={response.headers.get('x-tts-provider')} sample_rate={response.headers.get('x-sample-rate')} duration={duration:.3f} size={output.stat().st_size} wav_valid={valid}")
