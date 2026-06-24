---
id: geo_analysis
name: GEO 分析 Skill
version: 1
enabled: true
task_type: geo_analysis
priority: 120
trigger_keywords:
  - GEO
  - 生成式引擎优化
  - AI可见性
  - AI 可见性
  - 问题矩阵
  - 内容Brief
  - 内容 Brief
  - 平台合规
workflow:
  - 读取 GEO 规则包并生成问题矩阵
  - 生成 GEO 分析报告
---

# GEO 分析 Skill

这是对 `skills/vendor/geo-agent-marketing-optimized/` 规则包的 UTA 适配层。

当前只接入 P0 主链路：

- GEO 问题矩阵。
- AI 可引用性和事实缺口。
- 内容规划 Brief。
- 平台合规检查。

P1/P2/P3 规则保留在 vendor 目录中，暂不进入默认执行链路。
