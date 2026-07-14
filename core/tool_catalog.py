from __future__ import annotations

from typing import Any, Mapping

from tools.base_tool import BaseTool


DANGEROUS_TOOL_NAMES = frozenset(
    {
        "langchain_shell_tool",
        "langchain_file_write_tool",
        "langchain_python_repl_tool",
        "langchain_file_delete_tool",
        "langchain_directory_create_tool",
    }
)

DEFAULT_ACTIONS = {
    "code_tool": "scan",
    "file_tool": "read",
    "geo_tool": "analyze",
    "history_tool": "list",
    "text_tool": "process",
    "table_tool": "analyze",
    "report_tool": "generate",
    "search_tool": "search",
}

DEFAULT_PARAMETER_SCHEMA = {"type": "object"}


def get_action_contract(
    catalog_item: Mapping[str, Any] | None,
    action_name: str | None,
) -> dict[str, Any] | None:
    """Return a normalized action contract, including legacy catalog entries."""
    if not isinstance(catalog_item, Mapping):
        return None
    effective_name = str(action_name or catalog_item.get("default_action") or "")
    actions = catalog_item.get("actions")
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, Mapping) and str(action.get("name") or "") == effective_name:
                return dict(action)
        return None
    if effective_name != str(catalog_item.get("default_action") or ""):
        return None
    return {
        "name": effective_name,
        "parameter_schema": dict(DEFAULT_PARAMETER_SCHEMA),
        "requires_authorization": bool(catalog_item.get("requires_authorization")),
    }


def validate_action_params(schema: Mapping[str, Any] | None, params: Any) -> bool:
    """Validate the small JSON-Schema subset used by runtime tool contracts."""
    if not isinstance(schema, Mapping):
        return isinstance(params, dict)
    return _matches_schema(params, schema)


def _matches_schema(value: Any, schema: Mapping[str, Any]) -> bool:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        return any(_matches_schema(value, {**schema, "type": item}) for item in expected_type)
    if expected_type == "object":
        if not isinstance(value, dict):
            return False
        required = schema.get("required") or []
        if not isinstance(required, list) or any(key not in value for key in required):
            return False
        properties = schema.get("properties") or {}
        if not isinstance(properties, Mapping):
            return False
        if schema.get("additionalProperties") is False and any(key not in properties for key in value):
            return False
        return all(
            key not in value
            or not isinstance(property_schema, Mapping)
            or _matches_schema(value[key], property_schema)
            for key, property_schema in properties.items()
        )
    if expected_type == "array":
        if not isinstance(value, list):
            return False
        item_schema = schema.get("items")
        return not isinstance(item_schema, Mapping) or all(
            _matches_schema(item, item_schema) for item in value
        )
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def build_tool_catalog(registry: Mapping[str, BaseTool]) -> list[dict[str, Any]]:
    """从当前真实注册表生成可供 Planner/Router 使用的工具目录。"""
    catalog: list[dict[str, Any]] = []
    for registry_name, tool in registry.items():
        # Executor 以 registry key 查找工具，目录也必须使用同一个运行时标识。
        name = str(registry_name)
        declared_action = tool.__class__.__dict__.get("default_action")
        default_action = str(
            declared_action
            or DEFAULT_ACTIONS.get(name)
            or ("invoke" if name.startswith("langchain_") else "run")
        )
        tool_requires_authorization = bool(
            getattr(tool, "requires_authorization", False) or name in DANGEROUS_TOOL_NAMES
        )
        declared_contracts = getattr(tool, "action_contracts", None)
        actions: list[dict[str, Any]] = []
        if isinstance(declared_contracts, Mapping) and declared_contracts:
            for action_name, raw_contract in declared_contracts.items():
                contract = raw_contract if isinstance(raw_contract, Mapping) else {}
                schema = contract.get("parameter_schema")
                actions.append(
                    {
                        "name": str(action_name),
                        "parameter_schema": (
                            dict(schema)
                            if isinstance(schema, Mapping)
                            else dict(DEFAULT_PARAMETER_SCHEMA)
                        ),
                        "requires_authorization": bool(
                            tool_requires_authorization
                            or contract.get("requires_authorization", False)
                        ),
                    }
                )
            if default_action not in {item["name"] for item in actions}:
                default_action = actions[0]["name"]
        else:
            actions.append(
                {
                    "name": default_action,
                    "parameter_schema": dict(DEFAULT_PARAMETER_SCHEMA),
                    "requires_authorization": tool_requires_authorization,
                }
            )
        requires_authorization = any(item["requires_authorization"] for item in actions)
        catalog.append(
            {
                "name": name,
                "description": str(getattr(tool, "description", "") or ""),
                "default_action": default_action,
                "requires_authorization": requires_authorization,
                "actions": actions,
            }
        )
    return catalog
