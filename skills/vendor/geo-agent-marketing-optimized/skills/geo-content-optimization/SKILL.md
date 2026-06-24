---
name: geo-content-optimization
description: Use when optimizing GEO/AIO workflows around brand facts, question matrices, AI visibility, citability, source coverage, content gaps, or monitoring-to-content recommendations.
---

# GEO 内容优化

这是当前项目的 P0 主技能。它只服务 GEO 主链路，不做泛营销策划。

## 核心原则

- 先看事实，再生成问题，再做内容。
- 不把 AI 平台名写进用户问题，除非用户明确要比较 AI 产品本身。
- 不把示例企业、示例行业写进通用规则。
- 不声称知道 AI 引擎内部机制，只根据监测回答、来源链接和公开表现做谨慎推断。
- 资质、价格、地址、证书编号、案例、联系方式等确定性内容必须来自已确认事实或项目知识资产。

## 当前项目落地

- 品牌事实：对接品牌事实库。
- 项目资料：对接项目知识库。
- 问题矩阵：对接问题库和行业问题模板库。
- 监测分析：对接 AI 搜索详情、来源抓取、推荐率、提及率。
- 内容任务：把未提及、未推荐、来源不足的问题转成内容任务。

详细映射见 `references/current-project-integration.md`。

## 工作顺序

1. 读取项目行业、地区、品牌主体、服务范围、目标用户和已确认事实。
2. 判断事实缺口：资质、价格、地址、案例、产品、联系方式、荣誉、服务边界。
3. 生成或修正问题矩阵，使用四层结构：入池层、基础验证层、权重提升层、转化承接层。
4. 给每个问题补齐意图、公式、证据需求、推荐平台、商业价值和内容可执行性。
5. 根据监测结果识别内容缺口，输出”应该补什么内容、发到什么平台、需要哪些事实”。
6. **问题矩阵 → Brief生成**：将完整问题矩阵传递给 geo-copywriting 技能。用户从矩阵中手动指定 N个平台 × M个文章模板，geo-copywriting 根据矩阵中的问题匹配平台和模板，输出内容规划brief（标题推荐 + 行文指南），不生成完整文章。

### 输出链路总结

```
品牌资料 → 事实审计（Output 1）
         → AI可引用性评估（Output 2）
         → 问题矩阵（Output 3，含四层×8公式×N个问题）
                ↓
         用户指定 平台×模板 组合
                ↓
         geo-copywriting 从矩阵中选问题 → 生成Brief（Output 4）
                ↓
         platform-compliance-check 合规预检（嵌入每份Brief末尾）
```

Brief是问题矩阵的下游产物，每份brief必须可追溯到矩阵中的一个具体问题。

## 必读参考

- 问题矩阵合同：`references/question-matrix-contract.md`
- AI 可引用性框架：`references/citability-framework.md`
- 当前项目映射：`references/current-project-integration.md`

## 禁止事项

- 禁止生成“某企业适合哪些 DeepSeek / Kimi / 豆包”这类错误问题。
- 禁止为了推荐品牌而编造事实。
- 禁止把平台规则、合规风险和事实边界写成可选建议。
- 禁止输出只适配单一历史项目的问题矩阵。
