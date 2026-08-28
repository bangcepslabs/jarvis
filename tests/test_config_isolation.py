from app.core.config import Settings


def test_explicit_process_environment_has_priority_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("JARVIS_AUTH_ENABLED=true\nLLM_PROVIDER=openai\n", encoding="utf-8")
    monkeypatch.setenv("JARVIS_AUTH_ENABLED", "false")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    settings = Settings(_env_file=env_file)
    assert settings.auth_enabled is False
    assert settings.llm_provider == "mock"
