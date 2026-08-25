"""Compatibility-only Supertonic 3 validation; does not modify JARVIS production code."""
import time
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx

MODEL = Path("tmp/sherpa-onnx-supertonic-3-tts-int8-2026-05-11")
def p(name):
    return str(MODEL / name)

started = time.perf_counter()
supertonic = sherpa_onnx.OfflineTtsSupertonicModelConfig(
    p("duration_predictor.int8.onnx"), p("text_encoder.int8.onnx"),
    p("vector_estimator.int8.onnx"), p("vocoder.int8.onnx"),
    p("tts.json"), p("unicode_indexer.bin"), p("voice.bin"),
)
model = sherpa_onnx.OfflineTtsModelConfig(supertonic=supertonic, num_threads=2, provider="cpu")
config = sherpa_onnx.OfflineTtsConfig(model=model)
assert config.validate(), str(config)
tts = sherpa_onnx.OfflineTts(config)
load_elapsed = time.perf_counter() - started

texts = [
    "안녕하세요. 저는 자비스입니다.",
    "오늘 부산 날씨를 알려드릴게요.",
    "Docker 컨테이너와 FastAPI 서버가 정상적으로 실행 중입니다.",
]
outputs = []
for text in texts:
    started = time.perf_counter()
    audio = tts.generate(text, sid=0, speed=1.0)
    elapsed = time.perf_counter() - started
    samples = np.asarray(audio.samples, dtype=np.float32)
    output = Path("tmp") / f"supertonic_validation_{len(outputs)}.wav"
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(audio.sample_rate); wav.writeframes(pcm.tobytes())
    outputs.append((text, elapsed, len(samples) / audio.sample_rate, audio.sample_rate, output.stat().st_size))

print(f"sherpa_onnx_version={getattr(sherpa_onnx, '__version__', 'unknown')}")
print(f"model_load_seconds={load_elapsed:.3f} model_load_success=True")
print(f"sample_rate={tts.sample_rate} num_speakers={tts.num_speakers}")
for text, elapsed, duration, rate, size in outputs:
    print(f"text={text}")
    print(f"synthesis_seconds={elapsed:.3f} generated_duration_seconds={duration:.3f} rtf={elapsed / duration:.3f} sample_rate={rate} wav_size={size} wav_valid={size > 44}")
