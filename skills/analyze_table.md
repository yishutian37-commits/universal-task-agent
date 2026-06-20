---
id: analyze_table
name: 表格分析 Skill
version: 1
enabled: true
task_type: data_analysis
priority: 100
trigger_keywords:
  - 分析
  - 表格
  - csv
  - excel
workflow:
  - 读取表格文件
  - 分析字段、行数、列数和缺失值
  - 生成表格分析报告
---

# 表格分析 Skill

适用于读取 CSV 或 Excel 文件，并输出字段说明、基础统计、异常数据、分类汇总、业务解释和后续建议。
