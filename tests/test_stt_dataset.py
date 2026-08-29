import json

from scripts.stt_dataset import labeled_dataset, read_manifest, write_manifest


def test_dataset_label_and_export_helpers(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, [
        {"id": "a1", "audio_file": "one.wav", "expected_transcript": "hello"},
        {"id": "a2", "audio_file": "two.wav", "expected_transcript": None},
    ])
    dataset = labeled_dataset(manifest, read_manifest(manifest))
    assert dataset == [{"file": str(tmp_path / "one.wav"), "expected": "hello"}]


def test_dataset_cli_set_pending_export(tmp_path, monkeypatch, capsys):
    from scripts import stt_dataset

    manifest = tmp_path / "manifest.jsonl"
    stt_dataset.write_manifest(manifest, [{"id": "a1", "audio_file": "one.wav", "expected_transcript": None}])
    monkeypatch.setattr("sys.argv", ["stt_dataset", "set", "a1", "hello", "--manifest", str(manifest)])
    assert stt_dataset.main() == 0
    assert json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])["expected_transcript"] == "hello"
    output = tmp_path / "dataset.json"
    monkeypatch.setattr("sys.argv", ["stt_dataset", "export", "--manifest", str(manifest), "--output", str(output)])
    assert stt_dataset.main() == 0
    assert json.loads(output.read_text())[0]["expected"] == "hello"


def manifest_with_samples(tmp_path):
    (tmp_path / "old.wav").write_bytes(b"wav")
    (tmp_path / "new.wav").write_bytes(b"wav")
    manifest = tmp_path / "manifest.jsonl"
    stt_dataset_records = [
        {"id": "old", "audio_file": "old.wav", "created_at": "2026-01-01", "raw_transcript": "old raw", "expected_transcript": None},
        {"id": "new", "audio_file": "new.wav", "created_at": "2026-01-02", "raw_transcript": "new raw", "expected_transcript": "existing"},
        {"id": "empty", "audio_file": "old.wav", "created_at": "2026-01-03", "raw_transcript": "", "expected_transcript": None},
    ]
    write_manifest(manifest, stt_dataset_records)
    return manifest


def run_cli(monkeypatch, command, manifest, *extra):
    from scripts import stt_dataset
    monkeypatch.setattr("sys.argv", ["stt_dataset", command, *extra, "--manifest", str(manifest)])
    return stt_dataset.main()


def test_pending_next_and_summary_show_raw(tmp_path, monkeypatch, capsys):
    manifest = manifest_with_samples(tmp_path)
    run_cli(monkeypatch, "pending", manifest)
    output = capsys.readouterr().out
    assert "[old]" in output and "raw: old raw" in output
    assert "raw: <empty>" in output
    run_cli(monkeypatch, "next", manifest)
    assert "[old]" in capsys.readouterr().out
    run_cli(monkeypatch, "summary", manifest)
    output = capsys.readouterr().out
    assert "total: 3" in output
    assert "labeled: 1" in output
    assert "pending: 2" in output


def test_accept_and_force_and_empty_rejection(tmp_path, monkeypatch):
    from scripts import stt_dataset
    manifest = manifest_with_samples(tmp_path)
    run_cli(monkeypatch, "accept", manifest, "old")
    assert read_manifest(manifest)[0]["expected_transcript"] == "old raw"
    monkeypatch.setattr("sys.argv", ["stt_dataset", "accept", "new", "--manifest", str(manifest)])
    try:
        stt_dataset.main()
    except SystemExit as exc:
        assert "already labeled" in str(exc)
    else:
        raise AssertionError("accept should protect an existing label")
    monkeypatch.setattr("sys.argv", ["stt_dataset", "accept", "new", "--force", "--manifest", str(manifest)])
    stt_dataset.main()
    assert read_manifest(manifest)[1]["expected_transcript"] == "new raw"
    monkeypatch.setattr("sys.argv", ["stt_dataset", "accept", "empty", "--manifest", str(manifest)])
    try:
        stt_dataset.main()
    except SystemExit as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("empty raw should not be accepted")


def test_accept_all_dry_run_and_yes_does_not_overwrite(tmp_path, monkeypatch):
    from scripts import stt_dataset
    manifest = manifest_with_samples(tmp_path)
    run_cli(monkeypatch, "accept-all", manifest)
    assert read_manifest(manifest)[0]["expected_transcript"] is None
    monkeypatch.setattr("sys.argv", ["stt_dataset", "accept-all", "--yes", "--manifest", str(manifest)])
    stt_dataset.main()
    records = read_manifest(manifest)
    assert records[0]["expected_transcript"] == "old raw"
    assert records[1]["expected_transcript"] == "existing"
    assert records[2]["expected_transcript"] is None


def test_manifest_rewrite_leaves_no_temporary_files(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, [{"id": "a", "audio_file": "a.wav"}])
    assert not list(tmp_path.glob(".manifest.jsonl.*.tmp"))
