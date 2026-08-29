"""Reproducible local faster-whisper benchmark.

This script intentionally bypasses the Core HTTP endpoint so model loading and
inference can be measured separately. It does not change production settings.
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path
from typing import Any

from app.stt.context import build_initial_prompt


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def normalize(text: str) -> str:
    return "".join(text.split()).lower()


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(actual: str, expected: str) -> float:
    expected_normalized = normalize(expected)
    if not expected_normalized:
        return 0.0 if not normalize(actual) else 1.0
    return edit_distance(normalize(actual), expected_normalized) / len(expected_normalized)


def audio_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def transcribe(model: Any, path: Path, vad_filter: bool, language: str, beam_size: int, bias_prompt: str | None) -> dict[str, Any]:
    started = time.perf_counter()
    kwargs: dict[str, Any] = {"language": language, "beam_size": beam_size, "vad_filter": vad_filter}
    if bias_prompt:
        kwargs["initial_prompt"] = bias_prompt
    segments, info = model.transcribe(str(path), **kwargs)
    texts = [segment.text or "" for segment in segments]
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    text = "".join(texts).strip()
    return {
        "inference_ms": elapsed_ms,
        "text": text,
        "chars": len(text),
        "empty": not bool(text),
        "language": getattr(info, "language", None),
    }


def benchmark_config(
    path: Path,
    model_name: str,
    vad_filter: bool,
    cpu_threads: int,
    runs: int,
    cache_dir: str | None,
    language: str,
    beam_size: int,
    bias_prompt: str | None,
) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    load_started = time.perf_counter()
    kwargs: dict[str, Any] = {
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": cpu_threads,
        "num_workers": 1,
    }
    if cache_dir:
        kwargs["download_root"] = cache_dir
    model = WhisperModel(model_name, **kwargs)
    load_ms = round((time.perf_counter() - load_started) * 1000)

    cold = transcribe(model, path, vad_filter, language, beam_size, bias_prompt)
    warm_runs = [transcribe(model, path, vad_filter, language, beam_size, bias_prompt) for _ in range(runs)]
    duration = audio_duration_seconds(path)
    warm_inference_ms = round(sum(item["inference_ms"] for item in warm_runs) / len(warm_runs))
    result: dict[str, Any] = {
        "file": str(path),
        "model": model_name,
        "device": "cpu",
        "compute_type": "int8",
        "vad_filter": vad_filter,
        "cpu_threads": cpu_threads,
        "runs": runs,
        "audio_duration_ms": round(duration * 1000),
        "model_load_ms": load_ms,
        "cold_inference_ms": cold["inference_ms"],
        "cold_total_ms": load_ms + cold["inference_ms"],
        "warm_inference_ms": warm_inference_ms,
        "total_ms": warm_inference_ms,
        "rtf": round((warm_inference_ms / 1000) / duration, 3) if duration else None,
        "beam_size": beam_size,
        "bias_prompt": bool(bias_prompt),
        "chars": warm_runs[-1]["chars"],
        "empty": warm_runs[-1]["empty"],
        "language": warm_runs[-1]["language"],
    }
    return result | {"_transcript": warm_runs[-1]["text"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark local faster-whisper CPU configurations.")
    parser.add_argument("--file", nargs="+", required=True, type=Path, help="One or more PCM WAV files.")
    parser.add_argument("--models", nargs="+", default=["small", "base", "tiny"], choices=["small", "base", "tiny"])
    parser.add_argument("--vad", nargs="+", type=parse_bool, default=[True, False], metavar="BOOL")
    parser.add_argument("--cpu-threads", nargs="+", type=int, default=[2, 4, 6], metavar="N")
    parser.add_argument("--runs", type=int, default=3, help="Warm inference repetitions per configuration.")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--language", default="ko")
    parser.add_argument("--beam-size", nargs="+", type=int, default=[1], metavar="N")
    parser.add_argument("--bias-terms", default="", help="Comma-separated terms used as initial_prompt.")
    parser.add_argument("--compare-bias", action="store_true", help="Run both without and with --bias-terms.")
    parser.add_argument("--expected", nargs="+", help="Expected text per input file for normalized CER.")
    parser.add_argument("--show-transcript", action="store_true", help="Explicitly print the recognized text.")
    parser.add_argument("--json-output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.runs < 1 or any(thread <= 0 for thread in args.cpu_threads) or any(size < 1 for size in args.beam_size):
        raise SystemExit("--runs and --cpu-threads must be positive")
    paths = [path.resolve() for path in args.file]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"WAV file not found: {', '.join(missing)}")
    if args.expected and len(args.expected) not in {1, len(paths)}:
        raise SystemExit("--expected must contain one value or one value per --file")
    expected_by_path = dict(zip(paths, args.expected if args.expected and len(args.expected) == len(paths) else [args.expected[0]] * len(paths))) if args.expected else {}
    bias_prompt = build_initial_prompt(args.bias_terms) if args.bias_terms else None
    bias_variants = [None, bias_prompt] if args.compare_bias and bias_prompt else [bias_prompt]

    results: list[dict[str, Any]] = []
    for path in paths:
        for model_name in args.models:
            for vad_filter in args.vad:
                for cpu_threads in args.cpu_threads:
                    for beam_size in args.beam_size:
                        for variant in bias_variants:
                            result = benchmark_config(
                                path,
                                model_name,
                                vad_filter,
                                cpu_threads,
                                args.runs,
                                str(args.cache_dir) if args.cache_dir else None,
                                args.language,
                                beam_size,
                                variant,
                            )
                            transcript = result.pop("_transcript")
                            if path in expected_by_path:
                                result["cer"] = round(character_error_rate(transcript, expected_by_path[path]), 3)
                            if args.show_transcript:
                                result["transcript"] = transcript
                            results.append(result)

    print("Model | VAD | Threads | Load | Cold | Warm | RTF | Chars")
    print("------|-----|---------|------|------|------|-----|------")
    for result in results:
        print(
            f"{result['model']} | {'on' if result['vad_filter'] else 'off'} | "
            f"{result['cpu_threads']} | beam={result['beam_size']} | bias={'on' if result['bias_prompt'] else 'off'} | "
            f"{result['model_load_ms']}ms | "
            f"{result['cold_inference_ms']}ms | {result['warm_inference_ms']}ms | "
            f"{result['rtf']} | {result['chars']}"
        )
    fastest = min(results, key=lambda item: item["warm_inference_ms"])
    print(
        f"Fastest warm config: model={fastest['model']} vad={fastest['vad_filter']} "
        f"threads={fastest['cpu_threads']} inference={fastest['warm_inference_ms']}ms rtf={fastest['rtf']}"
    )
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
