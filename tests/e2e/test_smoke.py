"""
End-to-end smoke test — full orchestration cycle with mock agents.

Tests the complete flow: Plan → Execute → Evaluate → Retry → Complete
Uses mock AgentPool to avoid real LLM calls while exercising all system components.
"""
import asyncio
import json
import os
import sys
import tempfile
import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, patch

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.state_manager import StateManager, TaskState
from core.context_manager import ContextManager
from core.evaluator import QualityEvaluator
from core.iteration_engine import IterationEngine
from core.orchestrator import OrchestratorLoop
from core.feedback import FeedbackManager, FeedbackResponse
from core.task_dag import OrchestrationConfig, TaskDAG, SubTask
from core.signal import Signal


@dataclass
class MockTaskResult:
    """Mock agent execution result."""
    success: bool
    output: str
    error: Optional[str] = None
    cost_usd: float = 0.01
    duration_ms: int = 100


class MockAgentPool:
    """
    Mock AgentPool that returns scripted responses.

    Each call to execute() pops from a response queue.
    If the queue is empty, returns a default success response.
    """

    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self._call_log = []

    async def execute(self, agent_type, prompt, work_dir, timeout=300):
        self._call_log.append({"agent_type": agent_type, "prompt": prompt[:200]})
        if self._responses:
            return self._responses.pop(0)
        return MockTaskResult(success=True, output="Default mock output", cost_usd=0.01)

    @property
    def call_count(self):
        return len(self._call_log)


# ==================== Smoke Test Scenarios ====================


class TestSmokeHappyPath:
    """Scenario: Task decomposes into 2 subtasks, both succeed on first attempt."""

    @pytest.mark.asyncio
    async def test_full_cycle_happy_path(self):
        state = StateManager(enable_persistence=False)
        task = TaskState(
            task_id="smoke-1", status="running",
            prompt="Build a calculator", agent_type="claude", work_dir="/tmp"
        )
        state.create_task(task)

        # Script the mock responses:
        # Call 1: Planning — LLM decomposes into 2 subtasks
        plan_response = MockTaskResult(
            success=True,
            output=json.dumps({
                "subtasks": [
                    {"id": "s1", "description": "Write calculator functions", "agent_type": "claude"},
                    {"id": "s2", "description": "Write unit tests", "agent_type": "claude", "dependencies": ["s1"]},
                ],
                "edges": [["s1", "s2"]],
            }),
        )
        # Call 2: Execute s1
        exec_s1 = MockTaskResult(success=True, output="def add(a, b): return a + b")
        # Call 3: Evaluate s1 — proceed
        eval_s1 = MockTaskResult(
            success=True,
            output=json.dumps({
                "understanding": "Clean calculator implementation",
                "usable_parts": ["add function"],
                "decision": "proceed",
                "reasoning": "All criteria met",
                "forward_context": "def add(a, b): return a + b",
                "goal_progress": "50%",
                "ready_for_next": True,
            }),
        )
        # Call 4: Execute s2
        exec_s2 = MockTaskResult(success=True, output="def test_add(): assert add(1, 2) == 3")
        # Call 5: Evaluate s2 — proceed
        eval_s2 = MockTaskResult(
            success=True,
            output=json.dumps({
                "understanding": "Good test coverage",
                "decision": "proceed",
                "forward_context": "test_add passes",
                "goal_progress": "100%",
                "ready_for_next": True,
            }),
        )
        # Call 6: Synthesize
        synthesis = MockTaskResult(
            success=True,
            output="Calculator module with add() and tests. All tests pass."
        )

        pool = MockAgentPool([plan_response, exec_s1, eval_s1, exec_s2, eval_s2, synthesis])
        ctx = ContextManager(state, agent_pool=pool, storage_dir=tempfile.mkdtemp())
        evaluator = QualityEvaluator(agent_pool=pool)
        signal = Signal()

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
            task_signal=signal,
        )

        config = OrchestrationConfig(
            enable_checkpoints=False,
            enable_dynamic_replan=False,
        )
        result = await orch.run(
            goal="Build a calculator",
            work_dir="/tmp",
            config=config,
            parent_task_id="smoke-1",
        )

        assert result.success is True
        assert "Calculator" in result.final_output
        assert result.total_agent_calls >= 4  # plan + 2 exec + 2 eval + synth
        assert result.dag is not None
        assert result.dag.progress == 100

        # Verify parent task state
        t = state.get_task("smoke-1")
        assert t.status == "completed"
        assert t.dag_json is not None


