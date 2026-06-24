---
name: geo-copywriting
description: Use when generating GEO content planning briefs (title candidates + writing guidance) from question matrix. Outputs briefs, not full articles. Use when the user specifies N platforms × M templates for batch brief generation.
---

# GEO 内容规划Brief生成

这是当前项目的 P0 主技能。它从问题矩阵出发，生成内容规划brief（标题推荐 + 完整行文指南），供写手执行。不生成完整文章正文。

## 硬约束

1. 平台规则优先于通用写作习惯。
2. 已确认事实优先于模型推断。
3. 输出必须是内容规划brief，不是完整文章。brief是行文规划文档，包含标题候选、平台规则速查、行文结构、风格要点、事实引用和合规清单，不含正文。
4. 每份brief必须显式绑定问题矩阵中的一个问题，标注问题原文、层级和公式。
5. 经验技能和记忆库只能影响表达方式，不能新增事实。

## 工作流（问题矩阵 → Brief）

```
Step 1: 读取问题矩阵
  → 从 geo-content-optimization 输出的问题矩阵中获取全部问题
  → 每个问题包含：question、layer、intent、formula、keyword_breakdown、
    evidence_support、recommended_platforms、business_value、content_actionability

Step 2: 用户指定平台×模板组合
  → 用户手动选择 N个平台 × M个文章模板
  → 不自动选择，等待用户明确指定

Step 3: 匹配问题到平台×模板
  → 根据问题的 recommended_platforms 匹配用户指定的平台
  → 根据问题的 layer 和 intent 匹配文章模板：
    - 入池层 pool_layer → 推荐指南(recommendation) / 品牌介绍(brand_intro)
    - 验证层 verification_layer → FAQ问答(faq) / 产品详解(product)
    - 权重层 authority_layer → 对比分析(comparison) / 案例深度(case_study)
    - 转化层 conversion_layer → 购买指南(ranking) / 教程(tutorial)
  → 从矩阵中选取最匹配的问题作为该brief的目标问题

Step 4: 生成Brief
  → 按下方Brief输出模板，逐模块填充
  → 行文结构基于匹配的文章模板展开
  → 平台规则速查基于 platform-adaptation-rules.md 填充
  → 事实引用从问题矩阵的 evidence_support 字段和品牌事实库中提取

Step 5: 合规预检
  → 调用 platform-compliance-check 的5步检查序列
  → 结果写入brief末尾的合规检查清单
```

## 当前项目输入

- **问题矩阵**（必须，上游输入）。
- 从矩阵中选定的目标问题。
- 用户指定的平台×模板组合。
- 品牌事实库。
- 项目知识资产。
- 平台规则。
- 写作记忆和经验技能。

## Brief输出模板

每份brief使用如下结构：

```markdown
## [平台名] × [模板名]（[对应层级名]）

### 目标问题
[问题矩阵中的原始问题文本]
- 层级：[pool_layer / verification_layer / authority_layer / conversion_layer]
- 公式：[问题公式，如"地域+品类+推荐"]
- 意图：[如"本地推荐""价格比较""口碑验证"]

### 标题候选（3选1）
1. **[标题A]** — [风格说明，为什么适合该平台]
2. **[标题B]** — [风格说明]
3. **[标题C]** — [风格说明]

### 平台规则速查
- 字数：[平台字数范围]
- 引流策略：[该平台的引流规则]
- AIGC标识：[是/否，及具体要求]
- 核心禁忌：
  1. [禁忌1]
  2. [禁忌2]
  3. [禁忌3]

### 行文结构（基于[模板名]模板）

\```
[结构箭头图：段落流转关系]
\```

**首段要求：** [首段写法指引，不超过多少字，如何切入]

**段落组织：**
- 第1段（约XX字）：[段落主题和写法指引]
- 第2段（约XX字）：[段落主题和写法指引]
- ...（逐段展开，每段标注字数、主题、关键写法）

**收尾要求：** [收尾写法指引]

### 行文风格要点
1. **[风格要点1]**：[具体说明]
2. **[风格要点2]**：[具体说明]
3. **[风格要点3]**：[具体说明]

### 必须引用的事实
- fact_01：[事实描述]
- fact_02：[事实描述]
- ...（列出本brief要求撰稿时引用的已确认事实）

### 合规预检
按 platform-compliance-check 的5步检查顺序（通用红线 → 平台规则 → 行业风险 → 事实风险 → AIGC标识）：
- **通用红线：** [✅/⚠️/❌] [说明]
- **平台规则：** [✅/⚠️/❌] [说明]
- **行业风险：** [✅/⚠️/❌] [说明]
- **事实风险：** [✅/⚠️/❌] [说明]
- **AIGC标识：** [✅/⚠️/❌] [说明]
- 风险等级：**[低/中/高]**
```

## 批量输出格式

用户指定 N平台 × M模板时，输出 N×M 份brief，前后附汇总：

```markdown
# 内容规划Brief — [品牌名] × [N]平台[M]模板

> 生成日期：[日期]
> 执行技能：geo-copywriting（P0）
> 合规预检：platform-compliance-check 5步序列
> 品牌主体：[品牌全称]

---

[brief 1]
---
[brief 2]
---
[brief N×M]

---

## 汇总

| 维度 | 结果 |
|------|------|
| Brief总数 | N×M |
| 平台覆盖 | [列出] |
| 模板覆盖 | [列出] |
| 层级覆盖 | [列出] |
| 合规检查 | [通过/不通过数量] |
| 风险等级 | [汇总] |
```

## 平台适配

读取 `references/platform-adaptation-rules.md`。若当前项目已有更细的平台规则（如 platform-publishing-guide），以项目规则为准。

## 常见错误

- Brief没有绑定问题矩阵中的问题，凭空编造目标问题。
- 输出了完整文章正文而非brief。
- 行文结构没有基于指定的文章模板展开，写成通用提纲。
- 平台规则速查与实际平台规则不符。
- 事实引用中包含未确认事实（待确认事实须标注"待确认"或排除）。
- 合规预检流于形式，没有按5步序列逐项检查。
- 自动选择了平台或模板，而非等待用户手动指定。
