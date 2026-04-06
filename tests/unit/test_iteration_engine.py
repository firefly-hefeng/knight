"""Tests for core/iteration_engine.py — strategy generation and failure analysis parsing."""
import pytest

from core.task_dag import (
    SubTask, EvaluationResult, FailureAnalysis, RetryStrategy,
    AttemptRecord, TaskDAG,
)
from core.context_manager import ContextManager
from core.state_manager import StateManager
from core.iteration_engine import IterationEngine


class TestParseAnalysis:
    def setup_method(self):
        state = StateManager(enable_persistence=False)
        ctx = ContextManager(state, agent_pool=None)
        self.engine = IterationEngine(agent_pool=None, context_mgr=ctx)

    def test_clean_json(self):
        response = '''{
            "root_cause": "prompt_issue",
            "explanation": "The prompt was too vague",
            "confidence": 0.8,
            "refined_prompt": "Please write a Python function that...",
            "new_agent_type": null
        }'''
        analysis = self.engine._parse_analysis(response)
        assert analysis.root_cause == "prompt_issue"
        assert analysis.explanation == "The prompt was too vague"
        assert analysis.confidence == 0.8
        assert hasattr(analysis, '_refined_prompt')
        assert analysis._refined_prompt == "Please write a Python function that..."

    def test_json_in_code_block(self):
        response = '''Here's my analysis:
```json
{
    "root_cause": "agent_limitation",
    "explanation": "Kimi cannot handle this code task",
    "confidence": 0.9,
    "new_agent_type": "claude"
}
```'''
        analysis = self.engine._parse_analysis(response)
        assert analysis.root_cause == "agent_limitation"
        assert hasattr(analysis, '_new_agent')
        assert analysis._new_agent == "claude"

    def test_invalid_json_fallback(self):
        response = "I can't parse this"
        analysis = self.engine._parse_analysis(response)
        assert analysis.root_cause == "prompt_issue"
        assert analysis.confidence == 0.3


class TestInferAnalysis:
    def setup_method(self):
        state = StateManager(enable_persistence=False)
        ctx = ContextManager(state, agent_pool=None)
        self.engine = IterationEngine(agent_pool=None, context_mgr=ctx)

    def test_high_score_partial_success(self):
        eval_result = EvaluationResult(
            passed=False, score=0.7,
            failure_reasons=["minor formatting issue"]
        )
        analysis = self.engine._infer_analysis(eval_result)
        assert analysis.root_cause == "prompt_issue"

    def test_timeout_detection(self):
        eval_result = EvaluationResult(
            passed=False, score=0.0,
            failure_reasons=["Execution timeout after 300s"]
        )
        analysis = self.engine._infer_analysis(eval_result)
        assert analysis.root_cause == "external_failure"

    def test_low_score_default(self):
        eval_result = EvaluationResult(
            passed=False, score=0.2,
            failure_reasons=["completely wrong"]
        )
        analysis = self.engine._infer_analysis(eval_result)
        assert analysis.root_cause == "prompt_issue"


