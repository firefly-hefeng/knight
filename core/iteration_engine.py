"""
Iteration Engine - 智能重试与失败恢复

分析失败原因 → 生成修复策略 → 变更 DAG → 重试
替代旧的 error_handler.py 盲重试
"""
import json
import logging
from typing import Optional

from .task_dag import (
    TaskDAG, SubTask, EvaluationResult, FailureAnalysis, RetryStrategy,
)
from .context_manager import ContextManager
from .orchestrator_prompts import FAILURE_ANALYSIS_PROMPT
from .json_extract import extract_json

logger = logging.getLogger(__name__)


class IterationEngine:
    """智能重试引擎 — 分析失败、调整策略、变更 DAG"""

    def __init__(self, agent_pool, context_mgr: ContextManager):
        self.pool = agent_pool
        self.context = context_mgr

    async def handle_failure(
        self, dag: TaskDAG, subtask: SubTask, evaluation: EvaluationResult
    ) -> TaskDAG:
        """
        处理子任务失败：
        1. 分析失败原因
        2. 生成重试策略
        3. 应用策略到 DAG
        """
        if subtask.attempts >= subtask.max_retries:
            logger.info(f"[{subtask.id}] max retries ({subtask.max_retries}) exhausted, escalating")
            subtask.status = "failed"
            return dag

        analysis = await self._analyze_failure(subtask, evaluation)
        strategy = await self._generate_strategy(subtask, analysis)

        logger.info(f"[{subtask.id}] failure: {analysis.root_cause} → strategy: {strategy.action}")

        return await self._apply_strategy(dag, subtask, strategy, analysis)

    async def _analyze_failure(
        self, subtask: SubTask, evaluation: EvaluationResult
    ) -> FailureAnalysis:
        """调用 LLM 分析失败根因"""
        attempt_text = "\n".join(
            f"Attempt {a.attempt_number}: strategy={a.strategy_used}, success={a.result_success}, "
            f"output_preview={a.result_output[:200]}"
            for a in subtask.attempt_history[-3:]
        ) or "No previous attempts"

        prompt = FAILURE_ANALYSIS_PROMPT.format(
            task_description=subtask.description,
            agent_output=(subtask.result or "")[:2000],
            evaluation_result=json.dumps(evaluation.to_dict(), indent=2)[:1000],
            attempt_history=attempt_text,
        )

        try:
            result = await self.pool.execute("claude", prompt, "/tmp", timeout=60)
            if result.success:
                return self._parse_analysis(result.output)
        except Exception as e:
            logger.warning(f"Failure analysis LLM call failed: {e}")

        # 降级：基于评估结果推断
        return self._infer_analysis(evaluation)

    def _parse_analysis(self, response: str) -> FailureAnalysis:
        """解析 LLM 分析响应 — 提取根因 + 建议"""
        data = extract_json(response)
        if data:
            analysis = FailureAnalysis(
                root_cause=data.get("root_cause", "prompt_issue"),
                explanation=data.get("explanation", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
            # 附加 LLM 建议（如果有）
            if data.get("refined_prompt"):
                analysis._refined_prompt = data["refined_prompt"]
            if data.get("new_agent_type") and data["new_agent_type"] != "null":
                analysis._new_agent = data["new_agent_type"]
            return analysis
        return FailureAnalysis(root_cause="prompt_issue", explanation="Parse failed", confidence=0.3)

    def _infer_analysis(self, evaluation: EvaluationResult) -> FailureAnalysis:
        """降级：从评估结果推断失败原因"""
        if evaluation.score > 0.5:
            return FailureAnalysis(root_cause="prompt_issue", explanation="Partial success, prompt needs refinement")
        if "timeout" in " ".join(evaluation.failure_reasons).lower():
            return FailureAnalysis(root_cause="external_failure", explanation="Timeout detected")
        return FailureAnalysis(root_cause="prompt_issue", explanation="Inferred from low score")

    async def _generate_strategy(
        self, subtask: SubTask, analysis: FailureAnalysis
    ) -> RetryStrategy:
        """根据失败分析生成重试策略 — 优先使用 LLM 建议"""
        # 如果 LLM 分析提供了具体建议，直接使用
        if hasattr(analysis, '_llm_suggestion'):
            return analysis._llm_suggestion

        cause = analysis.root_cause

        # LLM 分析的 refined_prompt 如果有就用
        if hasattr(analysis, '_refined_prompt') and analysis._refined_prompt:
            self.context.record_failed_approach(subtask.id, analysis.explanation)
            return RetryStrategy(action="retry_same", refined_prompt=analysis._refined_prompt)

        if hasattr(analysis, '_new_agent') and analysis._new_agent:
            return RetryStrategy(action="retry_different", new_agent_type=analysis._new_agent)

        # 降级：基于分类的简单映射（但用错误上下文丰富 prompt）
        if cause in ("prompt_issue", "missing_context"):
            error_context = f"\n\n[Previous attempt failed: {analysis.explanation}]"
            if subtask.attempt_history:
                last = subtask.attempt_history[-1]
                error_context += f"\n[Last output: {last.result_output[:500]}]"
            self.context.record_failed_approach(subtask.id, analysis.explanation)
            return RetryStrategy(action="retry_same", refined_prompt=subtask.description + error_context)

        if cause == "agent_limitation":
            new_agent = "kimi" if subtask.agent_type == "claude" else "claude"
            return RetryStrategy(action="retry_different", new_agent_type=new_agent)

        if cause == "task_too_complex":
            return RetryStrategy(action="decompose")

        if cause == "external_failure":
            return RetryStrategy(action="retry_same")

        return RetryStrategy(action="retry_same")

    async def _apply_strategy(
        self, dag: TaskDAG, subtask: SubTask, strategy: RetryStrategy, analysis: FailureAnalysis
    ) -> TaskDAG:
        """将策略应用到 DAG"""
        action = strategy.action

        if action == "retry_same":
            dag.reset_subtask(subtask.id)
            if strategy.refined_prompt:
                subtask.description = strategy.refined_prompt
            if strategy.additional_context:
                subtask.description += strategy.additional_context
            return dag

        if action == "retry_different":
            dag.reset_subtask(subtask.id)
            if strategy.new_agent_type:
                subtask.agent_type = strategy.new_agent_type
            return dag

        if action == "decompose":
            dag.snapshot()
            subtask.status = "skipped"

            # LLM 设计分解方案（现在正确地在 async 上下文中调用）
            new_subtasks = await self._llm_decompose(subtask, analysis)

            if new_subtasks:
                last_id = None
                for new_st in new_subtasks:
                    dag.add_subtask(new_st, after=new_st.dependencies or subtask.dependencies)
                    last_id = new_st.id
                # 将原来依赖此任务的后续任务改为依赖最后一个新子任务
                if last_id:
                    for st in dag.subtasks.values():
                        if subtask.id in st.dependencies:
                            st.dependencies.remove(subtask.id)
                            st.dependencies.append(last_id)
            return dag

        if action in ("escalate", "skip"):
            subtask.status = "failed" if action == "escalate" else "skipped"
            return dag

        dag.reset_subtask(subtask.id)
        return dag

    async def _llm_decompose(self, subtask: SubTask, analysis: FailureAnalysis) -> list:
        """调用 LLM 设计分解方案"""
        prompt = (
            f"The following task is too complex for a single agent call. "
            f"Break it into 2-3 smaller, specific subtasks.\n\n"
            f"Task: {subtask.description}\n\n"
            f"Previous failure: {analysis.explanation}\n\n"
            f"Respond with ONLY valid JSON:\n"
            f'{{"subtasks": [{{"id": "...", "description": "...", '
            f'"agent_type": "claude|kimi", "dependencies": []}}]}}'
        )
        try:
            result = await self.pool.execute("claude", prompt, "/tmp", timeout=60)
            if result.success and result.output:
                data = extract_json(result.output)
                if data:
                    return [
                        SubTask(
                            id=st_data.get("id", f"{subtask.id}_{chr(97 + i)}"),
                            description=st_data["description"],
                            agent_type=st_data.get("agent_type", subtask.agent_type),
                            acceptance_criteria=subtask.acceptance_criteria,
                            dependencies=st_data.get("dependencies", []),
                            risk_level=subtask.risk_level,
                        )
                        for i, st_data in enumerate(data.get("subtasks", []))
                    ]
        except Exception as e:
            logger.warning(f"LLM decompose failed: {e}")
        return []
