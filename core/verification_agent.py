"""
Verification Agent — 对抗性验证器

设计哲学（参考 CC verificationAgent.ts）：
  - 验证者的职责是尝试「打破」实现，不是确认它能工作
  - 对抗 rubber-stamping：明确提示 LLM 不要宽容地放过问题
  - 结构化 VERDICT 输出：PASS / FAIL / PARTIAL，附带具体证据
  - 独立于执行 Agent：用不同的 Agent 或不同的 prompt 策略验证

在编排循环中的位置：
  OrchestratorLoop._evaluate() 可以选择性地调用 VerificationAgent
  代替或补充 QualityEvaluator 的审阅。
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List

from .orchestrator_prompts import VERIFICATION_PROMPT
from .task_dag import SubTask, ReviewVerdict
from .json_extract import extract_json

logger = logging.getLogger(__name__)


@dataclass
class VerificationVerdict:
    """验证裁定"""
    verdict: str                                    # PASS | FAIL | PARTIAL
    confidence: float = 0.0                         # 0.0 ~ 1.0
    evidence: List[str] = field(default_factory=list)       # 证据列表
    vulnerabilities: List[str] = field(default_factory=list) # 发现的漏洞
    suggestions: List[str] = field(default_factory=list)     # 改进建议
    reasoning: str = ""
    tested_aspects: List[str] = field(default_factory=list)  # 测试了哪些方面

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "vulnerabilities": self.vulnerabilities,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
            "tested_aspects": self.tested_aspects,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'VerificationVerdict':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_review_verdict(self) -> ReviewVerdict:
        """转换为 ReviewVerdict 供编排器使用"""
        if self.verdict == "PASS":
            return ReviewVerdict(
                understanding=self.reasoning,
                usable_parts=self.evidence,
                decision="proceed",
                reasoning=f"Verification PASS (confidence: {self.confidence:.0%})",
                forward_context=self.reasoning,
                ready_for_next=True,
            )
        elif self.verdict == "PARTIAL":
            return ReviewVerdict(
                understanding=self.reasoning,
                usable_parts=self.evidence,
                problematic_parts=self.vulnerabilities,
                decision="partial_rework",
                reasoning=f"Verification PARTIAL: {'; '.join(self.vulnerabilities[:3])}",
                rework_instructions='\n'.join(self.suggestions) if self.suggestions else "",
                ready_for_next=False,
            )
        else:  # FAIL
            return ReviewVerdict(
                understanding=self.reasoning,
                problematic_parts=self.vulnerabilities,
                decision="rework",
                reasoning=f"Verification FAIL: {'; '.join(self.vulnerabilities[:3])}",
                rework_instructions='\n'.join(self.suggestions) if self.suggestions else
                    "Address all identified vulnerabilities",
                ready_for_next=False,
            )


class VerificationAgent:
    """
    对抗性验证器

    使用方式：
        verifier = VerificationAgent(agent_pool)
        verdict = await verifier.verify(subtask, output, goal)
        if verdict.verdict != "PASS":
            # 处理失败...
    """

    def __init__(self, agent_pool, verify_agent: str = "claude"):
        self.pool = agent_pool
        self.verify_agent = verify_agent

    async def verify(
        self,
        subtask: SubTask,
        output: str,
        goal: str,
        acceptance_criteria: Optional[List[str]] = None,
    ) -> VerificationVerdict:
        """
        对抗性验证 — 尝试找出输出中的问题

        关键：提示词明确要求 LLM 扮演「破坏者」角色，
        不是问「这个好不好」，而是问「这个哪里有问题」。
        """
        criteria = acceptance_criteria or subtask.acceptance_criteria or []
        criteria_text = '\n'.join(f"- {c}" for c in criteria) if criteria else "(no specific criteria)"

        # 保留输出完整性
        output_text = output or "(no output)"
        if len(output_text) > 8000:
            output_text = (
                output_text[:5000]
                + "\n\n... [middle omitted] ...\n\n"
                + output_text[-2000:]
            )

        prompt = VERIFICATION_PROMPT.format(
            goal=goal,
            task_description=subtask.description,
            agent_type=subtask.agent_type,
            acceptance_criteria=criteria_text,
            agent_output=output_text,
        )

        try:
            result = await self.pool.execute(
                self.verify_agent, prompt, "/tmp", timeout=90
            )
            if result.success and result.output:
                return self._parse_verdict(result.output)
        except Exception as e:
            logger.warning(f"Verification LLM call failed: {e}")

        # 降级：无法验证时给出保守的 PARTIAL
        return VerificationVerdict(
            verdict="PARTIAL",
            confidence=0.3,
            reasoning="Verification unavailable (LLM call failed)",
            suggestions=["Manual review recommended"],
        )

    def _parse_verdict(self, response: str) -> VerificationVerdict:
        """解析 LLM 验证响应"""
        data = extract_json(response)
        if data:
            verdict_str = data.get("verdict", "PARTIAL").upper()
            if verdict_str not in ("PASS", "FAIL", "PARTIAL"):
                verdict_str = "PARTIAL"

            return VerificationVerdict(
                verdict=verdict_str,
                confidence=float(data.get("confidence", 0.5)),
                evidence=data.get("evidence", []),
                vulnerabilities=data.get("vulnerabilities", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
                tested_aspects=data.get("tested_aspects", []),
            )
        # JSON extraction failed — infer from text
        return self._infer_verdict(response)

    def _infer_verdict(self, text: str) -> VerificationVerdict:
        """从非结构化文本推断验证结果"""
        text_lower = text.lower()

        fail_signals = ["fail", "vulnerability", "bug", "error", "incorrect", "broken", "missing"]
        pass_signals = ["pass", "correct", "complete", "valid", "good", "secure"]

        fail_count = sum(1 for s in fail_signals if s in text_lower)
        pass_count = sum(1 for s in pass_signals if s in text_lower)

        if fail_count > pass_count:
            verdict = "FAIL"
        elif pass_count > fail_count and fail_count == 0:
            verdict = "PASS"
        else:
            verdict = "PARTIAL"

        return VerificationVerdict(
            verdict=verdict,
            confidence=0.4,
            reasoning=text[:500],
            suggestions=["Automated inference — manual review recommended"],
        )
