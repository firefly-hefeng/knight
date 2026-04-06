"""
Orchestrator - 编排系统的核心大脑

实现 Plan → Execute → Evaluate 循环
LLM 是大脑，代码是基础设施
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional, List, Tuple

from .task_dag import (
    TaskDAG, SubTask, EvaluationResult, ReviewVerdict, AttemptRecord,
    OrchestrationConfig, OrchestrationResult,
)
from .evaluator import QualityEvaluator
from .context_manager import ContextManager
from .orchestrator_prompts import PLANNING_PROMPT, SYNTHESIS_PROMPT, REPLAN_PROMPT
from .state_manager import StateManager
from .signal import Signal
from .feedback import FeedbackManager, FeedbackRequest
from .json_extract import extract_json

logger = logging.getLogger(__name__)


class OrchestratorLoop:
    """
    编排主循环 — Knight 系统的"人类专家大脑"

    职责：
    1. Think  — 调用 LLM 将目标分解为 TaskDAG
    2. Execute — 并行执行就绪子任务
    3. Evaluate — LLM 评估输出质量
    4. Iterate — 失败时分析原因、调整策略、重试
    5. Synthesize — 汇总所有子任务结果为最终输出
    """

    def __init__(
        self,
        agent_pool,
        state: StateManager,
        context_mgr: ContextManager,
        evaluator: QualityEvaluator,
        task_signal: Optional[Signal] = None,
    ):
        self.pool = agent_pool
        self.state = state
        self.context = context_mgr
        self.evaluator = evaluator
        self.signal = task_signal
        # Phase 3 会注入 iteration_engine 和 feedback_mgr
        self.iteration_engine = None
        self.feedback_mgr = None
        self.verifier = None        # Phase D: VerificationAgent (optional)

    async def run(
        self,
        goal: str,
        work_dir: str,
        config: OrchestrationConfig,
        parent_task_id: str,
    ) -> OrchestrationResult:
        """主编排循环"""
        start_time = time.time()
        total_calls = 0

        # Phase 1: Think — 分解目标
        self._update_parent(parent_task_id, "running", progress=5, log="Orchestrator: planning...")
        dag = await self._think(goal, work_dir, parent_task_id)

        if not dag or not dag.subtasks:
            # 降级：无法分解，作为单任务执行
            return await self._fallback_single(goal, work_dir, parent_task_id, start_time)

        # 持久化 DAG
        self._save_dag(parent_task_id, dag)
        self._update_parent(parent_task_id, "running", progress=10,
                           log=f"Plan: {len(dag.subtasks)} subtasks, v{dag.version}")

        # Phase 2: Execute → Evaluate 循环
        rounds = 0
        while not dag.is_complete() and rounds < config.max_rounds:
            rounds += 1

            if dag.has_failed_terminal():
                self._update_parent(parent_task_id, "running",
                                   log=f"Round {rounds}: terminal failure detected")
                break

            ready = dag.get_ready_subtasks()
            if not ready:
                # 死锁检测：没有就绪任务但 DAG 未完成
                self._update_parent(parent_task_id, "running",
                                   log=f"Round {rounds}: no ready tasks, possible deadlock")
                break

            self._update_parent(parent_task_id, "running",
                               progress=10 + int(dag.progress * 0.8),
                               log=f"Round {rounds}: executing {len(ready)} subtask(s)")

            # 检查点处理
            checkpoint_tasks = [st for st in ready if st.is_checkpoint]
            if checkpoint_tasks and self.feedback_mgr and config.enable_checkpoints:
                for cp_task in checkpoint_tasks:
                    should_proceed = await self._checkpoint(
                        "approval_gate", cp_task, dag, parent_task_id, config
                    )
                    if not should_proceed:
                        # 人类选择中止
                        self._update_parent(parent_task_id, "cancelled",
                                           error="Aborted at checkpoint by human")
                        return OrchestrationResult(
                            success=False, final_output="Aborted at checkpoint",
                            dag=dag, total_duration_ms=int((time.time() - start_time) * 1000),
                        )

            # 并行执行就绪子任务
            results = await self._execute_ready(ready, dag, work_dir)
            total_calls += len(results)

            # 协调者审阅 — LLM 理解输出并决定下一步
            for subtask, task_result in results:
                output = task_result.output if task_result else ""
                success = task_result.success if task_result else False

                # Layer 1: 全量输出持久化到磁盘
                if output:
                    self.context.store_raw_output(subtask.id, output)
                    self.context.extract_artifacts_from_output(subtask.id, output)

                # 获取前序上下文
                prev_context = ""
                for dep_id in subtask.dependencies:
                    dep = dag.subtasks.get(dep_id)
                    if dep and dep.result_summary:
                        prev_context += f"[{dep_id}]: {dep.result_summary}\n"

                # LLM 审阅
                verdict = await self.evaluator.review(
                    subtask=subtask,
                    result_output=output,
                    result_success=success,
                    goal=goal,
                    dag=dag,
                    previous_context=prev_context,
                )
                total_calls += 1
                subtask.evaluation = verdict.to_evaluation_result()

                # 根据 LLM 的决策执行（不再是 if passed/else）
                decision = verdict.decision

                if decision == "proceed":
                    # 高风险任务：可选对抗性验证
                    if (subtask.risk_level == "high" and self.verifier
                            and subtask.attempts < 2):
                        vv = await self.verifier.verify(subtask, output, goal)
                        total_calls += 1
                        if vv.verdict == "FAIL":
                            # 验证器推翻了审阅器的 proceed 决定
                            override = vv.to_review_verdict()
                            decision = override.decision
                            verdict = override
                            self._update_parent(parent_task_id, "running",
                                               log=f"  [{subtask.id}] verifier override: {vv.reasoning[:80]}")
                            # 跳到下面的 rework 分支
                        elif vv.verdict == "PARTIAL":
                            self._update_parent(parent_task_id, "running",
                                               log=f"  [{subtask.id}] verifier: PARTIAL — {'; '.join(vv.suggestions[:2])}")

                if decision == "proceed":
                    # 输出可用 — 使用审阅者精炼的 forward_context 传递给下游
                    # 这比截断原文好得多：LLM 已经理解了输出并提取了关键信息
                    forward_ctx = verdict.forward_context
                    if not forward_ctx:
                        # 审阅者没有提供 forward_context，走压缩管线
                        forward_ctx = await self.context.summarize_result(subtask.id, output)
                    dag.mark_complete(subtask.id, output, forward_ctx)
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] proceed: {verdict.understanding[:80]}")

                    # 应用计划调整建议
                    if verdict.plan_adjustments and config.enable_dynamic_replan:
                        dag = await self._maybe_replan(dag, subtask)

                elif decision == "partial_rework":
                    # 部分可用 — 保存可用部分，但对有问题的部分创建修复任务
                    dag.mark_complete(subtask.id, output, verdict.forward_context)
                    if verdict.rework_instructions and subtask.attempts < subtask.max_retries:
                        fix_id = f"{subtask.id}_fix"
                        fix_task = SubTask(
                            id=fix_id,
                            description=verdict.rework_instructions,
                            agent_type=verdict.rework_agent or subtask.agent_type,
                            acceptance_criteria=subtask.acceptance_criteria,
                            risk_level=subtask.risk_level,
                        )
                        dag.add_subtask(fix_task, after=[subtask.id])
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] partial: {verdict.reasoning[:80]}")

                elif decision == "rework":
                    # 需要重做
                    dag.mark_failed(subtask.id, verdict.reasoning)
                    if subtask.attempts < subtask.max_retries:
                        if verdict.rework_instructions:
                            # ReviewVerdict 提供了具体指令 — 直接使用
                            dag.reset_subtask(subtask.id)
                            subtask.description = verdict.rework_instructions
                            if verdict.rework_agent:
                                subtask.agent_type = verdict.rework_agent
                            self.context.record_failed_approach(subtask.id, verdict.reasoning)
                        elif self.iteration_engine:
                            # 没有具体指令 — 委托给 IterationEngine 做深度分析
                            dag = await self.iteration_engine.handle_failure(
                                dag, subtask, subtask.evaluation or verdict.to_evaluation_result()
                            )
                        else:
                            # 最后手段：带错误上下文重试
                            dag.reset_subtask(subtask.id)
                            subtask.description += f"\n\n[Previous attempt failed: {verdict.reasoning}]"
                            self.context.record_failed_approach(subtask.id, verdict.reasoning)
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] rework: {verdict.reasoning[:80]}")

                elif decision == "decompose":
                    # 任务太大 — 用 LLM 设计的子任务替换
                    dag.snapshot()
                    subtask.status = "skipped"
                    if verdict.new_subtasks:
                        for st_data in verdict.new_subtasks:
                            new_st = SubTask(
                                id=st_data.get("id", f"{subtask.id}_{len(dag.subtasks)}"),
                                description=st_data["description"],
                                agent_type=st_data.get("agent_type", subtask.agent_type),
                                acceptance_criteria=st_data.get("acceptance_criteria", []),
                                dependencies=st_data.get("dependencies", subtask.dependencies),
                                risk_level=st_data.get("risk_level", subtask.risk_level),
                            )
                            dag.add_subtask(new_st, after=new_st.dependencies)
                        # 更新依赖此任务的后续任务
                        last_new_id = verdict.new_subtasks[-1].get("id", subtask.id)
                        for st in dag.subtasks.values():
                            if subtask.id in st.dependencies:
                                st.dependencies.remove(subtask.id)
                                st.dependencies.append(last_new_id)
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] decomposed into {len(verdict.new_subtasks or [])} subtasks")

                elif decision == "escalate":
                    # 需要人类判断
                    if self.feedback_mgr:
                        from .feedback import FeedbackRequest
                        req = FeedbackRequest(
                            task_id=parent_task_id,
                            checkpoint_type="escalation",
                            question=f"Agent needs help with [{subtask.id}]: {verdict.reasoning}",
                            context=verdict.understanding,
                            dag_snapshot=dag.to_json(),
                        )
                        await self.feedback_mgr.request_feedback(req)
                        resp = await self.feedback_mgr.wait_for_feedback(parent_task_id, timeout=1800)
                        if resp and resp.action == "abort":
                            break
                        elif resp and resp.message:
                            dag.reset_subtask(subtask.id)
                            subtask.description = resp.message
                    else:
                        dag.mark_failed(subtask.id, f"Escalated: {verdict.reasoning}")
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] escalated: {verdict.reasoning[:80]}")

                elif decision == "abort":
                    subtask.status = "skipped"
                    self._update_parent(parent_task_id, "running",
                                       log=f"  [{subtask.id}] aborted: {verdict.reasoning[:80]}")

            # 更新 DAG 持久化
            self._save_dag(parent_task_id, dag)

            # 全局超时检查
            elapsed = time.time() - start_time
            if elapsed > config.global_timeout_seconds:
                self._update_parent(parent_task_id, "running",
                                   log=f"Global timeout ({config.global_timeout_seconds}s) reached")
                break

        # Phase 3: Synthesize
        self._update_parent(parent_task_id, "running", progress=95, log="Synthesizing final output...")
        final_output = await self._synthesize(dag, goal)
        total_calls += 1

        duration_ms = int((time.time() - start_time) * 1000)
        success = dag.is_complete()

        status = "completed" if success else "failed"
        self._update_parent(parent_task_id, status, progress=100 if success else dag.progress,
                           result=final_output if success else None,
                           error=None if success else "Not all subtasks completed",
                           log=f"Done: {status} in {duration_ms}ms, {total_calls} agent calls")

        return OrchestrationResult(
            success=success,
            final_output=final_output,
            dag=dag,
            total_duration_ms=duration_ms,
            total_cost_usd=dag.total_cost,
            total_agent_calls=total_calls,
            summary=f"{'Completed' if success else 'Partial'}: {dag.progress}% done, "
                    f"{len(dag.subtasks)} subtasks, {dag.total_attempts} attempts",
        )

    # ==================== Think ====================

    async def _think(self, goal: str, work_dir: str, parent_task_id: str) -> Optional[TaskDAG]:
        """调用 LLM 将目标分解为 TaskDAG"""
        prompt = PLANNING_PROMPT.format(goal=goal, work_dir=work_dir)

        try:
            result = await self.pool.execute("claude", prompt, work_dir, timeout=120)
            if not result.success:
                logger.error(f"Planning failed: {result.error}")
                return None
            return self._parse_plan(result.output, parent_task_id, goal)
        except Exception as e:
            logger.error(f"Planning exception: {e}")
            return None

    def _parse_plan(self, response: str, parent_task_id: str, goal: str) -> Optional[TaskDAG]:
        """解析 LLM 规划响应为 TaskDAG"""
        try:
            data = extract_json(response)
            if not data:
                logger.error("Failed to extract JSON from planning response")
                return None

            subtasks_data = data.get("subtasks", [])
            edges_data = data.get("edges", [])

            if not subtasks_data:
                return None

            dag = TaskDAG(id=parent_task_id, goal=goal)

            for st_data in subtasks_data:
                subtask = SubTask(
                    id=st_data["id"],
                    description=st_data["description"],
                    agent_type=st_data.get("agent_type", "claude"),
                    acceptance_criteria=st_data.get("acceptance_criteria", []),
                    dependencies=st_data.get("dependencies", []),
                    risk_level=st_data.get("risk_level", "low"),
                    is_checkpoint=st_data.get("is_checkpoint", False),
                )
                dag.subtasks[subtask.id] = subtask
                if subtask.is_checkpoint:
                    dag.checkpoints.append(subtask.id)

            dag.edges = [tuple(e) for e in edges_data]
            return dag

        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.error(f"Failed to parse plan: {e}")
            return None

    # ==================== Execute ====================

    async def _execute_ready(
        self, ready: List[SubTask], dag: TaskDAG, work_dir: str
    ) -> List[Tuple[SubTask, object]]:
        """并行执行所有就绪子任务"""
        async def _run_one(subtask: SubTask):
            dag.mark_running(subtask.id)
            prompt = await self.context.build_subtask_prompt(subtask, dag)
            start = time.time()
            try:
                result = await self.pool.execute(subtask.agent_type, prompt, work_dir, timeout=300)
                duration = int((time.time() - start) * 1000)

                # 记录尝试
                attempt = AttemptRecord(
                    attempt_number=subtask.attempts + 1,
                    agent_type=subtask.agent_type,
                    prompt_used=prompt[:2000],
                    result_output=result.output[:2000] if result.output else "",
                    result_success=result.success,
                    duration_ms=duration,
                    cost_usd=result.cost_usd,
                )
                subtask.attempt_history.append(attempt)
                return subtask, result
            except Exception as e:
                duration = int((time.time() - start) * 1000)
                attempt = AttemptRecord(
                    attempt_number=subtask.attempts + 1,
                    agent_type=subtask.agent_type,
                    prompt_used=prompt[:2000],
                    result_output=str(e),
                    result_success=False,
                    duration_ms=duration,
                )
                subtask.attempt_history.append(attempt)
                return subtask, None

        results = await asyncio.gather(*[_run_one(st) for st in ready], return_exceptions=False)
        return list(results)

    # ==================== Replan ====================

    async def _maybe_replan(self, dag: TaskDAG, completed: SubTask) -> TaskDAG:
        """完成一个子任务后，检查是否需要调整剩余计划"""
        remaining = [st for st in dag.subtasks.values() if st.status == "pending"]
        if not remaining:
            return dag

        try:
            remaining_desc = "\n".join(f"- [{st.id}] {st.description}" for st in remaining)
            prompt = REPLAN_PROMPT.format(
                goal=dag.goal,
                remaining_plan=remaining_desc,
                completed_task=f"[{completed.id}] {completed.description}",
                completed_result=(completed.result_summary or completed.result or "")[:1000],
            )
            result = await self.pool.execute("claude", prompt, "/tmp", timeout=60)
            if not result.success:
                return dag

            data = extract_json(result.output)
            if not data or not data.get("changed", False):
                return dag

            # 应用变更
            dag.snapshot()  # 保存旧版本

            # 移除被删除的子任务
            for removed_id in data.get("removed_subtask_ids", []):
                if removed_id in dag.subtasks and dag.subtasks[removed_id].status == "pending":
                    dag.remove_subtask(removed_id)

            # 添加新子任务
            for st_data in data.get("updated_subtasks", []):
                new_st = SubTask(
                    id=st_data["id"],
                    description=st_data["description"],
                    agent_type=st_data.get("agent_type", "claude"),
                    acceptance_criteria=st_data.get("acceptance_criteria", []),
                    dependencies=st_data.get("dependencies", []),
                    risk_level=st_data.get("risk_level", "low"),
                    is_checkpoint=st_data.get("is_checkpoint", False),
                )
                dag.add_subtask(new_st, after=st_data.get("dependencies"))

            for edge in data.get("new_edges", []):
                dag.edges.append(tuple(edge))

            logger.info(f"Replanned: {data.get('reason', 'no reason given')}")
            return dag

        except Exception as e:
            logger.warning(f"Replan failed (keeping current plan): {e}")
            return dag

    # ==================== Synthesize ====================

    async def _synthesize(self, dag: TaskDAG, goal: str) -> str:
        """汇总所有子任务结果为最终输出"""
        results_text = []
        for st in dag.subtasks.values():
            status_icon = "✓" if st.status == "completed" else "✗"
            summary = st.result_summary or (st.result[:300] if st.result else "no output")
            results_text.append(f"[{status_icon} {st.id}] {st.description}\n{summary}")

        prompt = SYNTHESIS_PROMPT.format(
            goal=goal,
            subtask_results="\n\n".join(results_text),
        )

        try:
            result = await self.pool.execute("claude", prompt, "/tmp", timeout=120)
            if result.success and result.output:
                return result.output
        except Exception as e:
            logger.warning(f"Synthesis LLM call failed: {e}")

        # 降级：简单拼接
        return "\n\n---\n\n".join(
            f"## {st.description}\n{st.result or 'No output'}"
            for st in dag.subtasks.values()
            if st.status == "completed"
        )

    # ==================== Fallback ====================

    async def _checkpoint(
        self, checkpoint_type: str, subtask: SubTask, dag: TaskDAG,
        parent_task_id: str, config: OrchestrationConfig
    ) -> bool:
        """
        检查点暂停：
        1. 发送反馈请求
        2. 等待人类响应
        3. 返回 True 继续 / False 中止
        """
        if not self.feedback_mgr:
            return True

        # 判断是否需要检查点
        if config.checkpoint_mode == "never":
            return True
        if config.checkpoint_mode == "on_high_risk" and subtask.risk_level != "high":
            return True

        request = FeedbackRequest(
            task_id=parent_task_id,
            checkpoint_type=checkpoint_type,
            question=f"Approve execution of: {subtask.description[:200]}",
            context=f"Agent: {subtask.agent_type}, Risk: {subtask.risk_level}",
            options=["approve", "reject", "modify", "abort"],
            dag_snapshot=dag.to_json(),
        )
        await self.feedback_mgr.request_feedback(request)
        response = await self.feedback_mgr.wait_for_feedback(parent_task_id, timeout=3600)

        if not response or response.action == "approve":
            return True
        if response.action == "abort":
            return False
        if response.action == "reject":
            subtask.status = "skipped"
            return True
        if response.action == "modify" and response.message:
            subtask.description = response.message
            return True

        return True

    async def _fallback_single(
        self, goal: str, work_dir: str, parent_task_id: str, start_time: float
    ) -> OrchestrationResult:
        """降级：无法分解时作为单任务直接执行"""
        self._update_parent(parent_task_id, "running", progress=20,
                           log="Fallback: executing as single task")
        try:
            result = await self.pool.execute("claude", goal, work_dir, timeout=300)
            duration = int((time.time() - start_time) * 1000)
            success = result.success
            self._update_parent(
                parent_task_id,
                "completed" if success else "failed",
                progress=100 if success else 0,
                result=result.output if success else None,
                error=result.error if not success else None,
                log=f"Fallback {'completed' if success else 'failed'} in {duration}ms",
            )
            return OrchestrationResult(
                success=success, final_output=result.output or "",
                total_duration_ms=duration, total_cost_usd=result.cost_usd,
                total_agent_calls=1, summary="Fallback single-task execution",
            )
        except Exception as e:
            self._update_parent(parent_task_id, "failed", error=str(e))
            return OrchestrationResult(success=False, final_output="", summary=f"Fallback failed: {e}")

    # ==================== Helpers ====================

    def _update_parent(self, task_id: str, status: str = None, **kwargs):
        """更新父任务状态"""
        if status:
            self.state.update_status(task_id, status, **kwargs)
        if self.signal:
            self.signal.emit(task_id)

    def _save_dag(self, parent_task_id: str, dag: TaskDAG):
        """持久化 DAG 到父任务"""
        task = self.state.get_task(parent_task_id)
        if task:
            task.dag_json = dag.to_json()
            if self.state.persistence:
                self.state.persistence.save_task(task)
                # 保存尝试历史
                for st in dag.subtasks.values():
                    for attempt in st.attempt_history:
                        try:
                            self.state.persistence.save_attempt(
                                parent_task_id=parent_task_id,
                                subtask_id=st.id,
                                attempt_number=attempt.attempt_number,
                                agent_type=attempt.agent_type,
                                prompt_used=attempt.prompt_used[:2000],
                                result_output=attempt.result_output[:2000],
                                result_success=attempt.result_success,
                                evaluation_json=json.dumps(attempt.evaluation.to_dict()) if attempt.evaluation else "",
                                strategy=attempt.strategy_used,
                                duration_ms=attempt.duration_ms,
                                cost_usd=attempt.cost_usd,
                            )
                        except Exception:
                            pass  # 重复插入等容错
