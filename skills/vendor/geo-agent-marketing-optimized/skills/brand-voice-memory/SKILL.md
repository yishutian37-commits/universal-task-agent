---
name: brand-voice-memory
description: Use when turning article feedback, brand voice preferences, style rules, rejected expressions, or project experience into reusable writing memory or experience skills.
---

# 品牌调性与记忆沉淀

这是当前项目的 P1 支撑技能。它用于记忆库和经验技能库，不负责生成品牌事实。

## 能沉淀的内容

- 语气偏好：客观、克制、口语化、专业、案例化。
- 结构偏好：先结论、再证据、再建议。
- 禁用表达：极限词、空泛词、强营销词。
- 平台经验：某平台适合什么标题、什么尾部表达。
- 复盘经验：哪些问题没被 AI 推荐，后续怎么补内容。

## 不能沉淀的内容

- 未确认的资质、价格、案例、地址、证书编号。
- 模型临时编出来的事实。
- 只适合单篇文章的一次性措辞。
- 用户原话中含糊、矛盾、明显错误的要求。

## 当前项目流程

1. 收集人工反馈。
2. AI 分析成清晰规则，而不是直接保存原话。
3. 生成待确认技能建议。
4. 用户可确认启用、拒绝使用、编辑、删除。
5. 启用后按项目级、行业级、全局级生效。

## 输出格式

```json
{
  "title": "规则标题",
  "scope": "project | industry | global",
  "trigger_scene": "article_writing | platform_adaptation | monitoring_review",
  "rule": "可执行的中文规则",
  "negative_examples": [],
  "positive_examples": []
}
```
