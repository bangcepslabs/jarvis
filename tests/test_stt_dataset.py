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
    assert json.loads(manifest.read_text().splitlines()[0])["expected_transcript"] == "hello"
    output = tmp_path / "dataset.json"
    monkeypatch.setattr("sys.argv", ["stt_dataset", "export", "--manifest", str(manifest), "--output", str(output)])
    assert stt_dataset.main() == 0
    assert json.loads(output.read_text())[0]["expected"] == "hello"
