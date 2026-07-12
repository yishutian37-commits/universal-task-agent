from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterable, Iterator
from typing import Any, Callable

import certifi
import httpx


class LLMClientError(RuntimeError):
    pass


Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]
StreamTransport = Callable[[str, dict[str, str], dict[str, Any], int], Iterable[str]]


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int = 30,
        transport: Transport | None = None,
        fallback_transport: Transport | None = None,
        stream_transport: StreamTransport | None = None,
        ssl_verify: bool = True,
        use_curl_fallback: bool = False,
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = self._normalize_endpoint(base_url)
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self.use_curl_fallback = use_curl_fallback
        self.transport = transport or self._default_transport
        self.stream_transport = stream_transport or self._default_stream_transport
        self.fallback_transport = fallback_transport or (
            self._curl_transport if use_curl_fallback else None
        )

    @classmethod
    def from_config(cls, use_curl_fallback: bool = True) -> "LLMClient":
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_SSL_VERIFY

        return cls(
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            ssl_verify=LLM_SSL_VERIFY,
            use_curl_fallback=use_curl_fallback,
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
            if self.fallback_transport is None or not self._should_try_curl_fallback(exc):
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

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
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
            "stream": True,
        }
        emitted = False
        try:
            for chunk in self.stream_transport(self.endpoint, headers, payload, self.timeout):
                text = str(chunk or "")
                if not text:
                    continue
                emitted = True
                yield text
        except LLMClientError as exc:
            if emitted or self.fallback_transport is None or not self._should_try_curl_fallback(exc):
                raise
            yield self.chat(system_prompt, user_prompt)

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
        verify: str | bool = certifi.where() if self.ssl_verify else False
        try:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise LLMClientError(f"LLM network error: {exc}") from exc

        try:
            parsed = response.json()
        except ValueError as exc:
            raise LLMClientError(f"Invalid LLM HTTP JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError("Invalid LLM HTTP JSON: expected object")
        return parsed

    def _default_stream_transport(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> Iterator[str]:
        verify: str | bool = certifi.where() if self.ssl_verify else False
        try:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        chunk = self._parse_stream_line(line)
                        if chunk:
                            yield chunk
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise LLMClientError(f"LLM network error: {exc}") from exc

    @staticmethod
    def _parse_stream_line(line: str | bytes) -> str | None:
        text = line.decode("utf-8") if isinstance(line, bytes) else str(line or "")
        text = text.strip()
        if not text or text.startswith(":"):
            return None
        if text.startswith("data:"):
            text = text[5:].strip()
        if text == "[DONE]":
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid LLM stream JSON: {exc}") from exc
        if not isinstance(payload, dict):
            return None
        if isinstance(payload.get("error"), dict):
            raise LLMClientError(f"LLM stream error: {payload['error'].get('message') or payload['error']}")
        try:
            choice = payload["choices"][0]
        except (KeyError, IndexError, TypeError):
            return None
        delta = choice.get("delta") if isinstance(choice, dict) else None
        if isinstance(delta, dict) and delta.get("content") is not None:
            return str(delta.get("content") or "")
        message = choice.get("message") if isinstance(choice, dict) else None
        if isinstance(message, dict) and message.get("content") is not None:
            return str(message.get("content") or "")
        return None

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
