import subprocess

from desktop.credential_store import (
    FallbackCredentialStore,
    MacOSKeychainCredentialStore,
    MemoryCredentialStore,
    PrivateFileCredentialStore,
)


class FailingCredentialStore:
    backend_name = "failing-keychain"

    def __init__(self):
        self.get_calls = 0
        self.set_calls = 0

    def get_password(self):
        self.get_calls += 1
        raise RuntimeError("钥匙串不可用")

    def set_password(self, password):
        self.set_calls += 1
        raise RuntimeError("钥匙串不可用")

    def delete_password(self):
        raise RuntimeError("钥匙串不可用")


def test_memory_credential_store_round_trip_and_delete():
    store = MemoryCredentialStore("test-namespace")

    store.set_password("secret")
    assert store.get_password() == "secret"

    store.delete_password()
    assert store.get_password() == ""


def test_macos_keychain_prompts_with_matching_password_twice_without_command_argument(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("desktop.credential_store.subprocess.run", fake_run)

    MacOSKeychainCredentialStore().set_password("secret-value")

    args, kwargs = calls[0]
    assert "secret-value" not in args
    assert kwargs["input"] == "secret-value\nsecret-value\n"


def test_fallback_credential_store_uses_private_file_when_keychain_is_unavailable(tmp_path):
    credentials_path = tmp_path / "credentials.json"
    primary = FailingCredentialStore()
    store = FallbackCredentialStore(
        primary,
        PrivateFileCredentialStore(credentials_path),
    )

    store.set_password("secret-value")

    assert store.get_password() == "secret-value"
    assert credentials_path.stat().st_mode & 0o777 == 0o600
    assert "本地凭据文件" in store.warning
    assert primary.set_calls == 1
    assert primary.get_calls == 0
