# Task 2: 清理根目录重复设计文档

**Files:**
- Delete: `mqmhzojl-2026-06-20-desktop-app-design.md`, `mqmi5wkc-2026-06-20-desktop-app-design.md`, `mqmid6ez-2026-06-20-desktop-app-design.md`
- Keep: 如需归档，保留一份到 `docs/superpowers/designs/desktop-app-design.md`

**Interfaces:**
- 无代码接口变更。

- [ ] **Step 1: 检查三份文件是否确实相同**

Run:
```bash
diff -q mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md
diff -q mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
```
Expected: 无输出（表示相同）。

- [ ] **Step 2: 归档一份到 docs**

```bash
mkdir -p docs/superpowers/designs
cp mqmhzojl-2026-06-20-desktop-app-design.md docs/superpowers/designs/desktop-app-design.md
```

- [ ] **Step 3: 删除根目录三份重复文件**

```bash
rm mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
```

- [ ] **Step 4: 确认 git status**

Run: `git status --short`
Expected: 显示 `D` 删除三文件，`A` 新增归档文件。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/designs/desktop-app-design.md mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
git commit -m "chore: deduplicate and archive desktop design docs"
```
