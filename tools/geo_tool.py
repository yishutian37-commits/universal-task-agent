from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool


class GeoTool(BaseTool):
    name = "geo_tool"
    description = "Generate GEO question matrices, content briefs, and compliance checks."

    def __init__(self, vendor_root: Path | str = "skills/vendor/geo-agent-marketing-optimized"):
        self.vendor_root = Path(vendor_root)

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = str(params.get("user_input") or params.get("goal") or "")
        industry = self._extract_field(user_input, "行业") or "未提供行业"
        region = self._extract_field(user_input, "地区") or "未提供地区"
        brand_facts = self._extract_brand_facts(user_input)
        fact_gaps = self._fact_gaps(brand_facts)
        question_matrix = self._question_matrix(industry, region)
        compliance_checks = self._compliance_checks(user_input, brand_facts)
        content_briefs = self._content_briefs(question_matrix, brand_facts, compliance_checks)

        return {
            "message": "已完成 GEO 分析",
            "geo_analysis": True,
            "industry": industry,
            "region": region,
            "brand_facts": brand_facts,
            "fact_gaps": fact_gaps,
            "question_matrix": question_matrix,
            "content_briefs": content_briefs,
            "compliance_checks": compliance_checks,
            "vendor_rules": self._vendor_rules(),
        }

    def _extract_field(self, text: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*(?:是|为|:|：)\s*([^，。；;\n]+)", text)
        return match.group(1).strip() if match else ""

    def _extract_brand_facts(self, text: str) -> list[str]:
        match = re.search(r"品牌事实\s*(?:是|为|:|：)\s*([^。\n]+)", text)
        if not match:
            return []
        parts = re.split(r"[、，,；;]", match.group(1))
        return [part.strip() for part in parts if part.strip()]

    def _fact_gaps(self, brand_facts: list[str]) -> list[str]:
        facts_text = " ".join(brand_facts)
        required = {
            "资质": ("资质", "证书", "认证"),
            "价格": ("价格", "收费", "报价"),
            "地址": ("地址", "门店", "位置"),
            "案例": ("案例", "客户", "项目"),
            "联系方式": ("电话", "微信", "联系方式", "官网"),
        }
        return [
            label
            for label, keywords in required.items()
            if not any(keyword in facts_text for keyword in keywords)
        ]

    def _question_matrix(self, industry: str, region: str) -> list[dict[str, Any]]:
        return [
            self._question(
                f"{region}{industry}哪家靠谱？",
                "pool_layer",
                "本地推荐",
                "地域+品类+推荐",
                region,
                industry,
                ["公众号", "百家号"],
                "high",
            ),
            self._question(
                f"{region}{industry}服务有哪些资质、地址和案例可以核验？",
                "verification_layer",
                "资质核验",
                "地域+品类+验证",
                region,
                industry,
                ["官网", "公众号"],
                "high",
            ),
            self._question(
                f"{region}{industry}服务怎么比较口碑和案例？",
                "authority_layer",
                "口碑验证",
                "地域+品类+比较",
                region,
                industry,
                ["知乎", "百家号"],
                "medium",
            ),
            self._question(
                f"{region}{industry}咨询或下单前要注意什么？",
                "conversion_layer",
                "售后保障",
                "地域+品类+怎么选",
                region,
                industry,
                ["公众号", "小红书"],
                "medium",
            ),
        ]

    def _question(
        self,
        question: str,
        layer: str,
        intent: str,
        formula: str,
        region: str,
        industry: str,
        platforms: list[str],
        business_value: str,
    ) -> dict[str, Any]:
        return {
            "question": question,
            "layer": layer,
            "intent": intent,
            "formula": formula,
            "keyword_breakdown": {
                "region": [] if region.startswith("未提供") else [region],
                "category": [] if industry.startswith("未提供") else [industry],
                "scenario": [],
                "brand": [],
                "evidence": ["资质", "案例", "来源"],
            },
            "evidence_support": "需要已确认品牌事实、可公开来源、案例或服务边界支撑。",
            "recommended_platforms": platforms,
            "business_value": business_value,
            "content_actionability": "high",
            "enabled": True,
        }

    def _content_briefs(
        self,
        question_matrix: list[dict[str, Any]],
        brand_facts: list[str],
        compliance_checks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        target = question_matrix[0]
        return [
            {
                "platform": "公众号",
                "template": "品牌介绍",
                "target_question": target["question"],
                "layer": target["layer"],
                "title_candidates": [
                    f"{target['question']}先看这几个核验点",
                    f"{target['question']}一份客观选择清单",
                    f"{target['question']}从资质、案例和服务边界判断",
                ],
                "writing_guidance": "先回答目标问题，再列核验标准，最后提醒读者以公开资料和官方渠道核验。",
                "required_facts": brand_facts,
                "compliance_level": compliance_checks[0]["level"],
            }
        ]

    def _compliance_checks(self, user_input: str, brand_facts: list[str]) -> list[dict[str, Any]]:
        issues = []
        if "承诺" in user_input or "夸大" in user_input:
            issues.append(
                {
                    "type": "claim_risk",
                    "message": "输入中出现承诺或夸大相关表达，生成内容时需要避免绝对化表述。",
                    "suggestion": "改成可核验事实、服务边界或第三方来源说明。",
                }
            )
        if not brand_facts:
            issues.append(
                {
                    "type": "fact_gap",
                    "message": "缺少已确认品牌事实，不能生成确定性推荐。",
                    "suggestion": "先补充资质、地址、案例、价格或公开来源。",
                }
            )
        return [
            {
                "level": "warning" if issues else "suggestion",
                "issues": issues,
                "can_save_publish_record": True,
            }
        ]

    def _vendor_rules(self) -> dict[str, str]:
        base = self.vendor_root / "skills"
        return {
            "root": str(self.vendor_root),
            "question_matrix_contract": str(
                base / "geo-content-optimization/references/question-matrix-contract.md"
            ),
            "citability_framework": str(
                base / "geo-content-optimization/references/citability-framework.md"
            ),
            "platform_risk_levels": str(
                base / "platform-compliance-check/references/risk-levels.md"
            ),
        }
