"""
Evaluator - 协调者智能审阅

不再是打分机器，而是一个理解输出内容、自主决策的审阅者。
用 LLM 理解 Agent 输出 → 产出 ReviewVerdict（行动计划）
"""
import json
import logging
from typing import Optional, List

from .task_dag import SubTask, EvaluationResult, ReviewVerdict, TaskDAG
from .json_extract import extract_json
from .orchestrator_prompts import EVALUATION_PROMPT, COORDINATOR_REVIEW_PROMPT

logger = logging.getLogger(__name__)


class QualityEvaluator:
    """
    协调者审阅器

    两种模式：
    1. review() — 新模式：LLM 语义理解 + 行动决策，返回 ReviewVerdict
    2. evaluate() — 旧模式（向后兼容）：返回 EvaluationResult
    """

    def __init__(self, agent_pool):
        self.pool = agent_pool

    # ==================== 新模式：智能审阅 ====================

    async def review(
        self,
        subtask: SubTask,
        result_output: str,
        result_success: bool,
        goal: str,
        dag: Optional[TaskDAG] = None,
        previous_context: str = "",
    ) -> ReviewVerdict:
        """
        协调者审阅 — LLM 理解输出并产出行动计划

        即使 Agent 执行失败（exit code != 0），也让 LLM 审阅输出，
        因为失败的输出中可能包含有用信息（错误日志、部分结果等）。
        """
        # 构建审阅上下文
        remaining_plan = ""
        if dag:
            pending = [st for st in dag.subtasks.values() if st.status == "pending"]
            if pending:
                remaining_plan = "\n".join(
                    f"- [{st.id}] {st.description[:120]}" for st in pending
                )
            else:
                remaining_plan = "(no remaining subtasks)"

        output_text = result_output or ""
        if not result_success:
            output_text = f"[AGENT EXECUTION FAILED]\n{output_text}"

        # 调用 LLM 进行智能审阅
        try:
            return await self._llm_review(
                subtask=subtask,
                output_text=output_text,
                goal=goal,
                previous_context=previous_context,
                remaining_plan=remaining_plan,
            )
        except Exception as e:
            logger.warning(f"LLM review failed, using fallback: {e}")
            return self._fallback_review(result_output, result_success)

    async def _llm_review(
        self,
        subtask: SubTask,
        output_text: str,
        goal: str,
        previous_context: str,
        remaining_plan: str,
    ) -> ReviewVerdict:
        """调用 LLM 进行语义审阅"""
        # 保留输出完整性 — 不做硬截断，让 LLM 自己判断重要性
        # 仅在极长时截取头尾
        if len(output_text) > 8000:
            output_text = (
                output_text[:5000]
                + "\n\n... [middle section omitted for brevity] ...\n\n"
                + output_text[-2000:]
            )

        prompt = COORDINATOR_REVIEW_PROMPT.format(
            goal=goal,
            subtask_id=subtask.id,
            task_description=subtask.description,
            agent_type=subtask.agent_type,
            agent_output=output_text,
            previous_context=previous_context or "(first subtask, no previous context)",
            remaining_plan=remaining_plan or "(last subtask)",
        )

        result = await self.pool.execute("claude", prompt, "/tmp", timeout=90)

        if not result.success:
            return self._fallback_review(output_text, False)

        return self._parse_review(result.output)

    def _parse_review(self, response: str) -> ReviewVerdict:
        """解析 LLM 审阅响应"""
        data = extract_json(response)
        if data:
            return ReviewVerdict(
                understanding=data.get("understanding", ""),
                usable_parts=data.get("usable_parts", []),
                problematic_parts=data.get("problematic_parts", []),
                decision=data.get("decision", "proceed"),
                reasoning=data.get("reasoning", ""),
                forward_context=data.get("forward_context", ""),
                rework_instructions=data.get("rework_instructions", ""),
                rework_agent=data.get("rework_agent"),
                new_subtasks=data.get("new_subtasks"),
                plan_adjustments=data.get("plan_adjustments"),
                goal_progress=data.get("goal_progress", ""),
                ready_for_next=data.get("ready_for_next", True),
            )
        # 从非结构化响应中推断
        return self._infer_from_text(response)

    def _infer_from_text(self, text: str) -> ReviewVerdict:
        """从非结构化文本推断审阅结果"""
        text_lower = text.lower()
        has_problems = any(w in text_lower for w in ["error", "fail", "wrong", "incorrect", "issue"])
        has_positive = any(w in text_lower for w in ["success", "correct", "good", "complete", "done"])

        if has_positive and not has_problems:
            decision = "proceed"
        elif has_problems and has_positive:
            decision = "partial_rework"
        elif has_problems:
            decision = "rework"
        else:
            decision = "proceed"

        return ReviewVerdict(
            understanding=text[:300],
            decision=decision,
            reasoning="Inferred from unstructured LLM response",
            forward_context=text[:500] if decision == "proceed" else "",
            rework_instructions=text[:500] if "rework" in decision else "",
        )

    def _fallback_review(self, output: str, success: bool) -> ReviewVerdict:
        """降级审阅 — LLM 不可用时的最后手段"""
        if success:
            return ReviewVerdict(
                understanding="Agent completed execution (fallback: no LLM review available)",
                usable_parts=["Full output available"],
                decision="proceed",
                reasoning="LLM review unavailable; agent reported success",
                forward_context=(output or "")[:2000],
                ready_for_next=True,
            )
        else:
            return ReviewVerdict(
                understanding="Agent execution failed (fallback: no LLM review available)",
                problematic_parts=["Execution failed — output may contain error details"],
                decision="rework",
                reasoning="LLM review unavailable; agent reported failure",
                rework_instructions="Retry the task. Previous attempt failed.",
                forward_context="",
                ready_for_next=False,
            )

    # ==================== 旧模式（向后兼容） ====================

    async def evaluate(
        self,
        subtask: SubTask,
        result_output: str,
        result_success: bool,
        goal_context: str = "",
    ) -> EvaluationResult:
        """旧接口 — 返回 EvaluationResult（向后兼容）"""
        verdict = await self.review(
            subtask=subtask,
            result_output=result_output,
            result_success=result_success,
            goal=goal_context,
        )
        return verdict.to_evaluation_result()
