"""Inspect and label the opt-in STT sample manifest."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
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
    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_record(records: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    matches = [record for record in records if identifier in {str(record.get("id", "")), str(record.get("audio_file", ""))}]
    if len(matches) > 1:
        raise SystemExit(f"Sample identifier is ambiguous: {identifier}")
    if matches:
        return matches[0]
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


def is_pending(record: dict[str, Any]) -> bool:
    return not str(record.get("expected_transcript") or "").strip()


def print_pending(record: dict[str, Any], manifest: Path) -> None:
    raw = str(record.get("raw_transcript") or "").strip() or "<empty>"
    print(f"[{record.get('id', '<unknown>')}]")
    print(f"file: {record.get('audio_file', '<missing>')}")
    print(f"audio: {audio_path(manifest, record)}")
    print(f"raw: {raw}")
    print("expected: <empty>")


def pending_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if is_pending(record)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the opt-in JARVIS STT sample dataset.")
    parser.add_argument("command", choices=["list", "set", "show", "pending", "next", "accept", "accept-all", "summary", "export"])
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("expected", nargs="?")
    parser.add_argument("--manifest", type=Path, default=Path("data/stt_samples/manifest.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("tmp/stt_dataset.json"))
    parser.add_argument("--force", action="store_true", help="Allow accept to overwrite an existing label.")
    parser.add_argument("--yes", action="store_true", help="Confirm bulk accept-all changes.")
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
        print(f"set {record['id']}")
        print(f"expected: {args.expected}")
    elif args.command == "accept":
        if not args.identifier:
            raise SystemExit("accept requires <id-or-file>")
        record = resolve_record(records, args.identifier)
        raw = str(record.get("raw_transcript") or "").strip()
        if not raw:
            raise SystemExit(f"Cannot accept {record['id']}: raw_transcript is empty")
        if not is_pending(record) and not args.force:
            raise SystemExit(f"Sample {record['id']} is already labeled; use --force to overwrite")
        record["expected_transcript"] = raw
        write_manifest(manifest, records)
        print(f"accepted {record['id']}")
        print(f"expected: {raw}")
    elif args.command == "accept-all":
        candidates = [record for record in records if is_pending(record) and str(record.get("raw_transcript") or "").strip()]
        print(f"{len(candidates)} samples would be accepted.")
        if not args.yes:
            print("Run again with --yes to continue.")
        else:
            for record in candidates:
                record["expected_transcript"] = str(record["raw_transcript"]).strip()
            write_manifest(manifest, records)
            print(f"accepted {len(candidates)} samples")
    elif args.command == "show":
        if not args.identifier:
            raise SystemExit("show requires <id-or-file>")
        record = resolve_record(records, args.identifier)
        print(f"id: {record.get('id', '<unknown>')}")
        print(f"audio file: {record.get('audio_file', '<missing>')}")
        print(f"audio: {audio_path(manifest, record)}")
        print(f"duration: {record.get('duration_ms', '<unknown>')} ms")
        print(f"created_at: {record.get('created_at', '<unknown>')}")
        print(f"raw_transcript: {str(record.get('raw_transcript') or '').strip() or '<empty>'}")
        print(f"expected_transcript: {str(record.get('expected_transcript') or '').strip() or '<empty>'}")
    elif args.command == "pending":
        for index, record in enumerate(pending_records(records)):
            if index:
                print()
            print_pending(record, manifest)
    elif args.command == "next":
        pending = pending_records(records)
        if not pending:
            print("No pending samples.")
        else:
            record = min(pending, key=lambda item: str(item.get("created_at") or ""))
            print_pending(record, manifest)
    elif args.command == "summary":
        pending = pending_records(records)
        raw_empty = sum(not str(record.get("raw_transcript") or "").strip() for record in records)
        print(f"total: {len(records)}")
        print(f"labeled: {len(records) - len(pending)}")
        print(f"pending: {len(pending)}")
        print(f"raw empty: {raw_empty}")
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
