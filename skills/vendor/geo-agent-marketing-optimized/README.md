# GEO Agent 营销规则优化包

这是从 `市场营销-custom-v2.0.0` 改写出来的当前项目适配版。它不是为了替换 GEO Flow Agent，而是作为规则补充包，服务当前项目的主链路：

`项目知识库 / 品牌事实库 -> 问题矩阵 -> AI 监测 -> 内容任务 -> 平台稿件 -> 发布检查 -> 复测报告 -> 经验沉淀`

## 改写原则

- 保留 GEO 相关方法论，弱化传统营销泛化模块。
- 所有确定性事实必须来自已确认、可公开使用的品牌事实或项目知识资产。
- 不声称知道 AI 平台内部机制，只基于公开回答、来源和监测结果做推断。
- 问题矩阵必须跨行业通用，禁止写死某个企业、行业或 AI 平台名称。
- 平台规则必须作为硬约束进入文章生成和发布检查，不能只作为提示建议。
- 传统活动策划、热点追踪、竞品追踪只作为外围能力，不进入默认 GEO 主链路。

## 技能分层

| 层级 | 技能 | 当前项目用途 |
| --- | --- | --- |
| P0 | `geo-content-optimization` | 问题矩阵、可引用性、内容缺口、内容任务建议 |
| P0 | `geo-copywriting` | 平台稿件生成、事实引用、输出格式约束 |
| P0 | `platform-compliance-check` | 发布检查、风险分级、平台规则校验 |
| P1 | `brand-voice-memory` | 记忆库、经验技能库、文章反馈沉淀 |
| P1 | `geo-monitoring-analysis` | 监测明细、来源覆盖、报告中心 |
| P2 | `competitive-visibility-tracking` | 竞品可见性、来源资产对比 |
| P3 | `social-trend-screening` | 选题筛选，不直接追热点硬蹭 |
| P3 | `lightweight-campaign-planning` | 内容活动计划，不替代 GEO 主链路 |

## 与当前项目的落地映射

详见 `skills/geo-content-optimization/references/current-project-integration.md`。

## 不建议直接做的事

- 不要把整个包作为一段 prompt 塞进文章生成。
- 不要用包里的示例企业、示例行业污染通用规则。
- 不要用传统营销活动逻辑替代 GEO 闭环。
- 不要让平台合规只停留在文本建议，必须进入结构化规则和检查结果。
