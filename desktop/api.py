from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from desktop.chat_router import chat_route_kind, direct_chat_response
from desktop.conversation_store import ConversationStore
from desktop.history_store import HistoryStore
from desktop.memory_compression import estimate_tokens, parse_compression_result
from desktop.memory_store import MemoryStore
from desktop.paths import resource_path, uta_home
from desktop.rag_client import RAGClient
from desktop.runner import TaskRunner
from desktop.settings_store import SettingsStore
from desktop.skill_store import SkillStore


class DesktopAPI:
    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        runner: TaskRunner | None = None,
        history_store: HistoryStore | None = None,
        memory_store: MemoryStore | None = None,
        rag_client: RAGClient | None = None,
        skill_store: SkillStore | None = None,
        conversation_store: ConversationStore | None = None,
        chat_client=None,
        skills_root=None,
    ):
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.runner = runner if runner is not None else TaskRunner(settings_store=self.settings_store)
        self.history_store = history_store if history_store is not None else HistoryStore(uta_home() / "outputs")
        self.memory_store = memory_store if memory_store is not None else MemoryStore(uta_home() / "memory")
        self.rag_client = rag_client if rag_client is not None else RAGClient()
        self.skill_store = skill_store if skill_store is not None else SkillStore(skills_root or resource_path("skills"))
        self.conversation_store = (
            conversation_store if conversation_store is not None else ConversationStore(uta_home() / "conversations")
        )
        self.chat_client = chat_client

    def bind_window(self, window) -> None:
        if hasattr(self.runner, "bind_window"):
            self.runner.bind_window(window)

    def get_settings(self) -> dict[str, Any]:
        return self.settings_store.public_settings()

    def save_settings(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            self.settings_store.save(payload or {})
            self.settings_store.apply_to_environment()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def load_example(self, category: str = "summarize") -> dict[str, Any]:
        if category in {"summarize", "summary"}:
            example_path = resource_path("examples", "summarize_example.txt")
            content = example_path.read_text(encoding="utf-8") if example_path.exists() else ""
            return {
                "ok": True,
                "title": "文本总结示例",
                "input": f"帮我总结一段文本：{content}".strip(),
            }

        if category in {"data", "table", "data_analysis"}:
            table_path = resource_path("examples", "orders.csv")
            return {
                "ok": True,
                "title": "表格分析示例",
                "input": f"分析 {table_path}，输出字段说明、基础统计、异常数据、分类汇总和后续建议。",
            }

        return {"ok": False, "error": f"未知示例类型：{category}"}

    def run_task(self, user_input: str) -> dict[str, Any]:
        text = str(user_input or "").strip()
        if not text:
            return {"ok": False, "error": "请输入任务内容"}

        if not self.settings_store.public_settings()["has_api_key"]:
            return {"ok": False, "error": "请先配置 API Key"}

        try:
            task_id = self.runner.start(text)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "task_id": task_id}

    def list_runs(self) -> dict[str, Any]:
        try:
            return self.history_store.list_runs()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_run(self, task_id: str) -> dict[str, Any]:
        try:
            return self.history_store.get_run(str(task_id or ""))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_memory_overview(self) -> dict[str, Any]:
        try:
            return self.memory_store.overview()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_skill_overview(self) -> dict[str, Any]:
        try:
            return self.skill_store.overview()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_result(self, task_id: str) -> dict[str, Any]:
        return self.runner.get_result(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self.runner.cancel(task_id)

    # ---- 对话 ----

    def list_conversations(self) -> dict[str, Any]:
        try:
            return self.conversation_store.list_conversations()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def new_conversation(self) -> dict[str, Any]:
        try:
            return self.conversation_store.new_conversation()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        try:
            return self.conversation_store.get_conversation(str(conversation_id or ""))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def compress_conversation(self, conversation_id: str) -> dict[str, Any]:
        if not self.settings_store.public_settings()["has_api_key"]:
            return {"ok": False, "error": "请先配置 API Key"}

        try:
            loaded = self.conversation_store.get_conversation(str(conversation_id or ""))
            if not loaded.get("ok"):
                return loaded

            conversation = loaded["conversation"]
            messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
            short_term = dict(conversation.get("short_term") or {})
            compression = dict(conversation.get("compression") or {})
            start_index = int(short_term.get("compressed_until_index") or 0)
            pending_messages = messages[start_index:]
            if not pending_messages:
                return {
                    "ok": True,
                    "compressed": False,
                    "conversation_id": str(conversation_id or ""),
                    "message": "没有新的会话消息需要压缩",
                }

            self.settings_store.apply_to_environment()
            client = self.chat_client
            if client is None:
                from llm.llm_client import LLMClient

                client = LLMClient.from_config()

            raw_result = client.chat(
                _compression_system_prompt(),
                _compression_user_prompt(conversation, pending_messages),
            )
            parsed = parse_compression_result(raw_result)
            timestamp = datetime.now().isoformat(timespec="microseconds")
            token_estimate = estimate_tokens("\n".join(str(message.get("content") or "") for message in messages))
            candidates = _compression_candidates(parsed, pending_messages)
            merged = self.memory_store.merge_long_term_candidates(
                candidates,
                conversation_id=str(conversation_id or ""),
                now=timestamp,
            )
            if not merged.get("ok"):
                return merged

            short_term.update(
                {
                    "summary": parsed["short_term_summary"],
                    "compressed_until_index": len(messages),
                    "recent_message_limit": int(short_term.get("recent_message_limit") or 12),
                    "token_estimate": token_estimate,
                    "updated_at": timestamp,
                }
            )
            runs = compression.get("runs") if isinstance(compression.get("runs"), list) else []
            runs.append(
                {
                    "compressed_at": timestamp,
                    "from_index": start_index,
                    "to_index": len(messages),
                    "message_count": len(pending_messages),
                    "token_estimate": token_estimate,
                    "long_term_candidates": len(candidates),
                }
            )
            compression.update(
                {
                    "last_compressed_at": timestamp,
                    "last_trigger_tokens": token_estimate,
                    "runs": runs,
                }
            )
            updated = self.conversation_store.update_memory_state(
                str(conversation_id or ""),
                short_term=short_term,
                compression=compression,
            )
            if not updated.get("ok"):
                return updated

            return {
                "ok": True,
                "compressed": True,
                "conversation_id": str(conversation_id or ""),
                "compressed_until_index": len(messages),
                "short_term_summary": parsed["short_term_summary"],
                "long_term_candidates": len(candidates),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def run_chat_message(self, conversation_id: str, user_input: str) -> dict[str, Any]:
        text = str(user_input or "").strip()
        if not text:
            return {"ok": False, "error": "请输入消息内容"}

        direct_response = direct_chat_response(text)
        if direct_response is not None:
            try:
                conversation_id = self._ensure_conversation_id(conversation_id)
                self.conversation_store.append_message(conversation_id, role="user", content=text)
                self.conversation_store.append_message(
                    conversation_id,
                    role="assistant",
                    content=direct_response.content,
                    task_id=None,
                    status="completed",
                )
                return {
                    "ok": True,
                    "direct": True,
                    "category": direct_response.category,
                    "conversation_id": conversation_id,
                    "task_id": None,
                    "message": direct_response.content,
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        if chat_route_kind(text) == "chat":
            if not self.settings_store.public_settings()["has_api_key"]:
                return {"ok": False, "error": "普通聊天需要先配置 API Key"}
            try:
                conversation_id = self._ensure_conversation_id(conversation_id)
                answer = self._run_general_chat(text)
                self.conversation_store.append_message(conversation_id, role="user", content=text)
                self.conversation_store.append_message(
                    conversation_id,
                    role="assistant",
                    content=answer,
                    task_id=None,
                    status="completed",
                )
                return {
                    "ok": True,
                    "direct": True,
                    "category": "general_chat",
                    "conversation_id": conversation_id,
                    "task_id": None,
                    "message": answer,
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        if not self.settings_store.public_settings()["has_api_key"]:
            return {"ok": False, "error": "请先配置 API Key"}

        try:
            conversation_id = self._ensure_conversation_id(conversation_id)

            task_id = self.runner.start(text)
            self.conversation_store.append_message(conversation_id, role="user", content=text, task_id=task_id)
            self.conversation_store.append_message(
                conversation_id,
                role="assistant",
                content="正在处理...",
                task_id=task_id,
                status="running",
            )
            return {"ok": True, "conversation_id": conversation_id, "task_id": task_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _ensure_conversation_id(self, conversation_id: str) -> str:
        if conversation_id:
            loaded = self.conversation_store.get_conversation(str(conversation_id))
            if loaded.get("ok"):
                return str(conversation_id)
        created = self.conversation_store.new_conversation()
        return str(created["conversation"]["conversation_id"])

    def _run_general_chat(self, text: str) -> str:
        self.settings_store.apply_to_environment()
        client = self.chat_client
        if client is None:
            from llm.llm_client import LLMClient

            client = LLMClient.from_config()
        return client.chat(
            "你是 UTA Desktop 的本地对话助手。"
            "你服务于一个学习型 Agent 应用，回答要简洁、中文、可执行。"
            "如果用户提出明确任务，提醒用户可以直接发送任务让 Agent 拆解执行。",
            text,
        )

    def sync_chat_result(self, conversation_id: str, task_id: str) -> dict[str, Any]:
        try:
            result = self.runner.get_result(str(task_id or ""))
            status = str(result.get("status") or "unknown")
            if status == "running":
                return {"ok": True, "status": status}

            content = str(result.get("final_output") or result.get("error") or "未生成输出")
            updated = self.conversation_store.update_assistant_message(
                str(conversation_id or ""),
                task_id=str(task_id or ""),
                content=content,
                status=status,
            )
            if not updated.get("ok"):
                return updated
            return {"ok": True, "status": status, "conversation": updated["conversation"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ---- RAG 知识库 ----

    def rag_stats(self) -> dict[str, Any]:
        try:
            stats = self.rag_client.stats()
            return {"ok": True, "mode": self.rag_client.mode, "stats": stats}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rag_list_docs(self) -> dict[str, Any]:
        try:
            docs = self.rag_client.list_docs()
            return {"ok": True, "docs": docs}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rag_ingest(self, path: str) -> dict[str, Any]:
        try:
            result = self.rag_client.ingest(str(path or "").strip())
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rag_query(self, question: str, top_k: int = 5) -> dict[str, Any]:
        try:
            return self.rag_client.query(str(question or "").strip(), top_k=top_k)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rag_ask(self, question: str, top_k: int = 5) -> dict[str, Any]:
        try:
            return self.rag_client.ask(str(question or "").strip(), top_k=top_k)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rag_delete(self, target: str) -> dict[str, Any]:
        try:
            return self.rag_client.delete(str(target or "").strip())
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def _compression_system_prompt() -> str:
    return (
        "你是 UTA 的会话记忆压缩器。"
        "请提取当前会话中稳定、长期有用的信息。"
        "只输出 JSON，不要输出 Markdown、解释、代码块或多余文字。"
        "JSON 必须包含 short_term_summary、long_term_candidates、open_questions 三个字段。"
        "long_term_candidates 的 kind 只能是 identity、preference、work_habit、project、constraint、decision、open_question。"
    )


def _compression_user_prompt(conversation: dict[str, Any], pending_messages: list[dict[str, Any]]) -> str:
    payload = {
        "conversation_id": conversation.get("conversation_id"),
        "title": conversation.get("title"),
        "existing_short_term_summary": (conversation.get("short_term") or {}).get("summary", ""),
        "messages": [
            {
                "message_id": message.get("message_id"),
                "role": message.get("role"),
                "content": message.get("content"),
                "created_at": message.get("created_at"),
            }
            for message in pending_messages
        ],
        "required_schema": {
            "short_term_summary": "当前会话摘要",
            "long_term_candidates": [
                {
                    "kind": "preference",
                    "content": "用户要求使用中文回复。",
                    "confidence": 0.95,
                    "source_message_ids": ["msg_1"],
                }
            ],
            "open_questions": ["仍需确认的问题"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _compression_candidates(
    parsed: dict[str, Any],
    pending_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = list(parsed.get("long_term_candidates") or [])
    message_ids = [
        str(message.get("message_id") or "").strip()
        for message in pending_messages
        if str(message.get("message_id") or "").strip()
    ]
    for question in parsed.get("open_questions") or []:
        candidates.append(
            {
                "kind": "open_question",
                "content": str(question),
                "confidence": 0.7,
                "source_message_ids": message_ids,
            }
        )
    return candidates
