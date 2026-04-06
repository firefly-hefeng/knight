"""Tests for core/persistence.py — SQLite persistence with WAL mode."""
import json
import os
import tempfile
import pytest
from datetime import datetime

from core.state_manager import TaskState
from core.persistence import TaskPersistence


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    p = TaskPersistence(db_path)
    yield p
    p.close()
    os.remove(db_path)


class TestTaskPersistence:
    def test_save_and_load(self, db):
        task = TaskState(
            task_id="t1", status="pending", prompt="Write tests",
            agent_type="claude", work_dir="/tmp",
            dependencies=["dep1"], progress=25,
            logs=["started", "step 1 done"],
        )
        db.save_task(task)
        loaded = db.load_task("t1")
        assert loaded is not None
        assert loaded.task_id == "t1"
        assert loaded.status == "pending"
        assert loaded.prompt == "Write tests"
        assert loaded.progress == 25
        assert loaded.dependencies == ["dep1"]
        assert loaded.logs == ["started", "step 1 done"]

    def test_load_nonexistent(self, db):
        assert db.load_task("ghost") is None

    def test_update_overwrites(self, db):
        task = TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        )
        db.save_task(task)
        task.status = "completed"
        task.result = "output data"
        task.progress = 100
        db.save_task(task)
        loaded = db.load_task("t1")
        assert loaded.status == "completed"
        assert loaded.result == "output data"
        assert loaded.progress == 100

    def test_load_all_tasks(self, db):
        for i in range(5):
            db.save_task(TaskState(
                task_id=f"t{i}", status="pending", prompt=f"task {i}",
                agent_type="claude", work_dir="/tmp"
            ))
        all_tasks = db.load_all_tasks()
        assert len(all_tasks) == 5

    def test_delete_task(self, db):
        db.save_task(TaskState(
            task_id="t1", status="pending", prompt="x",
            agent_type="claude", work_dir="/tmp"
        ))
        assert db.delete_task("t1") is True
        assert db.load_task("t1") is None
        assert db.delete_task("t1") is False  # already deleted

    def test_new_fields_persisted(self, db):
        """Verify parent_task_id, dag_json, checkpoint_data are persisted."""
        task = TaskState(
            task_id="child", status="running", prompt="sub task",
            agent_type="kimi", work_dir="/tmp",
            parent_task_id="parent",
            dag_json='{"id":"parent","goal":"test"}',
            checkpoint_data='{"step":2}',
        )
        db.save_task(task)
        loaded = db.load_task("child")
        assert loaded.parent_task_id == "parent"
        assert loaded.dag_json == '{"id":"parent","goal":"test"}'
        assert loaded.checkpoint_data == '{"step":2}'

    def test_wal_mode(self, db):
        """Verify WAL journal mode is active."""
        row = db._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"


class TestFeedbackPersistence:
    def test_save_and_load_request(self, db):
        db.save_feedback_request(
            task_id="fb1",
            checkpoint_type="plan_review",
            question="Approve this plan?",
            context="DAG has 3 subtasks",
            options=["approve", "reject"],
            dag_snapshot='{"id":"fb1"}',
        )
        loaded = db.load_feedback_request("fb1")
        assert loaded is not None
        assert loaded["checkpoint_type"] == "plan_review"
        assert loaded["question"] == "Approve this plan?"
        assert loaded["options"] == ["approve", "reject"]

    def test_load_missing_request(self, db):
        assert db.load_feedback_request("nonexistent") is None

    def test_save_response_clears_pending(self, db):
        db.save_feedback_request(
            task_id="fb2",
            checkpoint_type="result_review",
            question="Is output good?",
        )
        db.save_feedback_response("fb2", action="approve", message="LGTM")
        # After response, load_feedback_request should return None (it filters by response_action IS NULL)
        assert db.load_feedback_request("fb2") is None


class TestAttemptHistory:
    def test_save_and_load(self, db):
        db.save_attempt(
            parent_task_id="p1",
            subtask_id="s1",
            attempt_number=1,
            agent_type="claude",
            prompt_used="Write code",
            result_output="def foo(): pass",
            result_success=True,
            evaluation_json='{"passed":true}',
            strategy="initial",
            duration_ms=1500,
            cost_usd=0.05,
        )
        db.save_attempt(
            parent_task_id="p1",
            subtask_id="s1",
            attempt_number=2,
            agent_type="kimi",
            prompt_used="Fix code",
            result_output="def foo(): return 42",
            result_success=True,
            strategy="retry_different",
            duration_ms=800,
            cost_usd=0.02,
        )
        attempts = db.load_attempts("p1")
        assert len(attempts) == 2
        assert attempts[0]["attempt_number"] == 1
        assert attempts[0]["agent_type"] == "claude"
        assert attempts[0]["result_success"] is True
        assert attempts[1]["strategy"] == "retry_different"

    def test_load_empty_attempts(self, db):
        assert db.load_attempts("nonexistent") == []
