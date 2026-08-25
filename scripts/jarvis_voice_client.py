"""Small PC client composing the JARVIS STT, chat, and TTS HTTP APIs."""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
import uuid
import wave
from pathlib import Path
from typing import Any, Callable

import httpx


def _url(server: str, path: str) -> str:
    return server.rstrip("/") + path


def _mic_wav(device: int | str | None = None) -> bytes:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("microphone recording requires sounddevice") from exc
    input("Press Enter to start recording")
    frames: list[bytes] = []

    def callback(indata: Any, _frames: int, _time: Any, _status: Any) -> None:
        frames.append(indata.copy().tobytes())

    try:
        stream = sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", device=device, callback=callback)
        stream.start()
        input("Recording... Press Enter to stop")
        stream.stop()
        stream.close()
    except Exception as exc:
        raise RuntimeError(f"microphone unavailable: {exc.__class__.__name__}") from exc
    if not frames:
        raise RuntimeError("microphone returned no audio")
    payload = b"".join(frames)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(payload)
    return output.getvalue()


def _list_devices() -> int:
    try:
        import sounddevice as sd
        for index, device in enumerate(sd.query_devices()):
            print(f"{index}: {device['name']}")
        return 0
    except Exception as exc:
        print(f"Device listing unavailable ({exc.__class__.__name__})", file=sys.stderr)
        return 1


def _request(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"server unavailable ({exc.__class__.__name__})") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"{method} failed (HTTP {response.status_code})")
    return response


def run_pipeline(
    *,
    server: str,
    audio: bytes | None,
    text: str | None,
    conversation_id: str,
    play: bool = False,
    save_output: str | None = None,
    client: httpx.Client | None = None,
    player: Callable[[bytes], None] | None = None,
) -> str | None:
    owns_client = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        started = time.perf_counter()
        if text is None:
            assert audio is not None
            stt = _request(client, "POST", _url(server, "/api/stt/transcribe"), files={"file": ("voice.wav", audio, "audio/wav")}).json()
            if not stt.get("speech_detected") or not (stt.get("text") or "").strip():
                print("No speech detected.")
                return None
            text = str(stt["text"]).strip()
            print(f"You: {text}")
        chat = _request(client, "POST", _url(server, "/api/chat"), json={"message": text, "conversation_id": conversation_id}).json()
        reply = str(chat.get("reply", "")).strip()
        if not reply:
            raise RuntimeError("chat returned an empty reply")
        print(f"JARVIS: {reply}")
        tts = _request(client, "POST", _url(server, "/api/tts/synthesize"), json={"text": reply, "language": "ko"})
        if not tts.headers.get("content-type", "").startswith("audio/wav"):
            raise RuntimeError("TTS returned a non-WAV response")
        wav_bytes = tts.content
        if save_output:
            output_path = Path(save_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)
            print(f"Saved audio: {output_path}")
        if play:
            if player is not None:
                player(wav_bytes)
            elif sys.platform == "win32":
                import winsound
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            else:
                raise RuntimeError("local WAV playback is supported on Windows only")
        print(f"Response latency: {time.perf_counter() - started:.2f}s")
        return reply
    finally:
        if owns_client:
            client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS PC voice client")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", type=Path, help="WAV/audio file to transcribe")
    source.add_argument("--mic", action="store_true", help="record from the local microphone")
    source.add_argument("--text", help="send text directly, skipping STT")
    parser.add_argument("--server", default=os.getenv("JARVIS_CORE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--conversation-id", default=f"voice-{uuid.uuid4().hex[:12]}")
    parser.add_argument("--input-device", help="sounddevice input device index/name")
    playback = parser.add_mutually_exclusive_group()
    playback.add_argument("--play", action="store_true", help="play returned WAV locally")
    playback.add_argument("--no-play", action="store_true", help="do not play returned WAV")
    parser.add_argument("--save-output", metavar="PATH", help="explicitly save returned WAV")
    parser.add_argument("--list-devices", action="store_true", help="list local audio devices and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_devices:
        return _list_devices()
    if not any((args.file, args.mic, args.text is not None)):
        parser.error("one of --file, --mic, or --text is required")
    try:
        audio = None
        text = args.text
        if args.file:
            if not args.file.is_file():
                raise RuntimeError("audio file not found")
            audio = args.file.read_bytes()
        elif args.mic:
            audio = _mic_wav(args.input_device)
        run_pipeline(server=args.server, audio=audio, text=text, conversation_id=args.conversation_id, play=args.play, save_output=args.save_output)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Voice client error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
