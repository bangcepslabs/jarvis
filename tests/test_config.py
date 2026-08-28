from app.core.config import Settings
from pathlib import Path


def test_data_dir_provides_default_database_location() -> None:
    settings = Settings(_env_file=None, JARVIS_DATA_DIR="/srv/jarvis/data")
    assert settings.memory_database_path == str(Path("/srv/jarvis/data") / "jarvis.db")


def test_explicit_database_path_wins_over_data_dir() -> None:
    settings = Settings(_env_file=None, JARVIS_DATA_DIR="/srv/jarvis/data", JARVIS_DB_PATH="/backup/jarvis.db")
    assert settings.memory_database_path == "/backup/jarvis.db"
