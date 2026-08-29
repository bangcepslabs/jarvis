"""Inspect and label the opt-in STT sample manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def resolve_record(records: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    for record in records:
        if identifier in {str(record.get("id", "")), str(record.get("audio_file", ""))}:
            return record
    raise SystemExit(f"Sample not found: {identifier}")


def audio_path(manifest: Path, record: dict[str, Any]) -> Path:
    root = manifest.parent.resolve()
    candidate = (root / str(record.get("audio_file", ""))).resolve()
    if candidate.parent != root or candidate.suffix.lower() != ".wav":
        raise SystemExit("Manifest audio path is outside the capture directory")
    return candidate


def labeled_dataset(manifest: Path, records: list[dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for record in records:
        expected = record.get("expected_transcript")
        if expected is not None and str(expected).strip():
            result.append({"file": str(audio_path(manifest, record)), "expected": str(expected)})
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the opt-in JARVIS STT sample dataset.")
    parser.add_argument("command", choices=["list", "set", "show", "pending", "export"])
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("expected", nargs="?")
    parser.add_argument("--manifest", type=Path, default=Path("data/stt_samples/manifest.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("tmp/stt_dataset.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = args.manifest.resolve()
    records = read_manifest(manifest)
    if args.command == "set":
        if not args.identifier or args.expected is None:
            raise SystemExit("set requires <id-or-file> <expected text>")
        record = resolve_record(records, args.identifier)
        record["expected_transcript"] = args.expected
        write_manifest(manifest, records)
        print(f"Labeled {record['id']}")
    elif args.command == "show":
        if not args.identifier:
            raise SystemExit("show requires <id-or-file>")
        print(json.dumps(resolve_record(records, args.identifier), ensure_ascii=False, indent=2))
    elif args.command == "pending":
        for record in records:
            if not record.get("expected_transcript"):
                print(f"{record.get('id')} {record.get('audio_file')}")
    elif args.command == "list":
        for record in records:
            print(f"{record.get('id')} {record.get('audio_file')} expected={'yes' if record.get('expected_transcript') else 'no'}")
    else:
        dataset = labeled_dataset(manifest, records)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported {len(dataset)} labeled samples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