class TestGenerateStrategy:
    def setup_method(self):
        state = StateManager(enable_persistence=False)
        ctx = ContextManager(state, agent_pool=None)
        self.engine = IterationEngine(agent_pool=None, context_mgr=ctx)

    @pytest.mark.asyncio
    async def test_prompt_issue_refines_prompt(self):
        subtask = SubTask(id="s1", description="Write code", agent_type="claude")
        subtask.attempt_history.append(
            AttemptRecord(attempt_number=1, agent_type="claude",
                         prompt_used="Write code", result_output="syntax error")
        )
        analysis = FailureAnalysis(
            root_cause="prompt_issue",
            explanation="Prompt was ambiguous"
        )
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "retry_same"
        assert "Previous attempt failed" in strategy.refined_prompt

    @pytest.mark.asyncio
    async def test_agent_limitation_switches(self):
        subtask = SubTask(id="s1", description="Search web", agent_type="claude")
        analysis = FailureAnalysis(
            root_cause="agent_limitation",
            explanation="Claude can't search"
        )
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "retry_different"
        assert strategy.new_agent_type == "kimi"

    @pytest.mark.asyncio
    async def test_task_too_complex_decomposes(self):
        subtask = SubTask(id="s1", description="Build everything", agent_type="claude")
        analysis = FailureAnalysis(
            root_cause="task_too_complex",
            explanation="Too many requirements"
        )
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "decompose"

    @pytest.mark.asyncio
    async def test_external_failure_retries(self):
        subtask = SubTask(id="s1", description="Call API", agent_type="claude")
        analysis = FailureAnalysis(
            root_cause="external_failure",
            explanation="API timeout"
        )
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "retry_same"

    @pytest.mark.asyncio
    async def test_llm_refined_prompt_used_directly(self):
        subtask = SubTask(id="s1", description="Write code", agent_type="claude")
        analysis = FailureAnalysis(root_cause="prompt_issue", explanation="vague")
        analysis._refined_prompt = "Write a Python function that adds two numbers"
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "retry_same"
        assert strategy.refined_prompt == "Write a Python function that adds two numbers"

    @pytest.mark.asyncio
    async def test_llm_new_agent_used_directly(self):
        subtask = SubTask(id="s1", description="Search", agent_type="claude")
        analysis = FailureAnalysis(root_cause="unknown", explanation="wrong agent")
        analysis._new_agent = "kimi"
        strategy = await self.engine._generate_strategy(subtask, analysis)
        assert strategy.action == "retry_different"
        assert strategy.new_agent_type == "kimi"


class TestApplyStrategy:
    def setup_method(self):
        state = StateManager(enable_persistence=False)
        ctx = ContextManager(state, agent_pool=None)
        self.engine = IterationEngine(agent_pool=None, context_mgr=ctx)

    def _make_dag(self):
        dag = TaskDAG(id="test", goal="test")
        dag.subtasks["s1"] = SubTask(id="s1", description="Task 1", agent_type="claude")
        return dag

    @pytest.mark.asyncio
    async def test_retry_same_resets(self):
        dag = self._make_dag()
        dag.mark_failed("s1", "error")
        analysis = FailureAnalysis(root_cause="prompt_issue")
        strategy = RetryStrategy(action="retry_same")
        result_dag = await self.engine._apply_strategy(dag, dag.subtasks["s1"], strategy, analysis)
        assert result_dag.subtasks["s1"].status == "pending"

    @pytest.mark.asyncio
    async def test_retry_same_with_refined_prompt(self):
        dag = self._make_dag()
        dag.mark_failed("s1", "error")
        analysis = FailureAnalysis(root_cause="prompt_issue")
        strategy = RetryStrategy(action="retry_same", refined_prompt="Better prompt")
        result_dag = await self.engine._apply_strategy(dag, dag.subtasks["s1"], strategy, analysis)
        assert result_dag.subtasks["s1"].description == "Better prompt"

    @pytest.mark.asyncio
    async def test_retry_different_switches_agent(self):
        dag = self._make_dag()
        dag.mark_failed("s1", "error")
        analysis = FailureAnalysis(root_cause="agent_limitation")
        strategy = RetryStrategy(action="retry_different", new_agent_type="kimi")
        result_dag = await self.engine._apply_strategy(dag, dag.subtasks["s1"], strategy, analysis)
        assert result_dag.subtasks["s1"].agent_type == "kimi"
        assert result_dag.subtasks["s1"].status == "pending"

    @pytest.mark.asyncio
    async def test_escalate_marks_failed(self):
        dag = self._make_dag()
        analysis = FailureAnalysis(root_cause="unknown")
        strategy = RetryStrategy(action="escalate")
        result_dag = await self.engine._apply_strategy(dag, dag.subtasks["s1"], strategy, analysis)
        assert result_dag.subtasks["s1"].status == "failed"

    @pytest.mark.asyncio
    async def test_skip_marks_skipped(self):
        dag = self._make_dag()
        analysis = FailureAnalysis(root_cause="unknown")
        strategy = RetryStrategy(action="skip")
        result_dag = await self.engine._apply_strategy(dag, dag.subtasks["s1"], strategy, analysis)
        assert result_dag.subtasks["s1"].status == "skipped"
