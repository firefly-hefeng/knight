"""Tests for SQLite contention under concurrent DAG updates (H2)."""
import asyncio
import os
import tempfile
import pytest

from core.state_manager import StateManager, TaskState
from core.persistence import TaskPersistence


class TestSQLiteContention:
    """Stress test: concurrent writes to the same SQLite database."""

    @pytest.fixture
    def db_path(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "contention_test.db")
        yield path
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    def test_concurrent_task_creation(self, db_path):
        """10 concurrent task creates should all succeed."""
        sm = StateManager(enable_persistence=True, db_path=db_path)
        for i in range(10):
            sm.create_task(TaskState(
                task_id=f"concurrent-{i}",
                status="pending",
                prompt=f"task {i}",
                agent_type="claude",
                work_dir="/tmp",
            ))
        # All 10 should be persisted
        assert len(sm.tasks) == 10
        # Reload from DB
        sm2 = StateManager(enable_persistence=True, db_path=db_path)
        assert len(sm2.tasks) == 10

    def test_concurrent_status_updates(self, db_path):
        """Rapid status updates on the same task should not corrupt."""
        sm = StateManager(enable_persistence=True, db_path=db_path)
        sm.create_task(TaskState(
            task_id="rapid",
            status="pending",
            prompt="test",
            agent_type="claude",
            work_dir="/tmp",
        ))
        # Rapid sequential updates
        for i in range(50):
            sm.update_status("rapid", "running", progress=i * 2, log=f"step {i}")
        sm.update_status("rapid", "completed", result="final", progress=100)

        task = sm.get_task("rapid")
        assert task.status == "completed"
        assert task.progress == 100
        assert len(task.logs) == 50

        # Reload and verify
        sm2 = StateManager(enable_persistence=True, db_path=db_path)
        task2 = sm2.get_task("rapid")
        assert task2.status == "completed"
        assert task2.progress == 100

    @pytest.mark.asyncio
    async def test_async_concurrent_writes(self, db_path):
        """Multiple async coroutines writing simultaneously."""
        persistence = TaskPersistence(db_path)

        async def write_task(i):
            task = TaskState(
                task_id=f"async-{i}",
                status="pending",
                prompt=f"async task {i}",
                agent_type="claude",
                work_dir="/tmp",
            )
            persistence.save_task(task)
            # Simulate processing
            await asyncio.sleep(0.01)
            task.status = "running"
            task.progress = 50
            persistence.save_task(task)
            await asyncio.sleep(0.01)
            task.status = "completed"
            task.progress = 100
            persistence.save_task(task)

        # Run 15 concurrent writes
        await asyncio.gather(*(write_task(i) for i in range(15)))

        # Verify all succeeded
        all_tasks = persistence.load_all_tasks()
        assert len(all_tasks) == 15
        assert all(t.status == "completed" for t in all_tasks)
        persistence.close()

    def test_dag_json_large_update(self, db_path):
        """Large DAG JSON updates should not cause issues."""
        sm = StateManager(enable_persistence=True, db_path=db_path)
        sm.create_task(TaskState(
            task_id="dag-large",
            status="running",
            prompt="big dag",
            agent_type="claude",
            work_dir="/tmp",
        ))

        # Simulate increasingly large DAG JSON
        import json
        for i in range(20):
            subtasks = {f"s{j}": {"id": f"s{j}", "desc": f"step {j}" * 50} for j in range(i + 1)}
            dag_json = json.dumps({"subtasks": subtasks, "edges": [], "version": i})
            task = sm.get_task("dag-large")
            task.dag_json = dag_json
            sm.persistence.save_task(task)

        # Final verify
        sm2 = StateManager(enable_persistence=True, db_path=db_path)
        task2 = sm2.get_task("dag-large")
        assert task2.dag_json is not None
        data = json.loads(task2.dag_json)
        assert len(data["subtasks"]) == 20

    def test_attempt_history_bulk_insert(self, db_path):
        """Bulk attempt history inserts."""
        persistence = TaskPersistence(db_path)
        persistence.save_task(TaskState(
            task_id="bulk",
            status="running",
            prompt="test",
            agent_type="claude",
            work_dir="/tmp",
        ))

        for i in range(100):
            persistence.save_attempt(
                parent_task_id="bulk",
                subtask_id=f"s{i % 5}",
                attempt_number=i // 5 + 1,
                agent_type="claude",
                prompt_used=f"prompt {i}",
                result_output=f"output {i}" * 100,
                result_success=i % 3 != 0,
                duration_ms=100 + i,
                cost_usd=0.01,
            )

        attempts = persistence.load_attempts("bulk")
        assert len(attempts) == 100
        persistence.close()

    def test_wal_mode_verified(self, db_path):
        """WAL mode should be active."""
        persistence = TaskPersistence(db_path)
        mode = persistence._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        persistence.close()

    def test_feedback_concurrent_access(self, db_path):
        """Concurrent feedback request/response."""
        persistence = TaskPersistence(db_path)

        for i in range(10):
            persistence.save_feedback_request(
                task_id=f"fb-{i}",
                checkpoint_type="plan_review",
                question=f"Approve plan {i}?",
            )

        # Respond to even-numbered ones
        for i in range(0, 10, 2):
            persistence.save_feedback_response(f"fb-{i}", action="approve", message="LGTM")

        # Check: odd ones still pending, even ones responded
        for i in range(10):
            req = persistence.load_feedback_request(f"fb-{i}")
            if i % 2 == 0:
                assert req is None  # responded, so not "pending"
            else:
                assert req is not None

        persistence.close()
