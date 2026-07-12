from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                json.dump({"llm_api_key": str(password or "")}, handle)
                temp_path = Path(handle.name)
            temp_path.chmod(0o600)
            temp_path.replace(self.path)
            self.path.chmod(0o600)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

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


class FallbackCredentialStore:
    backend_name = "macos-keychain-with-private-file-fallback"

    def __init__(self, primary, fallback: PrivateFileCredentialStore) -> None:
        self.primary = primary
        self.fallback = fallback
        self.warning = ""
        self._primary_unavailable = False

    def get_password(self) -> str:
        if self._primary_unavailable:
            return self.fallback.get_password()
        try:
            primary_password = str(self.primary.get_password() or "")
        except Exception as exc:
            self._primary_unavailable = True
            self.warning = self._fallback_warning(exc)
            return self.fallback.get_password()

        if primary_password:
            self.fallback.delete_password()
            self.warning = ""
            return primary_password

        fallback_password = self.fallback.get_password()
        if fallback_password:
            self.warning = "macOS 钥匙串中没有可用凭据，当前使用仅本人可读写的本地凭据文件。"
            return fallback_password

        self.warning = ""
        return ""

    def set_password(self, password: str) -> None:
        if self._primary_unavailable:
            self.fallback.set_password(password)
            return
        try:
            self.primary.set_password(password)
        except Exception as exc:
            self._primary_unavailable = True
            self.fallback.set_password(password)
            self.warning = self._fallback_warning(exc)
            return

        self.fallback.delete_password()
        self.warning = ""

    def delete_password(self) -> None:
        primary_error = None
        if not self._primary_unavailable:
            try:
                self.primary.delete_password()
            except Exception as exc:
                self._primary_unavailable = True
                primary_error = exc
        self.fallback.delete_password()
        self.warning = self._fallback_warning(primary_error) if primary_error else ""

    @staticmethod
    def _fallback_warning(exc: Exception) -> str:
        return f"macOS 钥匙串暂时不可用，API Key 已改存仅本人可读写的本地凭据文件：{exc}"


def create_credential_store(config_path: Path):
    backend = os.getenv("UTA_CREDENTIAL_BACKEND", "").strip().lower()
    if backend == "memory":
        return MemoryCredentialStore(str(config_path.resolve()))
    if sys.platform == "darwin":
        return FallbackCredentialStore(
            MacOSKeychainCredentialStore(),
            PrivateFileCredentialStore(config_path.with_name("credentials.json")),
        )
    return PrivateFileCredentialStore(config_path.with_name("credentials.json"))
