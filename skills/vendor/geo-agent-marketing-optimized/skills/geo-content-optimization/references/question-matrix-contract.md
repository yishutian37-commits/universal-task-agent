# 问题矩阵合同

## 输入

- 行业、地区、品牌主体、服务或产品范围。
- 已确认品牌事实。
- 项目知识资产。
- 目标用户类型。
- 当前监测平台和重点业务目标。

## 输出字段

每个问题必须包含：

```json
{
  "question": "用户真实会问的问题",
  "layer": "pool_layer | verification_layer | authority_layer | conversion_layer",
  "intent": "本地推荐 | 资质核验 | 价格比较 | 口碑验证 | 产品选型 | 案例验证 | 售后保障",
  "formula": "地域/品类/场景词 + 推荐/验证/比较/怎么选",
  "keyword_breakdown": {
    "region": [],
    "category": [],
    "scenario": [],
    "brand": [],
    "evidence": []
  },
  "evidence_support": "需要哪些事实支撑",
  "recommended_platforms": [],
  "business_value": "high | medium | low",
  "content_actionability": "high | medium | low",
  "enabled": true
}
```

## 四层定义

- 入池层：让品牌进入 AI 候选名单，例如“某地某类服务哪家靠谱”。
- 基础验证层：验证资质、地址、价格、证书、产品参数、案例。
- 权重提升层：比较品牌、案例、权威来源、行业背书。
- 转化承接层：报名、预约、购买、咨询、售后、流程、注意事项。

## 必须遵守

- 问题要像真实用户提问，不像 SEO 关键词堆砌。
- 默认不出现 AI 平台名：DeepSeek、Kimi、豆包、文心、通义、ChatGPT、Gemini 等。
- 只有当项目行业确实涉及某关键词时才使用该行业词，禁止跨行业污染。
- 生成后允许用户新增、修改、删除、禁用，并沉淀为行业模板建议。
