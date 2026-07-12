from desktop.credential_store import MemoryCredentialStore


def test_memory_credential_store_round_trip_and_delete():
    store = MemoryCredentialStore("test-namespace")

    store.set_password("secret")
    assert store.get_password() == "secret"

    store.delete_password()
    assert store.get_password() == ""
