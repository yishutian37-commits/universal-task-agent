# UTA V0.6 Data Analysis 设计

## 背景

当前 `v0.5-verifier-reflection` 已经跑通文本总结主链路：

- `TaskParser` 可以识别 `summarize` / `data_analysis` / `unknown`；
- `Planner` 已经为 `data_analysis` 生成三步计划；
- `Router` 已经能把表格相关步骤路由到 `table_tool`；
- `Verifier` 已经有表格 L1 数字一致性 helper；
- `Loop` 已支持单步失败后的 Reflection + 重试。

但 `table_tool` 仍然是占位工具，`FileTool` 只支持 `.txt` / `.md`，`ReportTool` 也只会输出总结报告。v0.6 的目标是把表格分析任务做成一条可运行、可校验、可展示的真实链路。

## 目标

完成 `v0.6-data-analysis`：

1. CLI 支持本地 `.csv` 和 `.xlsx` 表格分析任务；
2. `file_tool` 能识别表格文件路径，并把路径交给后续工具；
3. 新增真实 `table_tool`，读取表格并输出字段识别、行列统计、缺失值检查、异常值检查、分类汇总；
4. `report_tool` 能基于 `table_tool` 结果生成 Markdown 表格分析报告；
5. `Verifier` 对表格报告做结构性硬校验和 L1 数字一致性校验；
6. 增加 `examples/orders.csv` 作为可演示数据；
7. README / CHANGELOG 更新 v0.6 说明；
8. 完成后打 tag：`v0.6-data-analysis`。

## 非目标

v0.6 不做：

- 不接外部数据库；
- 不做图表；
- 不做复杂统计建模；
- 不做自然语言高级业务洞察；
- 不引入浏览器或前端界面；
- 不接 Memory / Skill / TAM；
- 不做完整 replan，只沿用 v0.5 的单步重试。

## 方案选择

### 方案 A：pandas 表格工具 + 规则报告 + 硬校验

使用 `pandas` 读取 CSV / Excel，`table_tool` 输出结构化统计，`report_tool` 用规则生成 Markdown，`Verifier` 校验小节、字段覆盖和数字一致性。

优点：贴合 PRD 的 pandas 学习目标；CSV / Excel 能统一处理；数字来源清晰；测试稳定。缺点：需要增加 `pandas` / `openpyxl` 依赖。

### 方案 B：只做 CSV，Excel 后补

只用 Python 标准库 `csv` 实现 CSV 分析。

优点：依赖少，开发更快。缺点：不满足 PRD A14 的 CSV / Excel 验收。

### 方案 C：LLM 参与业务解释

`table_tool` 负责数字统计，LLM 根据统计结果生成业务解释。

优点：输出更像智能分析。缺点：v0.6 容易膨胀，且 LLM 可能改写数字，增加校验压力。

选择方案 A。

## 数据流

表格分析任务沿用现有三步计划：

```text
读取表格文件 -> 分析字段、行数、列数和缺失值 -> 生成表格分析报告
```

运行时数据流：

1. `file_tool` 从 `user_input` 中识别 `.csv` / `.xlsx` 路径；
2. `file_tool` 返回 `source_type="file"`、`source=<path>`、`file_kind="table"`；
3. `table_tool` 优先读取 `previous_result["source"]`，找不到时再从 `user_input` 中识别路径；
4. `table_tool` 用 `pandas.read_csv()` 或 `pandas.read_excel()` 读取数据；
5. `table_tool` 返回结构化 `table_analysis`；
6. `report_tool` 检测到 `table_analysis` 后生成 Markdown 报告；
7. `Verifier` 检查报告结构和数字来源一致性；
8. `Loop` 通过后把最终 Markdown 写入 `state.final_output`。

## TableTool 输出结构

新增 `tools/table_tool.py`，工具名为 `table_tool`。

成功时返回：

