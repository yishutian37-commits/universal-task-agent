import json
import os

from desktop.settings_store import SettingsStore


def test_settings_store_saves_public_settings_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    store = SettingsStore()

    store.save(
        {
            "llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            "llm_model": "mimo-v2.5-pro",
            "llm_api_key": "secret-key",
            "llm_ssl_verify": False,
        }
    )

    saved = json.loads((tmp_path / "uta" / "config.json").read_text(encoding="utf-8"))
    public = store.public_settings()

    assert saved["llm_api_key"] == "secret-key"
    assert public["llm_base_url"] == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert public["llm_model"] == "mimo-v2.5-pro"
    assert public["llm_ssl_verify"] is False
    assert public["has_api_key"] is True
    assert public["memory_compression_enabled"] is True
    assert public["memory_context_window_tokens"] == 400_000
    assert public["memory_compression_trigger_ratio"] == 0.7
    assert public["memory_compression_cap_tokens"] == 250_000
    assert public["dangerous_tools_enabled"] is False
    assert public["desktop_access_enabled"] is False
    assert public["workspace_path"] == ""
    assert "llm_api_key" not in public


def test_settings_store_preserves_and_clears_existing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    store = SettingsStore()
    store.save({"llm_api_key": "secret-key"})

    store.save(
        {
            "llm_base_url": "https://example.test/v1",
            "llm_model": "new-model",
            "llm_api_key": "",
            "llm_ssl_verify": True,
        }
    )

    assert store.load()["llm_api_key"] == "secret-key"

    store.save({"clear_api_key": True})

    assert store.load()["llm_api_key"] == ""
    assert store.public_settings()["has_api_key"] is False


def test_settings_store_applies_values_to_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_SSL_VERIFY", raising=False)
    store = SettingsStore()
    store.save(
        {
            "llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            "llm_model": "mimo-v2.5-pro",
            "llm_api_key": "secret-key",
            "llm_ssl_verify": False,
        }
    )

    store.apply_to_environment()

    assert os.environ["LLM_API_KEY"] == "secret-key"
    assert os.environ["LLM_BASE_URL"] == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    assert os.environ["LLM_MODEL"] == "mimo-v2.5-pro"
    assert os.environ["LLM_SSL_VERIFY"] == "0"


def test_settings_store_saves_memory_compression_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    store = SettingsStore()

    store.save(
        {
            "memory_compression_enabled": False,
            "memory_context_window_tokens": 32_000,
            "memory_compression_trigger_ratio": 0.5,
            "memory_compression_cap_tokens": 12_000,
        }
    )

    settings = store.public_settings()

    assert settings["memory_compression_enabled"] is False
    assert settings["memory_context_window_tokens"] == 32_000
    assert settings["memory_compression_trigger_ratio"] == 0.5
    assert settings["memory_compression_cap_tokens"] == 12_000


def test_settings_store_saves_dangerous_tools_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    store = SettingsStore()

    store.save({"dangerous_tools_enabled": True})

    assert store.load()["dangerous_tools_enabled"] is True
    assert store.public_settings()["dangerous_tools_enabled"] is True


def test_settings_store_saves_desktop_access_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    store = SettingsStore()

    store.save({"desktop_access_enabled": True})

    assert store.load()["desktop_access_enabled"] is True
    assert store.public_settings()["desktop_access_enabled"] is True


def test_settings_store_saves_and_exposes_existing_workspace_path(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SettingsStore()

    store.save({"workspace_path": str(workspace)})

    assert store.load()["workspace_path"] == str(workspace.resolve())
    assert store.public_settings()["workspace_path"] == str(workspace.resolve())


def test_settings_store_drops_workspace_path_that_no_longer_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    config_path = tmp_path / "uta" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"workspace_path": str(tmp_path / "missing")}), encoding="utf-8")

    settings = SettingsStore().load()

    assert settings["workspace_path"] == ""
