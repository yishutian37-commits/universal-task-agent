from pathlib import Path


def test_architecture_html_exists_and_has_required_structure():
    html_path = Path("docs/uta-architecture.html")
    assert html_path.exists(), "architecture html should exist"
    content = html_path.read_text(encoding="utf-8")
    assert "cytoscape" in content.lower()
    assert 'id="cy"' in content
    assert 'id="toolbar"' in content
    assert 'id="details-panel"' in content
    assert "整体模块" in content
    assert "执行链路" in content
    assert "桌面端交互" in content
    assert "数据流转" in content


def test_architecture_html_has_render_view_function():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    assert "function renderView" in content
    assert "var cy = cytoscape" in content or "let cy = cytoscape" in content or "const cy = cytoscape" in content
    assert '"overview"' in content
    assert '"agentLoop"' in content
    assert '"desktop"' in content
    assert '"dataFlow"' in content


def test_architecture_html_has_detail_functions_and_styles():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    assert "function showNodeDetails" in content
    assert "function showEdgeDetails" in content
    assert "details-panel" in content
    assert "background-color" in content
    assert "shape" in content


def test_overview_view_has_key_nodes():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    required_ids = ["user", "main", "api_server", "desktop_api", "core", "tools", "memory", "rag", "llm", "search_providers", "weather_providers", "skills", "desktop", "outputs"]
    for nid in required_ids:
        assert f'id: "{nid}"' in content, f"missing node {nid}"


def test_agent_loop_view_has_flow():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    required = ["user_input", "task_parser", "skill_loader", "planner", "agent_loop", "router", "executor", "verifier", "reflection", "memory_writer", "final_output"]
    for nid in required:
        assert f'id: "{nid}"' in content, f"missing agent loop node {nid}"


def test_desktop_view_has_components():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    required = ["desktop_frontend", "desktop_api", "desktop_runner", "chat_router", "conversation_store", "desktop_memory", "desktop_rag", "core", "dist_app"]
    for nid in required:
        assert f'id: "{nid}"' in content, f"missing desktop node {nid}"


def test_data_flow_view_has_storage_nodes():
    content = Path("docs/uta-architecture.html").read_text(encoding="utf-8")
    required = ["agent_state", "state_files", "log_files", "task_history", "lessons", "negative_rules", "skill_candidates", "user_profile", "documents", "chunker", "embedder", "sqlite_store", "retrieval", "generation", "desktop_data"]
    for nid in required:
        assert f'id: "{nid}"' in content, f"missing data flow node {nid}"
