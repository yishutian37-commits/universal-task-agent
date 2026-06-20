# Expected Output Examples

## V0.1 Skeleton

```text
任务已完成：mock result
```

## V0.8 Skill Runtime

`outputs/logs/<task_id>.log` includes the matched Skill:

```text
[SkillLoader] matched_skill = analyze_table
[Planner] created 3 steps
[Loop] step 1 started: 读取表格文件
```

`outputs/states/<task_id>_state.json` includes:

```json
"matched_skill": {
  "id": "analyze_table",
  "name": "表格分析 Skill",
  "task_type": "data_analysis"
}
```
