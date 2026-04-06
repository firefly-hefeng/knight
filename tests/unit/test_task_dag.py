"""Tests for core/task_dag.py — DAG data structures, serialization, dependency resolution."""
import json
import pytest
from datetime import datetime

from core.task_dag import (
    EvaluationResult, ReviewVerdict, AttemptRecord, FailureAnalysis,
    RetryStrategy, SubTask, TaskDAG, OrchestrationConfig, OrchestrationResult,
)


# ==================== EvaluationResult ====================

class TestEvaluationResult:
    def test_success_factory(self):
        r = EvaluationResult.success()
        assert r.passed is True
        assert r.score == 1.0
        assert r.recommended_action == "accept"

    def test_from_exit_code_success(self):
        r = EvaluationResult.from_exit_code(True)
        assert r.passed is True
        assert r.score == 1.0

    def test_from_exit_code_failure(self):
        r = EvaluationResult.from_exit_code(False)
        assert r.passed is False
        assert r.score == 0.0
        assert r.recommended_action == "retry_same"

    def test_round_trip_dict(self):
        r = EvaluationResult(
            passed=True, score=0.85,
            criteria_results={"style": True, "correctness": False},
            failure_reasons=["type error on line 42"],
            recommended_action="retry_same",
            evaluator_reasoning="partial match",
        )
        d = r.to_dict()
        r2 = EvaluationResult.from_dict(d)
        assert r2.passed == r.passed
        assert r2.score == r.score
        assert r2.criteria_results == r.criteria_results
        assert r2.failure_reasons == r.failure_reasons
        assert r2.recommended_action == r.recommended_action

    def test_from_dict_ignores_extra_keys(self):
        d = {"passed": True, "score": 1.0, "extra_key": "ignored"}
        r = EvaluationResult.from_dict(d)
        assert r.passed is True
        assert not hasattr(r, "extra_key")


# ==================== ReviewVerdict ====================

class TestReviewVerdict:
    def test_default_values(self):
        v = ReviewVerdict()
        assert v.decision == "proceed"
        assert v.ready_for_next is True
        assert v.usable_parts == []

    def test_round_trip_dict(self):
        v = ReviewVerdict(
            understanding="Agent produced correct code",
            usable_parts=["function implementation", "test cases"],
            problematic_parts=["missing docstring"],
            decision="partial_rework",
            reasoning="Mostly good but needs docs",
            forward_context="def foo(): ...",
            rework_instructions="Add docstrings",
            rework_agent="claude",
            new_subtasks=[{"id": "fix_1", "description": "Add docs"}],
            plan_adjustments=["Skip linting step"],
            goal_progress="70% complete",
            ready_for_next=False,
        )
        d = v.to_dict()
        v2 = ReviewVerdict.from_dict(d)
        assert v2.decision == "partial_rework"
        assert v2.usable_parts == ["function implementation", "test cases"]
        assert v2.problematic_parts == ["missing docstring"]
        assert v2.rework_agent == "claude"
        assert v2.ready_for_next is False

    def test_to_evaluation_result_proceed(self):
        v = ReviewVerdict(decision="proceed")
        e = v.to_evaluation_result()
        assert e.passed is True
        assert e.score == 1.0

    def test_to_evaluation_result_partial_rework(self):
        v = ReviewVerdict(decision="partial_rework")
        e = v.to_evaluation_result()
        assert e.passed is True  # partial_rework still counts as passed
        assert e.score == 0.7

    def test_to_evaluation_result_rework(self):
        v = ReviewVerdict(decision="rework", problematic_parts=["bug in line 3"])
        e = v.to_evaluation_result()
        assert e.passed is False
        assert e.score == 0.3
        assert "bug in line 3" in e.failure_reasons

    def test_to_evaluation_result_all_decisions(self):
        expected = {
            "proceed": (True, 1.0),
            "partial_rework": (True, 0.7),
            "rework": (False, 0.3),
            "decompose": (False, 0.2),
            "escalate": (False, 0.1),
            "abort": (False, 0.0),
        }
        for decision, (exp_passed, exp_score) in expected.items():
            v = ReviewVerdict(decision=decision)
            e = v.to_evaluation_result()
            assert e.passed == exp_passed, f"decision={decision}"
            assert e.score == exp_score, f"decision={decision}"


# ==================== AttemptRecord ====================