class TestSmokeRetryScenario:
    """Scenario: First subtask fails, gets retried with refined prompt, then succeeds."""

    @pytest.mark.asyncio
    async def test_retry_on_rework(self):
        state = StateManager(enable_persistence=False)
        state.create_task(TaskState(
            task_id="smoke-2", status="running",
            prompt="Write a parser", agent_type="claude", work_dir="/tmp"
        ))

        plan = MockTaskResult(
            success=True,
            output=json.dumps({
                "subtasks": [
                    {"id": "s1", "description": "Implement parser", "agent_type": "claude"},
                ],
                "edges": [],
            }),
        )
        # Execute s1: first attempt — bad output
        exec_s1_bad = MockTaskResult(success=True, output="# TODO: implement parser")
        # Evaluate s1: rework with instructions
        eval_s1_rework = MockTaskResult(
            success=True,
            output=json.dumps({
                "understanding": "Agent only wrote a placeholder comment",
                "problematic_parts": ["No actual implementation"],
                "decision": "rework",
                "reasoning": "Only a TODO comment, no code",
                "rework_instructions": "Write a complete JSON parser that handles objects, arrays, strings, numbers, booleans, and null",
            }),
        )
        # Execute s1: second attempt — good output
        exec_s1_good = MockTaskResult(
            success=True,
            output="def parse_json(text): ..."
        )
        # Evaluate s1: proceed
        eval_s1_ok = MockTaskResult(
            success=True,
            output=json.dumps({
                "understanding": "Complete parser implementation",
                "decision": "proceed",
                "forward_context": "parse_json function implemented",
                "goal_progress": "100%",
            }),
        )
        # Synthesize
        synthesis = MockTaskResult(success=True, output="JSON parser implemented successfully.")

        pool = MockAgentPool([plan, exec_s1_bad, eval_s1_rework, exec_s1_good, eval_s1_ok, synthesis])
        ctx = ContextManager(state, pool, tempfile.mkdtemp())
        evaluator = QualityEvaluator(pool)

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
        )

        result = await orch.run(
            goal="Write a parser",
            work_dir="/tmp",
            config=OrchestrationConfig(enable_checkpoints=False, enable_dynamic_replan=False),
            parent_task_id="smoke-2",
        )

        assert result.success is True
        assert result.dag.total_attempts >= 2  # at least 2 attempts on s1


class TestSmokeFallbackSingle:
    """Scenario: Planning fails, system falls back to single-task execution."""

    @pytest.mark.asyncio
    async def test_fallback_on_plan_failure(self):
        state = StateManager(enable_persistence=False)
        state.create_task(TaskState(
            task_id="smoke-3", status="running",
            prompt="Simple task", agent_type="claude", work_dir="/tmp"
        ))

        # Planning fails
        plan_fail = MockTaskResult(success=False, output="", error="LLM unavailable")
        # Fallback execution succeeds
        fallback_exec = MockTaskResult(success=True, output="Task done directly.")

        pool = MockAgentPool([plan_fail, fallback_exec])
        ctx = ContextManager(state, pool, tempfile.mkdtemp())
        evaluator = QualityEvaluator(pool)

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
        )

        result = await orch.run(
            goal="Simple task",
            work_dir="/tmp",
            config=OrchestrationConfig(),
            parent_task_id="smoke-3",
        )

        assert result.success is True
        assert "Fallback" in result.summary
        assert result.total_agent_calls == 1  # only the fallback call

        t = state.get_task("smoke-3")
        assert t.status == "completed"


class TestSmokeParallelExecution:
    """Scenario: Two independent subtasks execute in parallel."""

    @pytest.mark.asyncio
    async def test_parallel_subtasks(self):
        state = StateManager(enable_persistence=False)
        state.create_task(TaskState(
            task_id="smoke-4", status="running",
            prompt="Build frontend and backend", agent_type="claude", work_dir="/tmp"
        ))

        plan = MockTaskResult(
            success=True,
            output=json.dumps({
                "subtasks": [
                    {"id": "frontend", "description": "Build React UI", "agent_type": "claude"},
                    {"id": "backend", "description": "Build API server", "agent_type": "kimi"},
                    {"id": "integrate", "description": "Wire frontend to backend",
                     "agent_type": "claude", "dependencies": ["frontend", "backend"]},
                ],
                "edges": [["frontend", "integrate"], ["backend", "integrate"]],
            }),
        )
        # Both frontend and backend execute (parallel — but mock is sequential)
        exec_fe = MockTaskResult(success=True, output="React app built")
        exec_be = MockTaskResult(success=True, output="API server running")
        # Both evaluated
        eval_fe = MockTaskResult(success=True, output=json.dumps({"decision": "proceed", "forward_context": "React ready"}))
        eval_be = MockTaskResult(success=True, output=json.dumps({"decision": "proceed", "forward_context": "API ready"}))
        # Integration
        exec_int = MockTaskResult(success=True, output="Frontend connected to API")
        eval_int = MockTaskResult(success=True, output=json.dumps({"decision": "proceed", "forward_context": "System integrated"}))
        # Synthesize
        synthesis = MockTaskResult(success=True, output="Full-stack app deployed.")

        pool = MockAgentPool([plan, exec_fe, exec_be, eval_fe, eval_be, exec_int, eval_int, synthesis])
        ctx = ContextManager(state, pool, tempfile.mkdtemp())
        evaluator = QualityEvaluator(pool)

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
        )

        result = await orch.run(
            goal="Build frontend and backend",
            work_dir="/tmp",
            config=OrchestrationConfig(enable_checkpoints=False, enable_dynamic_replan=False),
            parent_task_id="smoke-4",
        )

        assert result.success is True
        assert result.dag.progress == 100
        assert len(result.dag.subtasks) == 3


