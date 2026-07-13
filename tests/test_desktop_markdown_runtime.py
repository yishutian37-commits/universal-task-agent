from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_node(source: str) -> None:
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(source)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_markdown_renderer_renders_tables_instead_of_pipe_source() -> None:
    run_node(
        r"""
        const assert = require("node:assert/strict");
        const { renderMarkdown } = require("./desktop/frontend/markdown.js");
        const html = renderMarkdown(`| 模块 | 职责 |
| --- | --- |
| 检索 | 找到相关片段 |
| 生成 | 组织最终回答 |`);

        assert.match(html, /<table>/);
        assert.match(html, /<thead><tr><th>模块<\/th><th>职责<\/th><\/tr><\/thead>/);
        assert.match(html, /<tbody><tr><td>检索<\/td><td>找到相关片段<\/td><\/tr>/);
        assert.doesNotMatch(html, /\| --- \|/);
        """
    )


def test_markdown_renderer_renders_fenced_code_without_exposing_fences() -> None:
    run_node(
        r"""
        const assert = require("node:assert/strict");
        const { renderMarkdown } = require("./desktop/frontend/markdown.js");
        const html = renderMarkdown(`\`\`\`python
def retrieve(query):
    return chunks[0] < limit
\`\`\``);

        assert.match(html, /<pre class="markdownCode"><code data-language="python">/);
        assert.match(html, /def retrieve\(query\):/);
        assert.match(html, /chunks\[0\] &lt; limit/);
        assert.doesNotMatch(html, /\`\`\`/);
        """
    )


def test_markdown_renderer_handles_quotes_rules_and_common_inline_markup() -> None:
    run_node(
        r"""
        const assert = require("node:assert/strict");
        const { renderMarkdown } = require("./desktop/frontend/markdown.js");
        const html = renderMarkdown(`> 先检索，再生成。

---

**重点**、*说明*、~~旧内容~~、[文档](https://example.com/docs)。`);

        assert.match(html, /<blockquote><p>先检索，再生成。<\/p><\/blockquote>/);
        assert.match(html, /<hr>/);
        assert.match(html, /<strong>重点<\/strong>/);
        assert.match(html, /<em>说明<\/em>/);
        assert.match(html, /<del>旧内容<\/del>/);
        assert.match(html, /<a href="https:\/\/example.com\/docs" target="_blank" rel="noopener noreferrer">文档<\/a>/);
        """
    )


def test_markdown_renderer_escapes_raw_html_and_unsafe_links() -> None:
    run_node(
        r"""
        const assert = require("node:assert/strict");
        const { renderMarkdown } = require("./desktop/frontend/markdown.js");
        const html = renderMarkdown(`<img src=x onerror=alert(1)>

[危险](javascript:alert(1))`);

        assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
        assert.doesNotMatch(html, /<img/);
        assert.doesNotMatch(html, /href="javascript:/);
        assert.match(html, /\[危险\]\(javascript:alert\(1\)\)/);
        """
    )
