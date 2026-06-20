---
id: summarize_article
name: 文本总结 Skill
version: 1
enabled: true
task_type: summarize
priority: 100
trigger_keywords:
  - 总结
  - 摘要
  - 提取
workflow:
  - 读取输入内容
  - 提取核心信息
  - 生成结构化报告
---

# 文本总结 Skill

适用于把一段中文文本整理成包含摘要、核心观点和风险点的结构化报告。
