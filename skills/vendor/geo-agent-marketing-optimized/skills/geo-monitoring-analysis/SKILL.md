---
name: geo-monitoring-analysis
description: Use when analyzing AI monitoring samples, brand mention rate, recommendation rate, source links, screenshots, answer excerpts, sentiment, report aggregation, or monitoring-to-content feedback.
---

# GEO 监测分析

这是当前项目的 P1 支撑技能。它用于解释 AI 监测结果并回流内容任务。

## 明细粒度

监测结果应按“问题 × 平台”展示，而不是只按批次展示。

每条样本至少包含：

- 问题。
- 平台。
- 原始回答摘录或全文。
- 是否提及品牌。
- 是否推荐品牌。
- 情绪。
- 信息来源列表。
- 截图。
- 检测时间。
- 可删除操作。

## 来源分析

来源链接应分类为：

- 自有资产：官网、公众号、百家号、自有媒体。
- 权威来源：政府、协会、媒体、院校。
- 第三方平台：点评、问答、行业站。
- 竞品资产：竞品官网或内容页。
- 低质量聚合页。
- 无来源。

## 回流内容任务

如果出现以下情况，建议生成内容任务：

- 品牌未提及。
- 提及但未推荐。
- 推荐但无自有来源。
- 回答中事实错误。
- 来源被竞品占据。
- 某类问题持续低推荐。

## 报告表达

报告必须用业务人员看得懂的话解释，不直接展示大段 JSON。
