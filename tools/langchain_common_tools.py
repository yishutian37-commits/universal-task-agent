from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import ipaddress
import io
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx

from tools.search_tool import SearchTool


def _text_from_input(tool_input: Any, *keys: str) -> str:
    if isinstance(tool_input, str):
        return tool_input.strip()
    if isinstance(tool_input, dict):
        for key in keys:
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _current_user_input(text: str) -> str:
    matches = list(re.finditer(r"(?:^|\n)当前用户输入[:：]\s*", str(text or "")))
    if not matches:
        return str(text or "").strip()
    return str(text or "")[matches[-1].end() :].strip()


def _path_within_roots(path: Path, allowed_roots: list[Path]) -> bool:
    resolved = path.expanduser().resolve()
    for root in allowed_roots:
        root_resolved = root.expanduser().resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


def _normalize_allowed_roots(allowed_roots: list[Path | str] | None) -> list[Path]:
    roots = [Path(root).expanduser().resolve() for root in (allowed_roots or [])]
    return roots or [Path.cwd().resolve()]


class CalculatorLangChainTool:
    name = "langchain_calculator_tool"
    description = "安全计算器工具，只支持基础数学表达式。"

    _binary_ops = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.FloorDiv: lambda left, right: left // right,
        ast.Mod: lambda left, right: left % right,
        ast.Pow: lambda left, right: left**right,
    }
    _unary_ops = {
        ast.UAdd: lambda value: value,
        ast.USub: lambda value: -value,
    }
    _allowed_names = {
        "pi": math.pi,
        "e": math.e,
    }
    _allowed_calls = {
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        expression = _text_from_input(tool_input, "expression", "query").strip()
        expression = self._expression_from_text(expression)
        if not expression:
            raise ValueError("缺少计算表达式")

        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval_node(tree.body)
        except Exception as exc:
            raise ValueError(f"不支持的计算表达式：{expression}") from exc

        return {"expression": expression, "result": result}

    def _expression_from_text(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^(请|帮我|请帮我)?(计算|算一下|算一算)", "", cleaned).strip()
        cleaned = re.sub(r"(等于多少|结果是多少|是多少)[？?]?$", "", cleaned).strip()
        return cleaned.strip(" ：:，,。")

    def _eval_node(self, node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._binary_ops:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self._binary_ops[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary_ops:
            return self._unary_ops[type(node.op)](self._eval_node(node.operand))
        if isinstance(node, ast.Name) and node.id in self._allowed_names:
            return self._allowed_names[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self._allowed_calls:
            args = [self._eval_node(arg) for arg in node.args]
            return self._allowed_calls[node.func.id](*args)
        raise ValueError("unsupported node")


class DateTimeLangChainTool:
    name = "langchain_datetime_tool"
    description = "日期时间工具，返回指定时区的当前日期和时间。"

    def __init__(self, now_provider=None) -> None:
        self.now_provider = now_provider

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        timezone = _text_from_input(tool_input, "timezone") or "Asia/Shanghai"
        try:
            zone = ZoneInfo(timezone)
        except Exception as exc:
            raise ValueError(f"不支持的时区：{timezone}") from exc

        now = self.now_provider(timezone) if self.now_provider is not None else datetime.now(zone)
        if now.tzinfo is None:
            now = now.replace(tzinfo=zone)
        now = now.astimezone(zone)
        return {
            "timezone": timezone,
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timestamp": int(now.timestamp()),
        }


class JsonLangChainTool:
    name = "langchain_json_tool"
    description = "JSON 解析、格式化和简单字段提取工具。"

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        json_text = _text_from_input(tool_input, "json_text", "query")
        json_text = self._json_text_from_text(json_text)
        path = _text_from_input(tool_input, "path").lstrip("$.")
        try:
            parsed = json.loads(json_text)
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

        result = {
            "valid": True,
            "parsed": parsed,
            "pretty": json.dumps(parsed, ensure_ascii=False, indent=2),
        }
        if path:
            result["path"] = path
            result["value"] = self._extract_path(parsed, path)
        return result

    def _json_text_from_text(self, text: str) -> str:
        stripped = text.strip()
        starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
        if not starts:
            return stripped
        return stripped[min(starts) :]

    def _extract_path(self, parsed: Any, path: str) -> Any:
        current = parsed
        for part in path.split("."):
            if isinstance(current, dict):
                current = current[part]
            elif isinstance(current, list):
                current = current[int(part)]
            else:
                raise KeyError(part)
        return current


class HttpGetLangChainTool:
    name = "langchain_http_get_tool"
    description = "安全只读 HTTP GET 工具，拒绝访问本机和内网地址。"

    def __init__(
        self,
        http_client=None,
        timeout: int = 10,
        max_chars: int = 4000,
        hostname_resolver=None,
        max_redirects: int = 5,
    ) -> None:
        self.http_client = http_client
        self.timeout = timeout
        self.max_chars = max_chars
        self.hostname_resolver = hostname_resolver or self._resolve_hostname
        self.max_redirects = max(0, int(max_redirects))

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        url = _text_from_input(tool_input, "url", "query")
        url = self._url_from_text(url)
        current_url = url
        for redirect_count in range(self.max_redirects + 1):
            resolved_addresses = self._validate_url(current_url)
            response = self._request_once(current_url, resolved_addresses)
            status_code = int(response.status_code)
            if status_code not in {301, 302, 303, 307, 308}:
                break
            location = self._header_value(getattr(response, "headers", {}), "location")
            if not location:
                break
            if redirect_count >= self.max_redirects:
                raise ValueError("HTTP 重定向次数过多")
            current_url = urljoin(current_url, location)
        text = str(response.text or "")
        truncated = len(text) > self.max_chars
        return {
            "url": current_url,
            "status_code": int(response.status_code),
            "content_type": dict(getattr(response, "headers", {}) or {}).get("content-type", ""),
            "text": text[: self.max_chars],
            "truncated": truncated,
        }

    def _url_from_text(self, text: str) -> str:
        match = re.search(r"https?://[^\s，。！？；：、\"'“”‘’<>]+", text)
        return match.group(0) if match else text.strip()

    def _validate_url(self, url: str) -> list[str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("只支持 http/https URL")
        if not parsed.hostname:
            raise ValueError("URL 缺少主机名")
        if parsed.username or parsed.password:
            raise ValueError("URL 不允许包含用户凭据")
        if self._is_blocked_host(parsed.hostname):
            raise ValueError("不允许访问本机或内网地址")
        if self._is_ip_literal(parsed.hostname):
            return [parsed.hostname]
        try:
            addresses = self.hostname_resolver(parsed.hostname)
        except OSError as exc:
            raise ValueError(f"无法解析 URL 主机名：{parsed.hostname}") from exc
        if not addresses or any(self._is_blocked_host(str(address)) for address in addresses):
            raise ValueError("不允许访问本机或内网地址")
        return [str(address) for address in addresses]

    def _request_once(self, url: str, resolved_addresses: list[str]):
        if self.http_client is not None:
            return self.http_client.get(url, timeout=self.timeout, follow_redirects=False)
        pinned_url, headers, extensions = self._pinned_request_args(url, resolved_addresses[0])
        with httpx.Client(trust_env=False) as client:
            return client.request(
                "GET",
                pinned_url,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=False,
                extensions=extensions,
            )

    def _pinned_request_args(self, url: str, address: str) -> tuple[str, dict[str, str], dict[str, str]]:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        pinned_host = f"[{address}]" if ":" in address else address
        pinned_netloc = f"{pinned_host}:{parsed.port}" if parsed.port is not None else pinned_host
        pinned_url = urlunparse(parsed._replace(netloc=pinned_netloc))
        host_header = f"{host}:{parsed.port}" if parsed.port is not None else host
        return pinned_url, {"Host": host_header}, {"sni_hostname": host}

    def _is_ip_literal(self, hostname: str) -> bool:
        try:
            ipaddress.ip_address(hostname.strip().lower().rstrip("."))
        except ValueError:
            return False
        return True

    def _resolve_hostname(self, hostname: str) -> list[str]:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        return list(dict.fromkeys(str(record[4][0]) for record in records))

    def _header_value(self, headers: Any, name: str) -> str:
        for key, value in dict(headers or {}).items():
            if str(key).lower() == name.lower():
                return str(value)
        return ""

    def _is_blocked_host(self, hostname: str) -> bool:
        normalized = hostname.strip().lower().rstrip(".")
        if normalized in {"localhost", "0.0.0.0"} or normalized.endswith(".local"):
            return True
        try:
            ip = ipaddress.ip_address(normalized)
        except ValueError:
            return False
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )


class SearchLangChainTool:
    name = "langchain_search_tool"
    description = "LangChain 风格搜索工具，复用 UTA 现有搜索提供方。"

    def __init__(self, search_tool: SearchTool | None = None) -> None:
        self.search_tool = search_tool if search_tool is not None else SearchTool()

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        query = _text_from_input(tool_input, "query", "user_input")
        if not query:
            raise ValueError("缺少搜索关键词")
        return self.search_tool.run("search", {"query": query, "max_results": 5})


class WeatherLangChainTool:
    name = "langchain_weather_tool"
    description = "LangChain 风格天气工具，复用 UTA 现有天气查询能力。"

    def __init__(self, search_tool: SearchTool | None = None) -> None:
        self.search_tool = search_tool if search_tool is not None else SearchTool()

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        city = _text_from_input(tool_input, "city", "query") or "北京"
        query = city if "天气" in city else f"{city} 天气"
        return self.search_tool.run("search", {"query": query, "max_results": 5})


class ShellLangChainTool:
    name = "langchain_shell_tool"
    description = "需要手动授权的 Shell 命令工具。"

    _dangerous_patterns = (
        r"\bsudo\b",
        r"\brm\s+-[^;&|]*r[^;&|]*f",
        r"\brm\s+-[^;&|]*f[^;&|]*r",
        r"\bchmod\s+-R\b",
        r"\bchown\s+-R\b",
        r"\bcurl\b.*\|\s*(sh|bash)",
        r"\bwget\b.*\|\s*(sh|bash)",
        r"\bosascript\b",
        r"\bopen\b",
        r">\s*/dev/",
    )
    _allowed_executables = {
        "cat",
        "cp",
        "df",
        "du",
        "echo",
        "git",
        "grep",
        "head",
        "ls",
        "mkdir",
        "printf",
        "pwd",
        "rg",
        "sort",
        "stat",
        "tail",
        "touch",
        "uniq",
        "wc",
        "which",
    }
    _control_tokens = {"|", "||", "&&", ";", ">", ">>", "<", "<<", "&"}

    def __init__(
        self,
        authorization_manager=None,
        enabled: bool = False,
        allowed_roots: list[Path | str] | None = None,
        command_runner=None,
        timeout: int = 10,
        max_output_chars: int = 4000,
        authorization_timeout: float | None = 120,
    ) -> None:
        self.authorization_manager = authorization_manager
        self.enabled = enabled
        self.allowed_roots = _normalize_allowed_roots(allowed_roots)
        self.command_runner = command_runner or self._run_command
        self.timeout = timeout
        self.max_output_chars = max_output_chars
        self.authorization_timeout = authorization_timeout

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("高风险工具未启用")
        command = self._command_from_input(tool_input)
        cwd = self._cwd_from_input(tool_input)
        self._validate_path(cwd)
        self._validate_command(command, cwd)
        decision = self._request_authorization(
            {
                "tool_name": self.name,
                "risk_level": "high",
                "summary": f"执行 Shell 命令：{command}",
                "command": command,
                "cwd": str(cwd),
                "impact": "将在本机执行终端命令",
            }
        )
        result = self.command_runner(command, str(cwd), self.timeout)
        stdout = str(getattr(result, "stdout", "") or "")
        stderr = str(getattr(result, "stderr", "") or "")
        return {
            "command": command,
            "cwd": str(cwd),
            "returncode": int(getattr(result, "returncode", 0)),
            "stdout": stdout[: self.max_output_chars],
            "stderr": stderr[: self.max_output_chars],
            "truncated": len(stdout) > self.max_output_chars or len(stderr) > self.max_output_chars,
            "authorized_by": decision.approved_by,
        }

    def _command_from_input(self, tool_input: Any) -> str:
        command = _text_from_input(tool_input, "command", "query")
        command = re.sub(r"^(请|帮我|请帮我)?(执行|运行)?\s*(shell|终端)?\s*(命令)?[:：]?", "", command, flags=re.IGNORECASE).strip()
        if not command:
            raise ValueError("缺少 Shell 命令")
        return command

    def _cwd_from_input(self, tool_input: Any) -> Path:
        cwd_text = _text_from_input(tool_input, "cwd", "working_directory")
        return Path(cwd_text).expanduser().resolve() if cwd_text else self.allowed_roots[0]

    def _validate_command(self, command: str, cwd: Path) -> None:
        lowered = command.lower()
        for pattern in self._dangerous_patterns:
            if re.search(pattern, lowered):
                raise ValueError("禁止执行高风险命令")
        if "$(" in command or "`" in command:
            raise ValueError("不支持 Shell 控制符")
        try:
            args = shlex.split(command)
        except ValueError as exc:
            raise ValueError("Shell 命令格式无效") from exc
        if not args:
            raise ValueError("缺少 Shell 命令")
        if any(token in self._control_tokens for token in args):
            raise ValueError("不支持 Shell 控制符")
        executable = Path(args[0]).name.lower()
        if executable not in self._allowed_executables:
            raise ValueError(f"不支持的 Shell 命令：{executable}")
        for token in args[1:]:
            candidate = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
            if candidate.startswith("-"):
                continue
            if candidate in {".", ".."} or "/" in candidate or candidate.startswith("~"):
                path = Path(candidate).expanduser()
                resolved = path.resolve() if path.is_absolute() else (cwd / path).resolve()
                self._validate_path(resolved)

    def _validate_path(self, path: Path) -> None:
        if not _path_within_roots(path, self.allowed_roots):
            raise ValueError("不允许访问授权目录之外")

    def _request_authorization(self, operation: dict[str, Any]):
        if self.authorization_manager is None:
            raise PermissionError("缺少授权管理器")
        decision = self.authorization_manager.request(operation, timeout=self.authorization_timeout)
        if not decision.approved:
            raise PermissionError(decision.reason or "用户未授权")
        return decision

    def _run_command(self, command: str, cwd: str, timeout: int):
        return subprocess.run(
            shlex.split(command),
            cwd=cwd,
            timeout=timeout,
            shell=False,
            capture_output=True,
            text=True,
        )


class DirectoryCreateLangChainTool:
    name = "langchain_directory_create_tool"
    description = "需要手动授权的目录创建工具。"

    def __init__(
        self,
        authorization_manager=None,
        enabled: bool = False,
        allowed_roots: list[Path | str] | None = None,
        desktop_root: Path | str | None = None,
        authorization_timeout: float | None = 120,
    ) -> None:
        self.authorization_manager = authorization_manager
        self.enabled = enabled
        self.allowed_roots = _normalize_allowed_roots(allowed_roots)
        self.workspace_root = self.allowed_roots[0]
        self.desktop_root = (
            Path(desktop_root).expanduser().resolve()
            if desktop_root is not None
            else (Path.home() / "Desktop").resolve()
        )
        self.authorization_timeout = authorization_timeout

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("高风险工具未启用")
        path = Path(self._path_from_input(tool_input)).expanduser().resolve()
        self._validate_target(path)
        if path.exists():
            if path.is_dir():
                return {"path": str(path), "created": False, "already_exists": True}
            raise FileExistsError("目标路径已存在且不是目录")
        decision = self._request_authorization(
            {
                "tool_name": self.name,
                "risk_level": "high",
                "summary": f"创建目录：{path}",
                "path": str(path),
                "impact": "将在本机创建目录",
            }
        )
        path.mkdir(parents=True, exist_ok=False)
        return {
            "path": str(path),
            "created": True,
            "already_exists": False,
            "authorized_by": decision.approved_by,
        }

    def _path_from_input(self, tool_input: Any) -> str:
        path_text = _text_from_input(tool_input, "path", "target_path")
        if path_text:
            return path_text
        query = _current_user_input(_text_from_input(tool_input, "query"))
        desktop_match = re.search(
            r"(?:在)?桌面(?:上)?(?:创建|新建)(?:一个)?(?:名为|名叫|名字叫|叫)?\s*[‘’“”\"']?(.+?)[‘’“”\"']?(?:的)?(?:文件夹|目录)",
            query,
        )
        if desktop_match:
            name = desktop_match.group(1).strip().strip("‘’“”\"'")
            self._validate_name(name)
            return str(self.desktop_root / name)
        workspace_match = re.search(
            r"(?:在(?:当前)?(?:工作区|工作文件夹|项目目录|这个文件夹)(?:中|里|内)?)?"
            r"(?:创建|新建)(?:一个)?(?:名为|名叫|名字叫|叫)?\s*[‘’“”\"']?"
            r"(.+?)[‘’“”\"']?(?:的)?(?:文件夹|目录)",
            query,
        )
        if workspace_match:
            name = workspace_match.group(1).strip().strip("‘’“”\"'")
            self._validate_name(name)
            return str(self.workspace_root / name)
        explicit_match = re.search(r"(?:创建|新建)(?:文件夹|目录)\s+(\S+)", query)
        if explicit_match:
            return explicit_match.group(1)
        mkdir_match = re.search(r"\bmkdir(?:\s+-p)?\s+(\S+)", query)
        if mkdir_match:
            return mkdir_match.group(1)
        raise ValueError("缺少目录路径或目录名称")

    def _validate_name(self, name: str) -> None:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError("目录名称无效")

    def _validate_target(self, path: Path) -> None:
        if not _path_within_roots(path, self.allowed_roots):
            raise ValueError("不允许访问授权目录之外")
        if any(path == root.expanduser().resolve() for root in self.allowed_roots):
            raise ValueError("不能把授权根目录作为新目录")
        if ".git" in path.parts:
            raise ValueError("禁止在 .git 内创建目录")

    def _request_authorization(self, operation: dict[str, Any]):
        if self.authorization_manager is None:
            raise PermissionError("缺少授权管理器")
        decision = self.authorization_manager.request(operation, timeout=self.authorization_timeout)
        if not decision.approved:
            raise PermissionError(decision.reason or "用户未授权")
        return decision


class FileWriteLangChainTool:
    name = "langchain_file_write_tool"
    description = "需要手动授权的文件写入工具。"

    def __init__(
        self,
        authorization_manager=None,
        enabled: bool = False,
        allowed_roots: list[Path | str] | None = None,
        authorization_timeout: float | None = 120,
    ) -> None:
        self.authorization_manager = authorization_manager
        self.enabled = enabled
        self.allowed_roots = _normalize_allowed_roots(allowed_roots)
        self.authorization_timeout = authorization_timeout

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("高风险工具未启用")
        path_text, content = self._path_and_content_from_input(tool_input)
        path = Path(path_text).expanduser().resolve()
        mode = (_text_from_input(tool_input, "mode") or "create").lower()
        if mode not in {"create", "overwrite", "append"}:
            raise ValueError("写入模式只支持 create/overwrite/append")
        if not _path_within_roots(path, self.allowed_roots):
            raise ValueError("不允许访问授权目录之外")
        if mode == "create" and path.exists():
            raise FileExistsError("文件已存在")

        decision = self._request_authorization(
            {
                "tool_name": self.name,
                "risk_level": "high",
                "summary": f"写入文件：{path}",
                "path": str(path),
                "mode": mode,
                "content_preview": content[:500],
                "impact": "将在本机创建或修改文件",
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            with path.open("a", encoding="utf-8") as handle:
                written = handle.write(content)
        else:
            with path.open("w", encoding="utf-8") as handle:
                written = handle.write(content)
        return {
            "path": str(path),
            "mode": mode,
            "bytes_written": len(content.encode("utf-8")),
            "characters_written": written,
            "authorized_by": decision.approved_by,
        }

    def _path_and_content_from_input(self, tool_input: Any) -> tuple[str, str]:
        path_text = _text_from_input(tool_input, "path", "target_path")
        content = _text_from_input(tool_input, "content", "text")
        if path_text:
            return path_text, content

        query = _text_from_input(tool_input, "query")
        match = re.search(r"(?:写入文件|创建文件|覆盖文件|追加文件)\s+(\S+)\s+内容\s+(.+)", query, flags=re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        raise ValueError("缺少文件路径")

    def _request_authorization(self, operation: dict[str, Any]):
        if self.authorization_manager is None:
            raise PermissionError("缺少授权管理器")
        decision = self.authorization_manager.request(operation, timeout=self.authorization_timeout)
        if not decision.approved:
            raise PermissionError(decision.reason or "用户未授权")
        return decision


class PythonReplLangChainTool:
    name = "langchain_python_repl_tool"
    description = "需要手动授权的受限 Python REPL 工具。"

    _allowed_imports = {
        "collections",
        "datetime",
        "decimal",
        "fractions",
        "itertools",
        "json",
        "math",
        "re",
        "statistics",
    }
    _forbidden_imports = {
        "builtins",
        "ctypes",
        "importlib",
        "multiprocessing",
        "os",
        "pathlib",
        "shutil",
        "socket",
        "subprocess",
        "sys",
        "threading",
    }
    _forbidden_calls = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "globals",
        "input",
        "locals",
        "open",
        "vars",
    }

    def __init__(
        self,
        authorization_manager=None,
        enabled: bool = False,
        allowed_roots: list[Path | str] | None = None,
        authorization_timeout: float | None = 120,
        max_output_chars: int = 4000,
    ) -> None:
        self.authorization_manager = authorization_manager
        self.enabled = enabled
        self.allowed_roots = _normalize_allowed_roots(allowed_roots)
        self.authorization_timeout = authorization_timeout
        self.max_output_chars = max_output_chars

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("高风险工具未启用")
        code = _text_from_input(tool_input, "code", "query")
        code = self._code_from_text(code)
        if not code:
            raise ValueError("缺少 Python 代码")
        self._validate_code(code)
        decision = self._request_authorization(
            {
                "tool_name": self.name,
                "risk_level": "high",
                "summary": "执行 Python REPL 代码",
                "code": code,
                "impact": "将在受限 Python 环境中执行代码",
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        namespace: dict[str, Any] = {"__builtins__": self._safe_builtins()}
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(code, namespace, namespace)
        except Exception as exc:
            raise RuntimeError(f"Python REPL 执行失败：{exc}") from exc

        output = stdout.getvalue()
        error_output = stderr.getvalue()
        return {
            "stdout": output[: self.max_output_chars],
            "stderr": error_output[: self.max_output_chars],
            "result_repr": repr(namespace["result"]) if "result" in namespace else "",
            "truncated": len(output) > self.max_output_chars or len(error_output) > self.max_output_chars,
            "authorized_by": decision.approved_by,
        }

    def _code_from_text(self, text: str) -> str:
        return re.sub(
            r"^(请|帮我|请帮我)?(运行|执行)?\s*(python|Python)?\s*(代码|repl|REPL)?[:：]?",
            "",
            text.strip(),
        ).strip()

    def _validate_code(self, code: str) -> None:
        tree = ast.parse(code, mode="exec")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name.split(".", 1)[0] for alias in node.names]
                elif node.module:
                    modules = [node.module.split(".", 1)[0]]
                for module in modules:
                    if module in self._forbidden_imports or module not in self._allowed_imports:
                        raise ValueError("禁止导入高风险模块")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self._forbidden_calls:
                    raise ValueError("禁止调用高风险函数")
                if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("__"):
                    raise ValueError("禁止访问高风险属性")
            elif isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError("禁止访问高风险名称")
            elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise ValueError("禁止访问高风险属性")
            elif isinstance(node, ast.While):
                raise ValueError("禁止执行可能无限循环的语句")

    def _safe_builtins(self) -> dict[str, Any]:
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".", 1)[0]
            if root not in self._allowed_imports:
                raise ImportError(f"禁止导入模块：{name}")
            return __import__(name, globals, locals, fromlist, level)

        return {
            "__import__": safe_import,
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        }

    def _request_authorization(self, operation: dict[str, Any]):
        if self.authorization_manager is None:
            raise PermissionError("缺少授权管理器")
        decision = self.authorization_manager.request(operation, timeout=self.authorization_timeout)
        if not decision.approved:
            raise PermissionError(decision.reason or "用户未授权")
        return decision


class FileDeleteLangChainTool:
    name = "langchain_file_delete_tool"
    description = "需要手动授权的文件删除工具，实际移动到 UTA 回收站。"

    def __init__(
        self,
        authorization_manager=None,
        enabled: bool = False,
        allowed_roots: list[Path | str] | None = None,
        trash_root: Path | str | None = None,
        authorization_timeout: float | None = 120,
    ) -> None:
        self.authorization_manager = authorization_manager
        self.enabled = enabled
        self.allowed_roots = _normalize_allowed_roots(allowed_roots)
        self.trash_root = Path(trash_root).expanduser().resolve() if trash_root is not None else Path.home() / ".uta" / "trash"
        self.authorization_timeout = authorization_timeout

    def invoke(self, tool_input: Any) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("高风险工具未启用")
        path = Path(self._path_from_input(tool_input)).expanduser().resolve()
        self._validate_target(path)
        trash_path = self._trash_path_for(path)
        decision = self._request_authorization(
            {
                "tool_name": self.name,
                "risk_level": "high",
                "summary": f"移动到回收站：{path}",
                "path": str(path),
                "trash_path": str(trash_path),
                "impact": "不会永久删除，将移动到 UTA 回收站",
            }
        )
        trash_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(trash_path))
        return {
            "path": str(path),
            "trash_path": str(trash_path),
            "mode": "move_to_trash",
            "authorized_by": decision.approved_by,
        }

    def _path_from_input(self, tool_input: Any) -> str:
        path_text = _text_from_input(tool_input, "path", "target_path")
        if path_text:
            return path_text
        query = _text_from_input(tool_input, "query")
        match = re.search(r"(?:删除文件|删除目录|删除本地文件|移除文件|移除目录|移除本地文件)\s+(\S+)", query)
        if match:
            return match.group(1)
        raise ValueError("缺少删除路径")

    def _validate_target(self, path: Path) -> None:
        if not _path_within_roots(path, self.allowed_roots):
            raise ValueError("不允许访问授权目录之外")
        for root in self.allowed_roots:
            if path == root.expanduser().resolve():
                raise ValueError("禁止删除授权根目录")
        if ".git" in path.parts:
            raise ValueError("禁止删除 .git")
        if not path.exists():
            raise FileNotFoundError("文件不存在")

    def _trash_path_for(self, path: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return self.trash_root / f"{stamp}_{path.name}"

    def _request_authorization(self, operation: dict[str, Any]):
        if self.authorization_manager is None:
            raise PermissionError("缺少授权管理器")
        decision = self.authorization_manager.request(operation, timeout=self.authorization_timeout)
        if not decision.approved:
            raise PermissionError(decision.reason or "用户未授权")
        return decision


def build_common_langchain_tools(search_tool: SearchTool | None = None) -> tuple:
    return (
        CalculatorLangChainTool(),
        DateTimeLangChainTool(),
        HttpGetLangChainTool(),
        SearchLangChainTool(search_tool),
        WeatherLangChainTool(search_tool),
        JsonLangChainTool(),
    )