```python
{
    "message": "已完成表格分析",
    "table_analysis": True,
    "source": "/absolute/or/user/path/orders.csv",
    "row_count": 10,
    "column_count": 5,
    "missing_count": 2,
    "anomaly_count": 1,
    "columns": [
        {
            "name": "warehouse",
            "dtype": "object",
            "non_null_count": 10,
            "missing_count": 0,
        }
    ],
    "anomalies": [
        {
            "column": "quantity",
            "row_number": 8,
            "value": 999,
            "reason": "IQR 异常值",
        }
    ],
    "category_summaries": [
        {
            "column": "warehouse",
            "top_values": [
                {"value": "上海仓", "count": 4},
                {"value": "北京仓", "count": 3},
            ],
        }
    ],
}
```

异常值规则：

- 只检查数值列；
- 当有效数字少于 4 个时，该列不判异常；
- 使用 IQR：低于 `Q1 - 1.5 * IQR` 或高于 `Q3 + 1.5 * IQR` 的值计为异常；
- `anomaly_count` 是所有数值列异常单元格数量。

分类汇总规则：

- 只处理非数值列；
- 每列最多保留前 5 个高频值；
- 空值不进入 top values。

## ReportTool 表格报告

当 `previous_result` 中包含 `table_analysis=True` 时，`report_tool` 输出固定 Markdown：

```markdown
## 字段说明

## 基础统计

## 异常数据

## 分类汇总

## 业务解释

## 后续建议
```

报告必须显式写出：

- 全部字段名；
- 行数；
- 列数；
- 缺失值数量；
- 异常值数量；
- 未检测到异常时写 `未检测到异常`。

业务解释先采用规则生成，不调用 LLM。重点是保证数据来源可追踪、数字可校验。

## Verifier 表格校验

当 `state.task_type == "data_analysis"` 且当前工具是 `report_tool` 时，`Verifier` 检查：

1. 报告包含 `字段说明`、`基础统计`、`异常数据` 三个必要小节；
2. 三个必要小节内容非空；
3. `字段说明` 覆盖 `table_tool` 输出的全部列名；
4. 报告中的行数、列数、缺失值数量、异常值数量与 `table_tool` 结果完全一致；
5. `anomaly_count == 0` 时，报告包含 `未检测到异常`。

数字一致性复用并扩展 v0.5 的 `check_table_numbers()`。

## 错误处理

`table_tool` 对用户给出清晰失败原因：

- 找不到表格路径：`未找到可读取的 CSV 或 Excel 文件`；
- 文件后缀不支持：`仅支持 .csv / .xlsx`；
- 文件为空：`表格为空，无法分析`；
- pandas 读取失败：保留底层错误信息，但包装成 `ValueError`，交给 `Executor` 转成失败 `ToolResult`。

失败后由现有 `Verifier` / `Reflection` / `Loop` 机制处理。

## 依赖

新增依赖：

```text
pandas>=2.0.0
openpyxl>=3.1.0
```

`pandas` 负责 CSV / Excel 读取和基础统计；`openpyxl` 是 pandas 读取 `.xlsx` 的引擎。

## 测试策略

所有单元测试默认不访问真实网络。

1. `FileTool`：
   - 能识别 `.csv`；
   - 能识别 `.xlsx`；
   - 文本任务原行为不变；
2. `TableTool`：
   - 能读取 CSV 并返回行列、缺失值、字段；
   - 能读取 Excel；
   - 能检测 IQR 异常值；
   - 找不到文件时抛出清晰错误；
3. `ReportTool`：
   - 表格分析结果生成固定 Markdown 小节；
   - 无异常时写 `未检测到异常`；
4. `Verifier`：
   - 完整表格报告通过；
   - 缺字段失败；
   - 数字不一致失败；
   - 无异常但报告未写 `未检测到异常` 时失败；
5. `Loop` / `Main`：
   - 注入工具注册表后，`data_analysis` 任务能从读取文件到最终报告跑通；
   - CLI demo 使用 `examples/orders.csv` 跑通。

## 验收

完成后应满足：

- `.venv/bin/python -m pytest -v` 全部通过；
- `.venv/bin/python main.py --task "分析 examples/orders.csv"` 输出 Markdown 表格分析报告；
- 报告包含 `字段说明`、`基础统计`、`异常数据`；
- 报告数字与 `table_tool` 结果一致；
- `git grep` 不包含真实 API key；
- tag 为 `v0.6-data-analysis`。