class TestSmokeFeedbackCheckpoint:
    """Scenario: High-risk task triggers checkpoint, human approves."""

    @pytest.mark.asyncio
    async def test_checkpoint_approve(self):
        state = StateManager(enable_persistence=False)
        state.create_task(TaskState(
            task_id="smoke-5", status="running",
            prompt="Deploy to production", agent_type="claude", work_dir="/tmp"
        ))

        plan = MockTaskResult(
            success=True,
            output=json.dumps({
                "subtasks": [
                    {"id": "deploy", "description": "Deploy to prod", "agent_type": "claude",
                     "risk_level": "high", "is_checkpoint": True},
                ],
                "edges": [],
            }),
        )
        exec_deploy = MockTaskResult(success=True, output="Deployed successfully")
        eval_deploy = MockTaskResult(success=True, output=json.dumps({"decision": "proceed", "forward_context": "deployed"}))
        synthesis = MockTaskResult(success=True, output="Production deployment complete.")

        pool = MockAgentPool([plan, exec_deploy, eval_deploy, synthesis])
        ctx = ContextManager(state, pool, tempfile.mkdtemp())
        evaluator = QualityEvaluator(pool)
        feedback_mgr = FeedbackManager(state, persistence=None)

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
        )
        orch.feedback_mgr = feedback_mgr

        # Auto-submit feedback approval after a short delay
        async def auto_approve():
            await asyncio.sleep(0.1)
            # Find the pending feedback
            if feedback_mgr.get_all_pending():
                resp = FeedbackResponse(task_id="smoke-5", action="approve")
                await feedback_mgr.submit_feedback(resp)

        approval_task = asyncio.create_task(auto_approve())

        result = await orch.run(
            goal="Deploy to production",
            work_dir="/tmp",
            config=OrchestrationConfig(
                enable_checkpoints=True,
                checkpoint_mode="always",
                enable_dynamic_replan=False,
            ),
            parent_task_id="smoke-5",
        )

        await approval_task

        assert result.success is True


class TestSmokeGlobalTimeout:
    """Scenario: Global timeout triggers when tasks take too long."""

    @pytest.mark.asyncio
    async def test_timeout_stops_loop(self):
        state = StateManager(enable_persistence=False)
        state.create_task(TaskState(
            task_id="smoke-6", status="running",
            prompt="Long task", agent_type="claude", work_dir="/tmp"
        ))

        # Plan with a task that won't complete
        plan = MockTaskResult(
            success=True,
            output=json.dumps({
                "subtasks": [
                    {"id": "s1", "description": "Step 1", "agent_type": "claude"},
                    {"id": "s2", "description": "Step 2", "agent_type": "claude", "dependencies": ["s1"]},
                ],
                "edges": [["s1", "s2"]],
            }),
        )
        # s1 succeeds
        exec_s1 = MockTaskResult(success=True, output="step 1 done")
        eval_s1 = MockTaskResult(success=True, output=json.dumps({"decision": "proceed", "forward_context": "s1 done"}))
        # s2: keeps getting reworked (infinite loop scenario)
        exec_s2 = MockTaskResult(success=True, output="bad output")
        eval_s2_rework = MockTaskResult(
            success=True,
            output=json.dumps({"decision": "rework", "reasoning": "not good enough", "rework_instructions": "try again"}),
        )
        # Keep providing rework responses
        responses = [plan, exec_s1, eval_s1]
        for _ in range(10):
            responses.extend([exec_s2, eval_s2_rework])

        pool = MockAgentPool(responses)
        ctx = ContextManager(state, pool, tempfile.mkdtemp())
        evaluator = QualityEvaluator(pool)

        orch = OrchestratorLoop(
            agent_pool=pool, state=state,
            context_mgr=ctx, evaluator=evaluator,
        )

        result = await orch.run(
            goal="Long task",
            work_dir="/tmp",
            config=OrchestrationConfig(
                global_timeout_seconds=1,  # 1 second timeout
                max_rounds=20,
                enable_checkpoints=False,
                enable_dynamic_replan=False,
            ),
            parent_task_id="smoke-6",
        )

        # Should have stopped due to timeout or max retries, not success
        t = state.get_task("smoke-6")
        # Either completed partially or failed — but loop should have terminated
        assert t.status in ("completed", "failed")
