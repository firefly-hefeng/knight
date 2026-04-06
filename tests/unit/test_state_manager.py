"""Tests for core/state_manager.py — extended tests for new features."""
import pytest

from core.state_manager import StateManager, TaskState, VALID_STATUSES


class TestStateManagerBasic:
    def test_create_and_get(self):
        sm = StateManager(enable_persistence=False)
        task = TaskState(
            task_id="t1", status="pending", prompt="test",
            agent_type="claude", work_dir="/tmp"
        )
        sm.create_task(task)
        assert sm.get_task("t1") is not None
        assert sm.get_task("t1").prompt == "test"

    def test_get_nonexistent(self):
        sm = StateManager(enable_persistence=False)
        assert sm.get_task("nope") is None

    def test_update_status(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.update_status("t1", "running", progress=50, log="started")
        t = sm.get_task("t1")
        assert t.status == "running"
        assert t.progress == 50
        assert len(t.logs) == 1

    def test_update_status_with_result_and_error(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.update_status("t1", "completed", result="output text")
        t = sm.get_task("t1")
        assert t.result == "output text"

        sm.update_status("t1", "failed", error="something broke")
        t = sm.get_task("t1")
        assert t.error == "something broke"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="Invalid status"):
            TaskState(
                task_id="x", status="bogus", prompt="x",
                agent_type="x", work_dir="/tmp"
            )

    def test_invalid_status_update_rejected(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        with pytest.raises(ValueError, match="Invalid status"):
            sm.update_status("t1", "bogus_status")


class TestValidStatuses:
    def test_new_statuses_included(self):
        assert "waiting_for_feedback" in VALID_STATUSES
        assert "evaluating" in VALID_STATUSES
        assert "cancelled" in VALID_STATUSES

    def test_all_basic_statuses(self):
        for s in ("pending", "running", "completed", "failed", "cancelled"):
            assert s in VALID_STATUSES


class TestTryTransition:
    def test_successful_transition(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        assert sm.try_transition("t1", "pending", "running") is True
        assert sm.get_task("t1").status == "running"

    def test_failed_transition_wrong_from(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="running", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        # Try to transition from "pending" but task is already "running"
        assert sm.try_transition("t1", "pending", "running") is False
        assert sm.get_task("t1").status == "running"  # unchanged

    def test_transition_nonexistent_task(self):
        sm = StateManager(enable_persistence=False)
        assert sm.try_transition("ghost", "pending", "running") is False

    def test_transition_with_kwargs(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="running", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.try_transition("t1", "running", "completed", result="done!", progress=100)
        t = sm.get_task("t1")
        assert t.status == "completed"
        assert t.result == "done!"
        assert t.progress == 100

    def test_concurrent_transitions_only_one_succeeds(self):
        """Simulate race condition: two callers try the same transition."""
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        # First caller succeeds
        assert sm.try_transition("t1", "pending", "running") is True
        # Second caller fails (task is now "running", not "pending")
        assert sm.try_transition("t1", "pending", "running") is False


class TestRecoverStaleTasks:
    def test_recovers_running_tasks(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="running", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="t2", status="waiting_for_feedback", prompt="y",
            agent_type="kimi", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="t3", status="pending", prompt="z",
            agent_type="claude", work_dir="/tmp"
        ))

        recovered = sm.recover_stale_tasks()
        assert "t1" in recovered
        assert "t2" in recovered
        assert "t3" not in recovered  # pending is not stale

        assert sm.get_task("t1").status == "failed"
        assert sm.get_task("t2").status == "failed"
        assert sm.get_task("t3").status == "pending"

    def test_recovers_evaluating_tasks(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="evaluating", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        recovered = sm.recover_stale_tasks()
        assert "t1" in recovered
        assert sm.get_task("t1").status == "failed"

    def test_no_stale_tasks(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="completed", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        recovered = sm.recover_stale_tasks()
        assert recovered == []


class TestSubtaskQueries:
    def test_get_subtasks(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="parent", status="running", prompt="main",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="child1", status="pending", prompt="sub1",
            agent_type="claude", work_dir="/tmp", parent_task_id="parent"
        ))
        sm.create_task(TaskState(
            task_id="child2", status="pending", prompt="sub2",
            agent_type="kimi", work_dir="/tmp", parent_task_id="parent"
        ))
        sm.create_task(TaskState(
            task_id="other", status="pending", prompt="unrelated",
            agent_type="claude", work_dir="/tmp"
        ))

        subtasks = sm.get_subtasks("parent")
        assert len(subtasks) == 2
        assert all(st.parent_task_id == "parent" for st in subtasks)

    def test_get_parent_task(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="parent", status="running", prompt="main",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="child", status="pending", prompt="sub",
            agent_type="claude", work_dir="/tmp", parent_task_id="parent"
        ))

        parent = sm.get_parent_task("child")
        assert parent is not None
        assert parent.task_id == "parent"

    def test_get_parent_of_root_task(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="root", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        assert sm.get_parent_task("root") is None

    def test_get_tasks_by_status(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="t2", status="running", prompt="y",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="t3", status="pending", prompt="z",
            agent_type="kimi", work_dir="/tmp"
        ))
        pending = sm.get_tasks_by_status("pending")
        assert len(pending) == 2

    def test_get_ready_tasks(self):
        sm = StateManager(enable_persistence=False)
        sm.create_task(TaskState(
            task_id="t1", status="completed", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        sm.create_task(TaskState(
            task_id="t2", status="pending", prompt="y",
            agent_type="claude", work_dir="/tmp", dependencies=["t1"]
        ))
        sm.create_task(TaskState(
            task_id="t3", status="pending", prompt="z",
            agent_type="kimi", work_dir="/tmp", dependencies=["t2"]
        ))

        ready = sm.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "t2"
