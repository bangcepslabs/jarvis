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
try:
    from scripts.stt_dataset import read_manifest, labeled_dataset
except ModuleNotFoundError:  # direct `python scripts/benchmark_stt.py` invocation
    from stt_dataset import read_manifest, labeled_dataset


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


def default_compute_type(device: str) -> str:
    return "int8" if device == "cpu" else "float16"


def build_model_kwargs(device: str, compute_type: str, cpu_threads: int, cache_dir: str | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"device": device, "compute_type": compute_type, "num_workers": 1}
    if device == "cpu":
        kwargs["cpu_threads"] = cpu_threads
    if cache_dir:
        kwargs["download_root"] = cache_dir
    return kwargs


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
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    load_started = time.perf_counter()
    kwargs = build_model_kwargs(device, compute_type, cpu_threads, cache_dir)
    try:
        model = WhisperModel(model_name, **kwargs)
    except Exception as exc:
        if device == "cuda":
            raise RuntimeError(
                "CUDA benchmark unavailable: failed to initialize faster-whisper with device=cuda "
                f"and compute_type={compute_type}. Check CUDA/ cuBLAS/cuDNN installation and GPU visibility."
            ) from exc
        raise RuntimeError(f"Failed to initialize faster-whisper CPU benchmark: {exc}") from exc
    load_ms = round((time.perf_counter() - load_started) * 1000)

    cold = transcribe(model, path, vad_filter, language, beam_size, bias_prompt)
    warm_runs = [transcribe(model, path, vad_filter, language, beam_size, bias_prompt) for _ in range(runs)]
    duration = audio_duration_seconds(path)
    warm_inference_ms = round(sum(item["inference_ms"] for item in warm_runs) / len(warm_runs))
    result: dict[str, Any] = {
        "file": str(path),
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
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
    parser = argparse.ArgumentParser(description="Benchmark local faster-whisper CPU or CUDA configurations.")
    parser.add_argument("--file", nargs="+", type=Path, help="One or more PCM WAV files.")
    parser.add_argument("--dataset", type=Path, help="JSONL manifest containing labeled STT samples.")
    parser.add_argument("--models", nargs="+", default=["small", "base", "tiny"], choices=["small", "base", "tiny"])
    parser.add_argument("--vad", nargs="+", type=parse_bool, default=[True, False], metavar="BOOL")
    parser.add_argument("--cpu-threads", nargs="+", type=int, default=[2, 4, 6], metavar="N")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--compute-type", help="faster-whisper compute type (default: int8 on CPU, float16 on CUDA).")
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
    if bool(args.file) == bool(args.dataset):
        raise SystemExit("provide exactly one of --file or --dataset")
    compute_type = args.compute_type or default_compute_type(args.device)
    expected_by_path: dict[Path, str] = {}
    skipped = 0
    if args.dataset:
        manifest = args.dataset.resolve()
        dataset = labeled_dataset(manifest, read_manifest(manifest))
        all_records = read_manifest(manifest)
        skipped = sum(1 for record in all_records if not record.get("expected_transcript"))
        paths = [Path(item["file"]).resolve() for item in dataset]
        expected_by_path = {Path(item["file"]).resolve(): item["expected"] for item in dataset}
        if not paths:
            raise SystemExit("dataset contains no labeled samples")
    else:
        paths = [path.resolve() for path in args.file]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"WAV file not found: {', '.join(missing)}")
    if args.expected and len(args.expected) not in {1, len(paths)}:
        raise SystemExit("--expected must contain one value or one value per --file")
    if args.expected:
        expected_by_path = dict(zip(paths, args.expected if len(args.expected) == len(paths) else [args.expected[0]] * len(paths)))
    bias_prompt = build_initial_prompt(args.bias_terms) if args.bias_terms else None
    bias_variants = [None, bias_prompt] if args.compare_bias and bias_prompt else [bias_prompt]

    results: list[dict[str, Any]] = []
    for path in paths:
        for model_name in args.models:
            for vad_filter in args.vad:
                for cpu_threads in args.cpu_threads:
                    for beam_size in args.beam_size:
                        for variant in bias_variants:
                            try:
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
                                    args.device,
                                    compute_type,
                                )
                            except RuntimeError as exc:
                                raise SystemExit(str(exc)) from exc
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
        f"Fastest warm config: model={fastest['model']} device={fastest['device']} "
        f"compute_type={fastest['compute_type']} vad={fastest['vad_filter']} "
        f"threads={fastest['cpu_threads']} inference={fastest['warm_inference_ms']}ms rtf={fastest['rtf']}"
    )
    if skipped:
        print(f"Skipped unlabeled dataset samples: {skipped}")
    if any("cer" in result for result in results):
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for result in results:
            key = (result["model"], result["vad_filter"], result["cpu_threads"], result["beam_size"], result["bias_prompt"])
            grouped.setdefault(key, []).append(result)
        print("Configuration summary:")
        for key, items in grouped.items():
            cers = sorted(item["cer"] for item in items)
            times = sorted(item["warm_inference_ms"] for item in items)
            rtfs = [item["rtf"] for item in items if item["rtf"] is not None]
            exact = sum(item["cer"] == 0 for item in items)
            percentile = lambda values, p: values[min(len(values) - 1, round((len(values) - 1) * p))]
            print(f"{key}: avgCER={sum(cers)/len(cers):.3f} medianCER={percentile(cers, .5):.3f} exact={exact}/{len(items)} avgMs={sum(times)/len(times):.0f} p50Ms={percentile(times, .5)} p95Ms={percentile(times, .95)} avgRTF={sum(rtfs)/len(rtfs):.3f}")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
