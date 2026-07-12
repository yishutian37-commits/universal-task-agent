import subprocess

from desktop.credential_store import MacOSKeychainCredentialStore, MemoryCredentialStore


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
