from typing import Any

from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Return the final Markdown report for UTA tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        previous = params.get("previous_result")
        if isinstance(previous, dict) and previous.get("geo_analysis") is True:
            report = self._geo_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_geo_analysis": previous,
            }
        if isinstance(previous, dict) and previous.get("code_analysis") is True:
            report = self._code_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_code_analysis": previous,
            }
        if isinstance(previous, dict) and "weather_result" in previous:
            report = self._weather_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_weather": previous.get("weather_result", {}),
                "source_search_results": previous.get("search_results", []),
            }
        if isinstance(previous, dict) and "search_results" in previous:
            report = self._research_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_search_results": previous.get("search_results", []),
            }
        if isinstance(previous, dict) and previous.get("table_analysis") is True:
            report = self._table_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_table_stats": previous,
            }

        summary = ""
        if isinstance(previous, dict) and isinstance(previous.get("summary_markdown"), str):
            summary = previous["summary_markdown"].strip()
        if not summary:
            summary = "未生成总结报告"
        return {
            "message": summary,
            "report_markdown": summary,
        }

    def _geo_report(self, analysis: dict[str, Any]) -> str:
        return "\n\n".join(
            [
                self._geo_facts_section(analysis),
                self._geo_fact_gaps_section(analysis),
                self._geo_question_matrix_section(analysis),
                self._geo_brief_section(analysis),
                self._geo_compliance_section(analysis),
                self._geo_rule_sources_section(analysis),
                self._geo_next_steps_section(analysis),
            ]
        )

    def _geo_facts_section(self, analysis: dict[str, Any]) -> str:
        facts = analysis.get("brand_facts") if isinstance(analysis.get("brand_facts"), list) else []
        fact_text = "；".join(str(item) for item in facts) if facts else "未提供已确认品牌事实"
        return "\n".join(
            [
                "## 事实输入",
                f"- 行业：{analysis.get('industry') or '未提供行业'}",
                f"- 地区：{analysis.get('region') or '未提供地区'}",
                f"- 品牌事实：{fact_text}",
            ]
        )

    def _geo_fact_gaps_section(self, analysis: dict[str, Any]) -> str:
        gaps = analysis.get("fact_gaps") if isinstance(analysis.get("fact_gaps"), list) else []
        lines = ["## 事实缺口"]
        if not gaps:
            lines.append("- 未发现明显事实缺口")
        else:
            lines.extend(f"- {gap}" for gap in gaps)
        return "\n".join(lines)

    def _geo_question_matrix_section(self, analysis: dict[str, Any]) -> str:
        questions = analysis.get("question_matrix")
        if not isinstance(questions, list):
            questions = []
        lines = ["## 问题矩阵"]
        if not questions:
            lines.append("- 未生成问题矩阵")
            return "\n".join(lines)
        for item in questions:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"{item.get('question') or '未命名问题'}"
                f"（{item.get('layer') or 'unknown'}，{item.get('intent') or 'unknown'}，"
                f"商业价值：{item.get('business_value') or 'unknown'}）"
            )
        return "\n".join(lines)

    def _geo_brief_section(self, analysis: dict[str, Any]) -> str:
        briefs = analysis.get("content_briefs")
        if not isinstance(briefs, list):
            briefs = []
        lines = ["## 内容Brief"]
        if not briefs:
            lines.append("- 未生成内容 Brief")
            return "\n".join(lines)
        for item in briefs:
            if not isinstance(item, dict):
                continue
            titles = item.get("title_candidates") if isinstance(item.get("title_candidates"), list) else []
            title_text = "；".join(str(title) for title in titles[:3]) if titles else "未提供标题候选"
            lines.append(
                f"- {item.get('platform') or '未知平台'} × {item.get('template') or '未知模板'}："
                f"{item.get('target_question') or '未绑定问题'}。标题候选：{title_text}"
            )
        return "\n".join(lines)

    def _geo_compliance_section(self, analysis: dict[str, Any]) -> str:
        checks = analysis.get("compliance_checks")
        if not isinstance(checks, list):
            checks = []
        lines = ["## 平台合规"]
        if not checks:
            lines.append("- 未生成合规检查")
            return "\n".join(lines)
        for check in checks:
            if not isinstance(check, dict):
                continue
            issues = check.get("issues") if isinstance(check.get("issues"), list) else []
            if not issues:
                lines.append(f"- {check.get('level') or 'suggestion'}：未发现阻断风险")
            for issue in issues:
                if isinstance(issue, dict):
                    lines.append(
                        f"- {check.get('level') or 'warning'}：{issue.get('message') or '存在风险'}"
                        f" 建议：{issue.get('suggestion') or '人工复核'}"
                    )
        return "\n".join(lines)

    def _geo_rule_sources_section(self, analysis: dict[str, Any]) -> str:
        rules = analysis.get("vendor_rules") if isinstance(analysis.get("vendor_rules"), dict) else {}
        lines = ["## 规则来源"]
        for key in ["question_matrix_contract", "citability_framework", "platform_risk_levels"]:
            if rules.get(key):
                lines.append(f"- {key}: {rules[key]}")
        if len(lines) == 1:
            lines.append("- 未提供规则来源")
        return "\n".join(lines)

    def _geo_next_steps_section(self, analysis: dict[str, Any]) -> str:
        return "\n".join(
            [
                "## 下一步建议",
                "- 先补齐事实缺口，避免在内容中生成无法核验的确定性承诺。",
                "- 从问题矩阵中选择一个问题，生成平台内容 Brief。",
                "- 发布前按平台合规结果做人工复核。",
            ]
        )

    def _code_report(self, analysis: dict[str, Any]) -> str:
        files = analysis.get("files")
        if not isinstance(files, list):
            files = []

        if analysis.get("project_kind") == "generic":
            return self._generic_code_report(files)
        return "\n\n".join(
            [
                self._code_task_flow_section(),
                self._code_key_files_section(files),
                self._code_module_roles_section(files),
                self._code_call_order_section(),
                self._code_state_memory_section(),
                self._code_desktop_entry_section(files),
                self._code_risks_section(),
                self._code_next_steps_section(),
            ]
        )

    def _generic_code_report(self, files: list[dict[str, Any]]) -> str:
        entry_files = [
            str(item.get("path") or "")
            for item in files
            if "入口" in str(item.get("role") or "")
        ]
        dependencies = []
        for item in files:
            for imported in item.get("imports") if isinstance(item.get("imports"), list) else []:
                if str(imported) not in dependencies:
                    dependencies.append(str(imported))
        call_order = ["## 调用顺序"]
        call_order.append(
            "静态扫描识别到的入口文件：" + "、".join(f"`{path}`" for path in entry_files)
            if entry_files
            else "未从文件名和静态结构中确认唯一入口。"
        )
        if dependencies:
            call_order.append("可见依赖：" + "、".join(f"`{name}`" for name in dependencies[:20]))
        return "\n\n".join(
            [
                "## 任务链路\n本报告从项目清单、入口候选、导入关系和顶层符号梳理代码结构。",
                self._code_key_files_section(files),
                self._code_module_roles_section(files),
                "\n".join(call_order),
                "## 状态与记忆\n静态扫描未假定项目使用特定状态或记忆框架，需要沿入口和依赖继续确认运行时数据流。",
                "## 桌面端入口\n仅在代码中发现明确的桌面框架或窗口入口时才能确认；当前结果不做 UTA 专用假设。",
                "## 风险点\n当前是有文件数量和大小上限的静态扫描，不等同于完整语义调用图，也不会执行或修改项目代码。",
                "## 下一步建议\n- 从识别到的入口文件继续追踪调用关系。\n- 根据项目语言接入对应语法解析器。\n- 对关键流程补充运行时测试或日志验证。",
            ]
        )

    def _code_task_flow_section(self) -> str:
        return "\n".join(
            [
                "## 任务链路",
                "一次 UTA 任务先进入 `main.run_task()`，随后经过 TaskParser、SkillLoader、Planner、Agent Loop、Router、Executor、Verifier、Reflection/Replan、Memory 和最终输出。",
            ]
        )

    def _code_key_files_section(self, files: list[dict[str, Any]]) -> str:
        lines = ["## 关键文件"]
        if not files:
            lines.append("未扫描到关键文件。")
            return "\n".join(lines)
        for item in files:
            path = str(item.get("path") or "unknown")
            role = str(item.get("role") or "UTA 代码文件")
            lines.append(f"- `{path}`：{role}")
        return "\n".join(lines)

    def _code_module_roles_section(self, files: list[dict[str, Any]]) -> str:
        lines = ["## 模块职责"]
        for item in files:
            path = str(item.get("path") or "unknown")
            role = str(item.get("role") or "UTA 代码文件")
            functions = item.get("functions") if isinstance(item.get("functions"), list) else []
            classes = item.get("classes") if isinstance(item.get("classes"), list) else []
            symbols = "，".join([str(name) for name in classes + functions]) or "未发现顶层类或函数"
            lines.append(f"- `{path}`：{role}。主要符号：{symbols}。")
        return "\n".join(lines)

    def _code_call_order_section(self) -> str:
        return "\n".join(
            [
                "## 调用顺序",
                "1. `main.py` 创建 AgentState 并调用 TaskParser。",
                "2. `core/task_parser.py` 识别任务类型和意图。",
                "3. `core/skill_loader.py` 尝试匹配已有 Skill。",
                "4. `core/planner.py` 生成只含目标的 PlanStep。",
                "5. `core/loop.py` 按步骤推进任务，并在失败时触发 Reflection 或 Replan。",
                "6. `core/router.py` 根据 step goal 选择工具。",
                "7. `core/executor.py` 执行工具并返回 ToolResult。",
                "8. `core/verifier.py` 用硬规则判断结果是否合格。",
                "9. `memory_providers/json_memory_provider.py` 保存任务历史、经验、负向规则和 Skill 候选。",
            ]
        )

    def _code_state_memory_section(self) -> str:
        return "\n".join(
            [
                "## 状态与记忆",
                "`AgentState` 是单次任务内的短期记忆，保存 plan、results、checks、feedbacks、replan_events 和 final_output。任务结束后，摘要与最终输出写入长期 JSON Memory（`memory/task_history.json` 或桌面端的 `~/.uta/memory/`），供历史功能读取。",
            ]
        )

    def _code_desktop_entry_section(self, files: list[dict[str, Any]]) -> str:
        scanned_paths = {str(item.get("path") or "") for item in files}
        if "desktop/runner.py" in scanned_paths and "desktop/api.py" in scanned_paths:
            detail = "`desktop.api.DesktopAPI` 接收前端调用，`desktop.runner.TaskRunner` 在后台线程里调用同一条 `main.run_task()` 核心链路。"
        else:
            detail = "桌面端通过 `desktop.api.DesktopAPI` 和 `desktop.runner.TaskRunner` 调用核心任务链路。"
        return "\n".join(["## 桌面端入口", detail])

    def _code_risks_section(self) -> str:
        return "\n".join(
            [
                "## 风险点",
                "当前版本只扫描当前 UTA 项目的白名单文件，不读取任意外部项目；它提取静态结构，不生成完整语义调用图，也不会自动修改代码。",
            ]
        )

    def _code_next_steps_section(self) -> str:
        return "\n".join(
            [
                "## 下一步建议",
                "- 支持用户显式指定本地项目目录。",
                "- 为更大的项目增加文件数量上限和路径安全提示。",
                "- 在代码结构稳定后再考虑模块依赖图或语义检索。",
            ]
        )

    def _research_report(self, search_payload: dict[str, Any]) -> str:
        query = str(search_payload.get("query") or "调研主题")
        results = search_payload.get("search_results") or []
        if not results:
            return "\n\n".join(
                [
                    "## 结论\n未找到可用来源。",
                    "## 关键发现\n- 未找到可用来源。",
                    "## 来源\n未找到可用来源。",
                    "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
                ]
            )

        findings = "\n".join(
            f"- {item.get('snippet') or item.get('title') or '搜索结果未提供摘要'}"
            for item in results
        )
        sources = "\n".join(
            f"- [{item.get('title') or item.get('url')}]({item.get('url')}): {item.get('snippet') or '无摘要'}"
            for item in results
            if item.get("url")
        )
        return "\n\n".join(
            [
                f"## 结论\n基于当前搜索结果，{query} 可以先形成一份初步调研结论。",
                f"## 关键发现\n{findings}",
                f"## 来源\n{sources}",
                "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
            ]
        )

    def _weather_report(self, weather_payload: dict[str, Any]) -> str:
        weather = weather_payload.get("weather_result") or {}
        city = str(weather.get("city") or weather_payload.get("query") or "当前城市")
        weather_text = str(weather.get("weather_text") or "未知天气")
        temperature = self._weather_value(weather.get("temperature"), "℃")
        apparent = self._weather_value(weather.get("apparent_temperature"), "℃")
        humidity = self._weather_value(weather.get("relative_humidity"), "%")
        precipitation = self._weather_value(weather.get("precipitation"), " mm")
        wind_speed = self._weather_value(weather.get("wind_speed"), " km/h")
        wind_direction = self._weather_value(weather.get("wind_direction"), "°")
        observed_at = str(weather.get("time") or "未知")
        provider = str(weather.get("provider") or "天气数据接口")
        source_url = str(weather.get("source_url") or "")

        source = f"- [{provider}]({source_url}): 当前天气数据接口。" if source_url else f"- {provider}"
        return "\n\n".join(
            [
                (
                    f"## 结论\n{city}当前天气：{weather_text}。"
                    f"气温：{temperature}，体感温度：{apparent}。"
                ),
                "\n".join(
                    [
                        "## 关键发现",
                        f"- 观测时间：{observed_at}",
                        f"- 气温：{temperature}",
                        f"- 体感温度：{apparent}",
                        f"- 湿度：{humidity}",
                        f"- 降水量：{precipitation}",
                        f"- 风速：{wind_speed}",
                        f"- 风向：{wind_direction}",
                    ]
                ),
                f"## 来源\n{source}",
                "## 注意事项\n当前结果来自天气数据接口，不是普通网页搜索摘要；实时天气可能随时间变化。",
            ]
        )

    def _weather_value(self, value: Any, unit: str) -> str:
        if value is None or value == "":
            return "未知"
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value}{unit}"

    def _table_report(self, analysis: dict[str, Any]) -> str:
        return "\n\n".join(
            [
                self._field_section(analysis),
                self._stats_section(analysis),
                self._anomaly_section(analysis),
                self._category_section(analysis),
                self._business_section(analysis),
                self._next_steps_section(),
            ]
        )

    def _field_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 字段说明"]
        for column in analysis.get("columns", []):
            lines.append(
                f"- {column['name']}：类型 {column['dtype']}，非空 {column['non_null_count']}，缺失 {column['missing_count']}"
            )
        return "\n".join(lines)

    def _stats_section(self, analysis: dict[str, Any]) -> str:
        return "\n".join(
            [
                "## 基础统计",
                f"- 行数：{analysis.get('row_count', 0)}",
                f"- 列数：{analysis.get('column_count', 0)}",
                f"- 缺失值数量：{analysis.get('missing_count', 0)}",
                f"- 异常值数量：{analysis.get('anomaly_count', 0)}",
            ]
        )

    def _anomaly_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 异常数据"]
        anomalies = analysis.get("anomalies", [])
        if not anomalies:
            lines.append("未检测到异常")
            return "\n".join(lines)

        for anomaly in anomalies:
            lines.append(
                f"- 第 {anomaly['row_number']} 行，字段 {anomaly['column']}，值 {anomaly['value']}：{anomaly['reason']}"
            )
        return "\n".join(lines)

    def _category_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 分类汇总"]
        summaries = analysis.get("category_summaries", [])
        if not summaries:
            lines.append("未发现可汇总的分类字段")
            return "\n".join(lines)

        for summary in summaries:
            values = "，".join(
                f"{item['value']} {item['count']} 条"
                for item in summary.get("top_values", [])
            )
            lines.append(f"- {summary['column']}：{values}")
        return "\n".join(lines)

    def _business_section(self, analysis: dict[str, Any]) -> str:
        missing = analysis.get("missing_count", 0)
        anomalies = analysis.get("anomaly_count", 0)
        if missing or anomalies:
            return "\n".join(
                [
                    "## 业务解释",
                    "表格存在需要关注的数据质量问题，建议先处理缺失值和异常值，再用于业务决策。",
                ]
            )
        return "\n".join(
            [
                "## 业务解释",
                "表格基础质量较稳定，可用于后续分类汇总和业务复盘。",
            ]
        )

    def _next_steps_section(self) -> str:
        return "\n".join(
            [
                "## 后续建议",
                "- 核对缺失值来源",
                "- 复查异常值是否为真实业务峰值",
                "- 按关键分类字段继续做分组分析",
            ]
        )