class TestAttemptRecord:
    def test_round_trip_dict(self):
        a = AttemptRecord(
            attempt_number=1, agent_type="claude",
            prompt_used="Write code", result_output="def foo(): pass",
            result_success=True, strategy_used="initial",
            duration_ms=500, cost_usd=0.01,
        )
        d = a.to_dict()
        a2 = AttemptRecord.from_dict(d)
        assert a2.attempt_number == 1
        assert a2.result_success is True
        assert a2.cost_usd == 0.01

    def test_timestamp_serialization(self):
        a = AttemptRecord(attempt_number=1, agent_type="claude", prompt_used="x")
        d = a.to_dict()
        assert isinstance(d["timestamp"], str)
        a2 = AttemptRecord.from_dict(d)
        assert isinstance(a2.timestamp, datetime)

    def test_nested_evaluation_dict(self):
        e = EvaluationResult(passed=True, score=0.9)
        a = AttemptRecord(
            attempt_number=2, agent_type="kimi",
            prompt_used="test", evaluation=e,
        )
        d = a.to_dict()
        a2 = AttemptRecord.from_dict(d)
        assert a2.evaluation is not None
        assert a2.evaluation.score == 0.9


# ==================== SubTask ====================

class TestSubTask:
    def test_attempts_property(self):
        st = SubTask(id="s1", description="test", agent_type="claude")
        assert st.attempts == 0
        st.attempt_history.append(
            AttemptRecord(attempt_number=1, agent_type="claude", prompt_used="x")
        )
        assert st.attempts == 1

    def test_round_trip_dict(self):
        st = SubTask(
            id="s1", description="Build module",
            agent_type="claude", acceptance_criteria=["compiles", "passes tests"],
            dependencies=["s0"], risk_level="high",
            is_checkpoint=True, max_retries=5,
        )
        d = st.to_dict()
        st2 = SubTask.from_dict(d)
        assert st2.id == "s1"
        assert st2.acceptance_criteria == ["compiles", "passes tests"]
        assert st2.is_checkpoint is True
        assert st2.max_retries == 5
        assert st2.risk_level == "high"

    def test_from_dict_ignores_extra_keys(self):
        d = {"id": "x", "description": "y", "agent_type": "claude", "unknown": 42}
        st = SubTask.from_dict(d)
        assert st.id == "x"


# ==================== TaskDAG ====================

