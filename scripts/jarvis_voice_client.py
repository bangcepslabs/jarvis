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
        frames.append(bytes(indata))

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


def _input_device_arg(value: str) -> int | str:
    """Accept either a numeric PortAudio index or a device name."""
    try:
        return int(value)
    except ValueError:
        return value


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
    recording_elapsed: float | None = None,
    client: httpx.Client | None = None,
    player: Callable[[bytes], None] | None = None,
    client_token: str | None = None,
) -> str | None:
    owns_client = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        started = time.perf_counter()
        stt_elapsed: float | None = None
        chat_elapsed: float | None = None
        tts_elapsed: float | None = None
        headers = {"Authorization": f"Bearer {client_token}"} if client_token else {}
        if text is None:
            assert audio is not None
            stage_started = time.perf_counter()
            stt = _request(client, "POST", _url(server, "/api/stt/transcribe"), headers=headers, files={"file": ("voice.wav", audio, "audio/wav")}).json()
            stt_elapsed = time.perf_counter() - stage_started
            if not stt.get("speech_detected") or not (stt.get("text") or "").strip():
                print("No speech detected.")
                return None
            text = str(stt["text"]).strip()
            print(f"You: {text}")
        stage_started = time.perf_counter()
        chat = _request(client, "POST", _url(server, "/api/chat"), headers=headers, json={"message": text, "conversation_id": conversation_id}).json()
        chat_elapsed = time.perf_counter() - stage_started
        reply = str(chat.get("reply", "")).strip()
        if not reply:
            raise RuntimeError("chat returned an empty reply")
        print(f"JARVIS: {reply}")
        stage_started = time.perf_counter()
        tts = _request(client, "POST", _url(server, "/api/tts/synthesize"), headers=headers, json={"text": reply, "language": "ko"})
        tts_elapsed = time.perf_counter() - stage_started
        if not tts.headers.get("content-type", "").startswith("audio/wav"):
            raise RuntimeError("TTS returned a non-WAV response")
        wav_bytes = tts.content
        if save_output:
            output_path = Path(save_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)
            print(f"Saved audio: {output_path}")
        processing_elapsed = time.perf_counter() - started
        playback_started = time.perf_counter()
        if play:
            if player is not None:
                player(wav_bytes)
            elif sys.platform == "win32":
                import winsound
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            else:
                raise RuntimeError("local WAV playback is supported on Windows only")
        playback_elapsed = time.perf_counter() - playback_started if play else 0.0
        print("[voice]")
        print(f"recording_elapsed={recording_elapsed:.2f}s" if recording_elapsed is not None else "recording_elapsed=not_measured")
        print(f"stt_elapsed={stt_elapsed:.2f}s" if stt_elapsed is not None else "stt_elapsed=skipped")
        print(f"chat_elapsed={chat_elapsed:.2f}s")
        print(f"tts_elapsed={tts_elapsed:.2f}s")
        print(f"processing_elapsed={processing_elapsed:.2f}s")
        print(f"playback_elapsed={playback_elapsed:.2f}s")
        print(f"total_elapsed={time.perf_counter() - started:.2f}s")
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
    parser.add_argument("--client-token", default=os.getenv("JARVIS_CLIENT_TOKEN"), help="Bearer token for an authenticated Core")
    parser.add_argument("--conversation-id", default=f"voice-{uuid.uuid4().hex[:12]}")
    parser.add_argument("--input-device", type=_input_device_arg, help="sounddevice input device index/name")
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
        recording_elapsed = None
        if args.file:
            if not args.file.is_file():
                raise RuntimeError("audio file not found")
            audio = args.file.read_bytes()
        elif args.mic:
            recording_started = time.perf_counter()
            audio = _mic_wav(args.input_device)
            recording_elapsed = time.perf_counter() - recording_started
        run_pipeline(server=args.server, audio=audio, text=text, conversation_id=args.conversation_id, play=args.play, save_output=args.save_output, recording_elapsed=recording_elapsed, client_token=args.client_token)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Voice client error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
