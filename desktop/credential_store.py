from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


class MacOSKeychainCredentialStore:
    backend_name = "macos-keychain"

    def __init__(self, service: str = "com.uta.desktop.llm", account: str = "api-key") -> None:
        self.service = service
        self.account = account

    def get_password(self) -> str:
        result = self._run(
            ["find-generic-password", "-a", self.account, "-s", self.service, "-w"],
            allow_missing=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def set_password(self, password: str) -> None:
        value = str(password or "")
        if not value:
            self.delete_password()
            return
        self._run(
            ["add-generic-password", "-a", self.account, "-s", self.service, "-U", "-w"],
            input_text=f"{value}\n{value}\n",
        )

    def delete_password(self) -> None:
        self._run(
            ["delete-generic-password", "-a", self.account, "-s", self.service],
            allow_missing=True,
        )

    @staticmethod
    def _run(
        args: list[str],
        *,
        input_text: str | None = None,
        allow_missing: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["/usr/bin/security", *args],
            input=input_text,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0 and not (allow_missing and result.returncode == 44):
            message = result.stderr.strip() or result.stdout.strip() or "macOS 钥匙串操作失败"
            raise RuntimeError(message)
        return result


class PrivateFileCredentialStore:
    backend_name = "private-file"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def get_password(self) -> str:
        if not self.path.exists():
            return ""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ""
        return str(payload.get("llm_api_key") or "") if isinstance(payload, dict) else ""

    def set_password(self, password: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"llm_api_key": str(password or "")}), encoding="utf-8")
        self.path.chmod(0o600)

    def delete_password(self) -> None:
        if self.path.exists() and not self.path.is_symlink():
            self.path.unlink()


class MemoryCredentialStore:
    backend_name = "memory"
    _values: dict[str, str] = {}

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace

    def get_password(self) -> str:
        return self._values.get(self.namespace, "")

    def set_password(self, password: str) -> None:
        self._values[self.namespace] = str(password or "")

    def delete_password(self) -> None:
        self._values.pop(self.namespace, None)


def create_credential_store(config_path: Path):
    backend = os.getenv("UTA_CREDENTIAL_BACKEND", "").strip().lower()
    if backend == "memory":
        return MemoryCredentialStore(str(config_path.resolve()))
    if sys.platform == "darwin":
        return MacOSKeychainCredentialStore()
    return PrivateFileCredentialStore(config_path.with_name("credentials.json"))