class TestTaskDAG:
    def _make_dag(self):
        """Create a simple test DAG: s1 -> s2 -> s3"""
        dag = TaskDAG(id="test", goal="Build a feature")
        dag.subtasks["s1"] = SubTask(id="s1", description="Design", agent_type="claude")
        dag.subtasks["s2"] = SubTask(
            id="s2", description="Implement", agent_type="claude",
            dependencies=["s1"]
        )
        dag.subtasks["s3"] = SubTask(
            id="s3", description="Test", agent_type="kimi",
            dependencies=["s2"]
        )
        dag.edges = [("s1", "s2"), ("s2", "s3")]
        return dag

    def test_get_ready_subtasks_initial(self):
        dag = self._make_dag()
        ready = dag.get_ready_subtasks()
        assert len(ready) == 1
        assert ready[0].id == "s1"

    def test_get_ready_subtasks_after_completion(self):
        dag = self._make_dag()
        dag.mark_complete("s1", "Design doc")
        ready = dag.get_ready_subtasks()
        assert len(ready) == 1
        assert ready[0].id == "s2"

    def test_get_ready_subtasks_parallel(self):
        """Two independent tasks should both be ready."""
        dag = TaskDAG(id="t", goal="parallel test")
        dag.subtasks["a"] = SubTask(id="a", description="Task A", agent_type="claude")
        dag.subtasks["b"] = SubTask(id="b", description="Task B", agent_type="kimi")
        ready = dag.get_ready_subtasks()
        assert len(ready) == 2

    def test_is_complete(self):
        dag = self._make_dag()
        assert dag.is_complete() is False
        for sid in ["s1", "s2", "s3"]:
            dag.mark_complete(sid, "done")
        assert dag.is_complete() is True

    def test_is_complete_with_skipped(self):
        dag = self._make_dag()
        dag.mark_complete("s1", "done")
        dag.subtasks["s2"].status = "skipped"
        dag.mark_complete("s3", "done")
        assert dag.is_complete() is True

    def test_has_failed_terminal(self):
        dag = self._make_dag()
        assert dag.has_failed_terminal() is False
        st = dag.subtasks["s1"]
        st.status = "failed"
        # Not terminal yet — no attempts exhausted
        assert dag.has_failed_terminal() is False
        # Add max_retries attempts
        for i in range(st.max_retries):
            st.attempt_history.append(
                AttemptRecord(attempt_number=i+1, agent_type="claude", prompt_used="x")
            )
        assert dag.has_failed_terminal() is True

    def test_mark_running(self):
        dag = self._make_dag()
        dag.mark_running("s1")
        assert dag.subtasks["s1"].status == "running"

    def test_mark_failed(self):
        dag = self._make_dag()
        dag.mark_failed("s1", "timeout")
        assert dag.subtasks["s1"].status == "failed"
        assert dag.subtasks["s1"].result == "timeout"

    def test_add_subtask_with_after(self):
        dag = self._make_dag()
        new = SubTask(id="s4", description="Deploy", agent_type="claude")
        dag.add_subtask(new, after=["s3"])
        assert "s4" in dag.subtasks
        assert ("s3", "s4") in dag.edges
        assert "s3" in dag.subtasks["s4"].dependencies

    def test_add_subtask_with_before(self):
        dag = self._make_dag()
        new = SubTask(id="s0", description="Setup", agent_type="claude")
        dag.add_subtask(new, before=["s1"])
        assert "s0" in dag.subtasks
        assert ("s0", "s1") in dag.edges
        assert "s0" in dag.subtasks["s1"].dependencies

    def test_add_checkpoint_subtask(self):
        dag = self._make_dag()
        cp = SubTask(id="review", description="Review", agent_type="claude", is_checkpoint=True)
        dag.add_subtask(cp)
        assert "review" in dag.checkpoints

    def test_remove_subtask(self):
        dag = self._make_dag()
        dag.remove_subtask("s2")
        assert "s2" not in dag.subtasks
        assert ("s1", "s2") not in dag.edges
        assert ("s2", "s3") not in dag.edges
        # s3 should no longer depend on s2
        assert "s2" not in dag.subtasks["s3"].dependencies

    def test_reset_subtask(self):
        dag = self._make_dag()
        dag.mark_complete("s1", "result text")
        dag.reset_subtask("s1")
        assert dag.subtasks["s1"].status == "pending"
        assert dag.subtasks["s1"].result is None
        assert dag.subtasks["s1"].result_summary is None

    def test_snapshot(self):
        dag = self._make_dag()
        assert dag.version == 1
        assert len(dag.plan_history) == 0
        dag.snapshot()
        assert dag.version == 2
        assert len(dag.plan_history) == 1
        # Snapshot is valid JSON
        restored = TaskDAG.from_json(dag.plan_history[0])
        assert restored.id == dag.id

    def test_progress(self):
        dag = self._make_dag()
        assert dag.progress == 0
        dag.mark_complete("s1", "done")
        assert dag.progress == 33  # 1/3
        dag.mark_complete("s2", "done")
        assert dag.progress == 66  # 2/3
        dag.mark_complete("s3", "done")
        assert dag.progress == 100

    def test_progress_empty_dag(self):
        dag = TaskDAG(id="e", goal="empty")
        assert dag.progress == 0

    def test_total_cost(self):
        dag = self._make_dag()
        dag.subtasks["s1"].attempt_history.append(
            AttemptRecord(attempt_number=1, agent_type="claude", prompt_used="x", cost_usd=0.05)
        )
        dag.subtasks["s2"].attempt_history.append(
            AttemptRecord(attempt_number=1, agent_type="kimi", prompt_used="y", cost_usd=0.02)
        )
        assert dag.total_cost == pytest.approx(0.07)

    def test_total_attempts(self):
        dag = self._make_dag()
        dag.subtasks["s1"].attempt_history.append(
            AttemptRecord(attempt_number=1, agent_type="claude", prompt_used="x")
        )
        dag.subtasks["s1"].attempt_history.append(
            AttemptRecord(attempt_number=2, agent_type="claude", prompt_used="x")
        )
        assert dag.total_attempts == 2

    def test_json_round_trip(self):
        dag = self._make_dag()
        dag.mark_complete("s1", "design output")
        dag.subtasks["s1"].result_summary = "summarized"
        json_str = dag.to_json()
        dag2 = TaskDAG.from_json(json_str)
        assert dag2.id == dag.id
        assert dag2.goal == dag.goal
        assert len(dag2.subtasks) == 3
        assert dag2.subtasks["s1"].status == "completed"
        assert dag2.subtasks["s1"].result_summary == "summarized"
        assert dag2.edges == [("s1", "s2"), ("s2", "s3")]

    def test_json_preserves_timestamps(self):
        dag = self._make_dag()
        json_str = dag.to_json()
        dag2 = TaskDAG.from_json(json_str)
        assert isinstance(dag2.created_at, datetime)
        assert isinstance(dag2.updated_at, datetime)

    def test_dependency_with_missing_subtask(self):
        """Dependencies referencing non-existent subtasks should not block."""
        dag = TaskDAG(id="t", goal="test")
        dag.subtasks["a"] = SubTask(
            id="a", description="depends on ghost",
            agent_type="claude", dependencies=["nonexistent"]
        )
        ready = dag.get_ready_subtasks()
        # nonexistent dep is ignored (not in dag.subtasks), so a is ready
        assert len(ready) == 1


# ==================== OrchestrationConfig ====================

class TestOrchestrationConfig:
    def test_defaults(self):
        c = OrchestrationConfig()
        assert c.max_rounds == 5
        assert c.max_retries_per_subtask == 3
        assert c.enable_checkpoints is True
        assert c.global_timeout_seconds == 1800
