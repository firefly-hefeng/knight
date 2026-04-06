"""Tests for core/feedback.py — FeedbackManager request/wait/submit cycle."""
import asyncio
import pytest

from core.state_manager import StateManager, TaskState
from core.feedback import FeedbackManager, FeedbackRequest, FeedbackResponse


@pytest.fixture
def state():
    sm = StateManager(enable_persistence=False)
    task = TaskState(
        task_id="fb-test", status="running",
        prompt="test task", agent_type="claude", work_dir="/tmp"
    )
    sm.create_task(task)
    return sm


@pytest.fixture
def mgr(state):
    return FeedbackManager(state, persistence=None)


class TestFeedbackManager:
    @pytest.mark.asyncio
    async def test_request_creates_pending(self, mgr, state):
        req = FeedbackRequest(
            task_id="fb-test",
            checkpoint_type="plan_review",
            question="Approve this plan?",
        )
        await mgr.request_feedback(req)

        # Task should be in waiting_for_feedback
        task = state.get_task("fb-test")
        assert task.status == "waiting_for_feedback"

        # Pending feedback should be retrievable
        pending = mgr.get_pending_feedback("fb-test")
        assert pending is not None
        assert pending.question == "Approve this plan?"

    @pytest.mark.asyncio
    async def test_submit_wakes_waiter(self, mgr, state):
        req = FeedbackRequest(
            task_id="fb-test",
            checkpoint_type="result_review",
            question="Is this output correct?",
        )
        await mgr.request_feedback(req)

        # Submit feedback in a separate task
        async def submit_later():
            await asyncio.sleep(0.05)
            resp = FeedbackResponse(task_id="fb-test", action="approve", message="Looks good")
            await mgr.submit_feedback(resp)

        submit_task = asyncio.create_task(submit_later())
        result = await mgr.wait_for_feedback("fb-test", timeout=5)
        await submit_task

        assert result is not None
        assert result.action == "approve"
        assert result.message == "Looks good"

        # Task should be back to running
        task = state.get_task("fb-test")
        assert task.status == "running"

        # Pending should be cleared
        assert mgr.get_pending_feedback("fb-test") is None

    @pytest.mark.asyncio
    async def test_timeout_auto_approves(self, mgr, state):
        req = FeedbackRequest(
            task_id="fb-test",
            checkpoint_type="plan_review",
            question="Approve?",
        )
        await mgr.request_feedback(req)

        # Wait with very short timeout
        result = await mgr.wait_for_feedback("fb-test", timeout=0.1)

        assert result is not None
        assert result.action == "approve"
        assert "timeout" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_abort_cancels_task(self, mgr, state):
        req = FeedbackRequest(
            task_id="fb-test",
            checkpoint_type="escalation",
            question="Should we abort?",
        )
        await mgr.request_feedback(req)

        resp = FeedbackResponse(task_id="fb-test", action="abort")
        await mgr.submit_feedback(resp)

        task = state.get_task("fb-test")
        assert task.status == "cancelled"

    @pytest.mark.asyncio
    async def test_wait_no_event_returns_none(self, mgr):
        result = await mgr.wait_for_feedback("nonexistent", timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_pending(self, mgr):
        for i in range(3):
            tid = f"fb-test-{i}"
            # Create task states for these
            mgr.state.create_task(TaskState(
                task_id=tid, status="running",
                prompt="test", agent_type="claude", work_dir="/tmp"
            ))
            req = FeedbackRequest(
                task_id=tid,
                checkpoint_type="plan_review",
                question=f"Q{i}?",
            )
            await mgr.request_feedback(req)

        pending = mgr.get_all_pending()
        assert len(pending) >= 3

    @pytest.mark.asyncio
    async def test_request_options_default(self, mgr):
        req = FeedbackRequest(
            task_id="fb-test",
            checkpoint_type="plan_review",
            question="Approve?",
        )
        assert req.options == ["approve", "reject", "modify"]
