from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_frontend_has_skill_pack_view():
    index_html = (ROOT / "desktop/frontend/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "desktop/frontend/app.js").read_text(encoding="utf-8")

    assert 'id="openSkills"' in index_html
    assert 'id="skillsView"' in index_html
    assert 'id="runtimeSkillList"' in index_html
    assert 'id="vendorSkillPackList"' in index_html
    assert "get_skill_overview" in app_js
