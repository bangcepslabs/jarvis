"""Production STT endpoint smoke harness; never prints raw audio or logs transcript."""
import os
import time
import wave
from pathlib import Path

os.environ["STT_ENABLED"] = "true"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_stt_service


audio_path = Path("samples/jarvis_stt_test_ko.wav")
with wave.open(str(audio_path), "rb") as wav:
    audio_duration = wav.getnframes() / wav.getframerate()
audio = audio_path.read_bytes()
get_stt_service.cache_clear()
client = TestClient(app)

def run_once():
    started = time.perf_counter()
    response = client.post("/api/stt/transcribe", files={"file": (audio_path.name, audio, "audio/wav")})
    return response, time.perf_counter() - started

first, cold = run_once()
service = get_stt_service()
provider = service._provider
model_loaded_after_cold = getattr(provider, "_model", None) is not None
second, warm = run_once()
model_loaded_after_warm = getattr(provider, "_model", None) is not None

print(f"HTTP first={first.status_code} second={second.status_code}")
print(f"audio_duration_seconds={audio_duration:.3f}")
print(f"cold_start_seconds={cold:.3f}")
print(f"warm_transcription_seconds={warm:.3f}")
print(f"real_time_factor={warm / audio_duration if audio_duration else None:.3f}")
print(f"model_load_success={model_loaded_after_cold}")
print(f"model_reused={model_loaded_after_cold and model_loaded_after_warm}")
for label, response in (("first", first), ("second", second)):
    data = response.json()
    transcript = data.get("text", "")
    quality = all(word in transcript.replace(" ", "") for word in ("자비스", "부산", "날씨"))
    print(f"{label} speech_detected={data.get('speech_detected')} language={data.get('language')} language_probability={data.get('language_probability')} duration_seconds={data.get('duration_seconds')} transcript_quality_core_words={quality}")
    print(f"{label} transcript={transcript}")
