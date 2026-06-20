import os
import importlib

from config import load_env_file


def test_load_env_file_sets_missing_environment_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_API_KEY=local_key",
                "LLM_MODEL=mimo-v2.5-pro",
                "EMPTY_LINE_AFTER=this",
                "",
                "# comment",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    load_env_file(env_file)

    assert os.environ["LLM_API_KEY"] == "local_key"
    assert os.environ["LLM_MODEL"] == "mimo-v2.5-pro"


def test_load_env_file_does_not_override_existing_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=local_key\n", encoding="utf-8")
    monkeypatch.setenv("LLM_API_KEY", "existing_key")

    load_env_file(env_file)

    assert os.environ["LLM_API_KEY"] == "existing_key"


def test_config_reads_ssl_verify_flag(monkeypatch):
    monkeypatch.setenv("LLM_SSL_VERIFY", "0")

    import config

    reloaded = importlib.reload(config)

    assert reloaded.LLM_SSL_VERIFY is False
