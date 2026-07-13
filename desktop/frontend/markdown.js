(function initMarkdownRenderer(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UTAMarkdown = api;
  }
})(typeof window !== "undefined" ? window : globalThis, function createMarkdownRenderer() {
  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function safeHref(value) {
    const href = String(value || "").trim();
    if (/^(https?:\/\/|mailto:|#|\/|\.\.?\/)/i.test(href)) {
      return href;
    }
    return "";
  }

  function tokenizeLinks(value, tokens) {
    let output = "";
    let cursor = 0;

    while (cursor < value.length) {
      const labelStart = value.indexOf("[", cursor);
      if (labelStart < 0) {
        output += value.slice(cursor);
        break;
      }
      const labelEnd = value.indexOf("](", labelStart + 1);
      if (labelEnd < 0) {
        output += value.slice(cursor);
        break;
      }

      let depth = 1;
      let targetEnd = labelEnd + 2;
      for (; targetEnd < value.length; targetEnd += 1) {
        const char = value[targetEnd];
        if (char === "\\") {
          targetEnd += 1;
          continue;
        }
        if (char === "(") depth += 1;
        if (char === ")") {
          depth -= 1;
          if (depth === 0) break;
        }
      }

      if (depth !== 0) {
        output += value.slice(cursor);
        break;
      }

      const label = value.slice(labelStart + 1, labelEnd);
      const target = value.slice(labelEnd + 2, targetEnd).trim();
      const href = safeHref(target);
      output += value.slice(cursor, labelStart);
      if (!href) {
        output += value.slice(labelStart, targetEnd + 1);
      } else {
        const token = `\uE000${tokens.length}\uE001`;
        tokens.push(
          `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`,
        );
        output += token;
      }
      cursor = targetEnd + 1;
    }

    return output;
  }

  function renderInlineMarkdown(value) {
    const tokens = [];
    let source = String(value || "").replace(/`([^`\n]+)`/g, (_match, code) => {
      const token = `\uE000${tokens.length}\uE001`;
      tokens.push(`<code>${escapeHtml(code)}</code>`);
      return token;
    });
    source = tokenizeLinks(source, tokens);

    let html = escapeHtml(source)
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
      .replace(/~~([^~\n]+)~~/g, "<del>$1</del>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");

    return html.replace(/\uE000(\d+)\uE001/g, (_match, index) => tokens[Number(index)] || "");
  }

  function splitTableRow(line) {
    let source = String(line || "").trim();
    if (source.startsWith("|")) source = source.slice(1);
    if (source.endsWith("|")) source = source.slice(0, -1);

    const cells = [];
    let cell = "";
    for (let index = 0; index < source.length; index += 1) {
      const char = source[index];
      if (char === "\\" && source[index + 1] === "|") {
        cell += "|";
        index += 1;
      } else if (char === "|") {
        cells.push(cell.trim());
        cell = "";
      } else {
        cell += char;
      }
    }
    cells.push(cell.trim());
    return cells;
  }

  function tableAlignments(line) {
    const cells = splitTableRow(line);
    if (cells.length < 2 || cells.some((cell) => !/^:?-{3,}:?$/.test(cell))) {
      return null;
    }
    return cells.map((cell) => {
      if (cell.startsWith(":") && cell.endsWith(":")) return "center";
      if (cell.endsWith(":")) return "right";
      return "left";
    });
  }

  function tableCell(tag, value, alignment) {
    const alignClass = alignment && alignment !== "left" ? ` class="align-${alignment}"` : "";
    return `<${tag}${alignClass}>${renderInlineMarkdown(value)}</${tag}>`;
  }

  function renderTable(lines, startIndex) {
    const headers = splitTableRow(lines[startIndex]);
    const alignments = tableAlignments(lines[startIndex + 1]);
    let index = startIndex + 2;
    const rows = [];

    while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
      const cells = splitTableRow(lines[index]);
      while (cells.length < headers.length) cells.push("");
      rows.push(cells.slice(0, headers.length));
      index += 1;
    }

    const head = headers.map((cell, cellIndex) => tableCell("th", cell, alignments[cellIndex])).join("");
    const body = rows
      .map((row) => `<tr>${row.map((cell, cellIndex) => tableCell("td", cell, alignments[cellIndex])).join("")}</tr>`)
      .join("");
    return {
      html: `<div class="markdownTableWrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      nextIndex: index,
    };
  }

  function fenceMatch(line) {
    return String(line || "").match(/^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+.-]*)\s*$/);
  }

  function isHorizontalRule(line) {
    const compact = String(line || "").trim().replace(/\s+/g, "");
    return /^(\*{3,}|-{3,}|_{3,})$/.test(compact);
  }

  function listMatch(line) {
    const unordered = String(line || "").match(/^\s*[-+*]\s+(.+)$/);
    if (unordered) return { type: "ul", content: unordered[1], start: null };
    const ordered = String(line || "").match(/^\s*(\d+)[.)、]\s+(.+)$/);
    if (ordered) return { type: "ol", content: ordered[2], start: Number(ordered[1]) };
    return null;
  }

  function isBlockStart(lines, index) {
    const line = lines[index] || "";
    if (!line.trim()) return true;
    if (fenceMatch(line) || /^\s{0,3}#{1,6}\s+/.test(line)) return true;
    if (/^\s*>/.test(line) || listMatch(line) || isHorizontalRule(line)) return true;
    return Boolean(index + 1 < lines.length && line.includes("|") && tableAlignments(lines[index + 1]));
  }

  function renderListItem(content) {
    const task = String(content || "").match(/^\[([ xX])\]\s+(.+)$/);
    if (!task) return `<li>${renderInlineMarkdown(content)}</li>`;
    const checked = task[1].toLowerCase() === "x" ? " checked" : "";
    return `<li class="taskListItem"><input type="checkbox" disabled${checked}><span>${renderInlineMarkdown(task[2])}</span></li>`;
  }

  function renderMarkdown(text) {
    if (!text) return "<p>无输出</p>";
    const lines = String(text).replace(/\r\n?/g, "\n").split("\n");
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
        continue;
      }

      const fence = fenceMatch(line);
      if (fence) {
        const marker = fence[1][0];
        const minimumLength = fence[1].length;
        const language = fence[2] || "";
        const code = [];
        index += 1;
        while (index < lines.length) {
          const closing = lines[index].match(/^\s*(`{3,}|~{3,})\s*$/);
          if (closing && closing[1][0] === marker && closing[1].length >= minimumLength) {
            index += 1;
            break;
          }
          code.push(lines[index]);
          index += 1;
        }
        const languageAttribute = language ? ` data-language="${escapeHtml(language)}"` : "";
        blocks.push(`<pre class="markdownCode"><code${languageAttribute}>${escapeHtml(code.join("\n"))}</code></pre>`);
        continue;
      }

      if (index + 1 < lines.length && line.includes("|") && tableAlignments(lines[index + 1])) {
        const table = renderTable(lines, index);
        blocks.push(table.html);
        index = table.nextIndex;
        continue;
      }

      const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
      if (heading) {
        const level = heading[1].length;
        blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
        index += 1;
        continue;
      }

      if (isHorizontalRule(line)) {
        blocks.push("<hr>");
        index += 1;
        continue;
      }

      if (/^\s*>/.test(line)) {
        const quoteLines = [];
        while (index < lines.length) {
          const quote = lines[index].match(/^\s*>\s?(.*)$/);
          if (!quote) break;
          quoteLines.push(quote[1]);
          index += 1;
        }
        blocks.push(`<blockquote>${renderMarkdown(quoteLines.join("\n"))}</blockquote>`);
        continue;
      }

      const firstListItem = listMatch(line);
      if (firstListItem) {
        const items = [];
        const type = firstListItem.type;
        const start = firstListItem.start;
        while (index < lines.length) {
          const item = listMatch(lines[index]);
          if (!item || item.type !== type) break;
          items.push(renderListItem(item.content));
          index += 1;
        }
        const startAttribute = type === "ol" && start !== 1 ? ` start="${start}"` : "";
        blocks.push(`<${type}${startAttribute}>${items.join("")}</${type}>`);
        continue;
      }

      const paragraphLines = [];
      while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
        paragraphLines.push(lines[index].trim());
        index += 1;
      }
      if (!paragraphLines.length) {
        paragraphLines.push(line.trim());
        index += 1;
      }
      const paragraph = paragraphLines
        .map((part) => ({ text: part.replace(/\s{2,}$/, ""), hardBreak: /\s{2,}$/.test(part) }))
        .map((part, partIndex) => `${renderInlineMarkdown(part.text)}${part.hardBreak && partIndex < paragraphLines.length - 1 ? "<br>" : ""}`)
        .join(" ");
      blocks.push(`<p>${paragraph}</p>`);
    }

    return blocks.join("");
  }

  return { escapeHtml, renderInlineMarkdown, renderMarkdown };
});
