from __future__ import annotations

import json
import re
import shutil
import ssl
import subprocess
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError


class LLMClientError(RuntimeError):
    pass


Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int = 30,
        transport: Transport | None = None,
        fallback_transport: Transport | None = None,
        ssl_verify: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = self._normalize_endpoint(base_url)
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self.transport = transport or self._default_transport
        self.fallback_transport = fallback_transport or self._curl_transport

    @classmethod
    def from_config(cls) -> "LLMClient":
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_SSL_VERIFY

        return cls(
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            ssl_verify=LLM_SSL_VERIFY,
        )

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise LLMClientError("LLM_API_KEY is required")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }

        try:
            response = self.transport(self.endpoint, headers, payload, self.timeout)
        except LLMClientError as exc:
            if not self._should_try_curl_fallback(exc):
                raise
            response = self.fallback_transport(self.endpoint, headers, payload, self.timeout)

        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Invalid LLM response: {exc}") from exc

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del schema
        content = self.chat(system_prompt, user_prompt)
        json_text = self._extract_json_text(content)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid JSON from LLM: {exc}") from exc

        if not isinstance(parsed, dict):
            raise LLMClientError("Invalid JSON from LLM: expected object")
        return parsed

    @staticmethod
    def _normalize_endpoint(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"

    @staticmethod
    def _extract_json_text(content: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content.strip()

    def _default_transport(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(endpoint, data=data, headers=headers, method="POST")
        context = self._ssl_context()
        try:
            with request.urlopen(req, timeout=timeout, context=context) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"LLM HTTP error {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LLMClientError(f"LLM network error: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid LLM HTTP JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError("Invalid LLM HTTP JSON: expected object")
        return parsed

    def _curl_transport(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        curl_path = shutil.which("curl")
        if curl_path is None:
            raise LLMClientError("curl is not available for LLM HTTPS fallback")

        body = json.dumps(payload, ensure_ascii=False)
        config = self._curl_config(endpoint, headers, body, timeout)
        try:
            completed = subprocess.run(
                [curl_path, "--config", "-"],
                input=config,
                text=True,
                capture_output=True,
                timeout=timeout + 5,
            )
        except subprocess.TimeoutExpired as exc:
            raise LLMClientError(f"LLM curl fallback timed out after {timeout} seconds") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise LLMClientError(f"LLM curl fallback failed: {detail}")

        response_body, status_code = self._split_curl_response(completed.stdout)
        if status_code >= 400:
            raise LLMClientError(f"LLM HTTP error {status_code}: {response_body}")

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid LLM HTTP JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError("Invalid LLM HTTP JSON: expected object")
        return parsed

    def _curl_config(
        self,
        endpoint: str,
        headers: dict[str, str],
        body: str,
        timeout: int,
    ) -> str:
        lines = [
            "silent",
            "show-error",
            "location",
            "http1.1",
            "request = POST",
            f"max-time = {timeout}",
            "url = " + self._curl_config_value(endpoint),
        ]
        for name, value in headers.items():
            lines.append("header = " + self._curl_config_value(f"{name}: {value}"))
        lines.extend(
            [
                "data-raw = " + self._curl_config_value(body),
                "write-out = " + self._curl_config_value("\n%{http_code}"),
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _curl_config_value(value: str) -> str:
        escaped = (
            str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return f'"{escaped}"'

    @staticmethod
    def _split_curl_response(output: str) -> tuple[str, int]:
        body, separator, status_text = output.rpartition("\n")
        if not separator or not status_text.isdigit():
            raise LLMClientError("Invalid LLM curl fallback response: missing HTTP status")
        return body, int(status_text)

    @staticmethod
    def _should_try_curl_fallback(exc: LLMClientError) -> bool:
        message = str(exc)
        return "UNEXPECTED_EOF_WHILE_READING" in message or "EOF occurred in violation" in message

    def _ssl_context(self):
        if not self.ssl_verify:
            return ssl._create_unverified_context()

        try:
            import certifi
        except ImportError:
            return None

        return ssl.create_default_context(cafile=certifi.where())
