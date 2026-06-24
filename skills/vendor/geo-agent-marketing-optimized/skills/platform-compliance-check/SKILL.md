---
name: platform-compliance-check
description: Use when checking drafts, titles, summaries, publication records, platform rules, advertising risk, forbidden terms, AI labels, contact information, or publish-readiness for Chinese content platforms.
---

# 平台发布合规检查

这是当前项目的 P0 主技能。它用于发布检查和记录发布结果，不替代人工法务审核。

## 检查顺序

1. 通用红线：违法、虚假、绝对化承诺、敏感行业违规。
2. 平台规则：标题、正文、摘要、图片、尾部推广、外链、二维码、联系方式。
3. 行业风险：教育、金融、医疗、食品、房地产、酒类等。
4. 事实风险：资质、价格、案例、证书编号、联系方式是否有已确认来源。
5. AIGC 标识：目标平台是否要求标识。

## 风险分级

详见 `references/risk-levels.md`。

## 当前项目行为建议

- `block`：默认阻止发布检查通过，但允许用户保存“已发布记录”时保留风险说明。
- `warning`：允许保存，必须展示风险提示。
- `suggestion`：仅作为优化建议，不阻断。

## 禁止事项

- 禁止把所有风险都当成阻断项。
- 禁止文章已经发布后仍强制无法记录发布结果。
- 禁止只返回“违规内容”而不说明触发原因和修改方向。
