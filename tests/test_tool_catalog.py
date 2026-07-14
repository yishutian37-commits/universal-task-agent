import json

from core.tool_catalog import build_tool_catalog
from tools.base_tool import BaseTool


class _DummyTool(BaseTool):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class _MultiActionTool(BaseTool):
    name = "document_tool"
    description = "Read or list documents"
    default_action = "read"
    action_contracts = {
        "read": {
            "parameter_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        "list": {"parameter_schema": {"type": "object"}},
    }


def test_tool_catalog_only_contains_registered_tools_and_runtime_metadata():
    registry = {
        "file_tool": _DummyTool("file_tool", "Read files from the current workspace."),
        "langchain_file_delete_tool": _DummyTool(
            "langchain_file_delete_tool",
            "Delete an authorized file.",
        ),
    }

    catalog = build_tool_catalog(registry)

    assert [item["name"] for item in catalog] == [
        "file_tool",
        "langchain_file_delete_tool",
    ]
    assert catalog[0]["default_action"] == "read"
    assert catalog[0]["requires_authorization"] is False
    assert catalog[0]["actions"] == [
        {
            "name": "read",
            "parameter_schema": {"type": "object"},
            "requires_authorization": False,
        }
    ]
    assert catalog[1]["default_action"] == "invoke"
    assert catalog[1]["requires_authorization"] is True
    assert catalog[1]["actions"][0]["requires_authorization"] is True
    json.dumps(catalog, ensure_ascii=False)


def test_tool_catalog_uses_registry_key_when_tool_name_is_empty():
    registry = {"custom_tool": _DummyTool("", "Custom capability")}

    catalog = build_tool_catalog(registry)

    assert catalog == [
        {
            "name": "custom_tool",
            "description": "Custom capability",
            "default_action": "run",
            "requires_authorization": False,
            "actions": [
                {
                    "name": "run",
                    "parameter_schema": {"type": "object"},
                    "requires_authorization": False,
                }
            ],
        }
    ]


def test_tool_catalog_exposes_explicit_action_contracts():
    catalog = build_tool_catalog({"document_tool": _MultiActionTool()})

    assert catalog[0]["default_action"] == "read"
    assert [item["name"] for item in catalog[0]["actions"]] == ["read", "list"]
    assert catalog[0]["actions"][0]["parameter_schema"]["required"] == ["path"]
    assert catalog[0]["actions"][0]["requires_authorization"] is False
