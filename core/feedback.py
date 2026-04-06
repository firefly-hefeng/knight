"""
Feedback - 人类反馈循环

编排器在检查点暂停 → 等待人类反馈 → 恢复执行
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

from .state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class FeedbackRequest:
    """编排器发出的反馈请求"""
    task_id: str
    checkpoint_type: str            # plan_review | result_review | approval_gate | escalation
    question: str
    context: str = ""
    options: List[str] = field(default_factory=lambda: ["approve", "reject", "modify"])
    dag_snapshot: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FeedbackResponse:
    """人类的反馈响应"""
    task_id: str
    action: str                     # approve | reject | modify | abort
    message: Optional[str] = None
    modifications: Optional[Dict] = None
    responded_at: datetime = field(default_factory=datetime.now)


class FeedbackManager:
    """人类反馈管理器 — 暂停/恢复编排循环"""

    def __init__(self, state: StateManager, persistence=None):
        self.state = state
        self.persistence = persistence
        self._events: Dict[str, asyncio.Event] = {}
        self._responses: Dict[str, FeedbackResponse] = {}
        self._pending: Dict[str, FeedbackRequest] = {}

    async def request_feedback(self, request: FeedbackRequest) -> None:
        """
        发出反馈请求：
        1. 持久化请求
        2. 更新任务状态为 waiting_for_feedback
        3. 创建 asyncio.Event 用于阻塞等待
        """
        self._pending[request.task_id] = request
        self._events[request.task_id] = asyncio.Event()

        # 更新任务状态
        self.state.update_status(
            request.task_id, "waiting_for_feedback",
            log=f"Checkpoint [{request.checkpoint_type}]: {request.question}"
        )

        # 持久化
        if self.persistence:
            try:
                self.persistence.save_feedback_request(
                    task_id=request.task_id,
                    checkpoint_type=request.checkpoint_type,
                    question=request.question,
                    context=request.context,
                    options=request.options,
                    dag_snapshot=request.dag_snapshot,
                )
            except Exception as e:
                logger.warning(f"Failed to persist feedback request: {e}")

        logger.info(f"Feedback requested for task {request.task_id}: {request.question}")

    async def submit_feedback(self, response: FeedbackResponse) -> None:
        """
        提交人类反馈：
        1. 保存响应
        2. 更新任务状态回 running
        3. 触发 Event 唤醒等待的编排器
        """
        self._responses[response.task_id] = response

        # 持久化
        if self.persistence:
            try:
                self.persistence.save_feedback_response(
                    task_id=response.task_id,
                    action=response.action,
                    message=response.message or "",
                )
            except Exception as e:
                logger.warning(f"Failed to persist feedback response: {e}")

        # 更新状态
        if response.action != "abort":
            self.state.update_status(
                response.task_id, "running",
                log=f"Feedback received: {response.action}" +
                    (f" — {response.message}" if response.message else "")
            )
        else:
            self.state.update_status(
                response.task_id, "cancelled",
                error="Aborted by human feedback",
                log="Feedback: abort"
            )

        # 唤醒等待者
        event = self._events.get(response.task_id)
        if event:
            event.set()

        # 清理 pending
        self._pending.pop(response.task_id, None)

        logger.info(f"Feedback submitted for task {response.task_id}: {response.action}")

    async def wait_for_feedback(
        self, task_id: str, timeout: int = 3600
    ) -> Optional[FeedbackResponse]:
        """
        阻塞等待反馈（via asyncio.Event）
        超时返回 None
        """
        event = self._events.get(task_id)
        if not event:
            return None

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Feedback timeout for task {task_id} after {timeout}s")
            self.state.update_status(
                task_id, "running",
                log=f"Feedback timeout ({timeout}s), continuing with defaults"
            )
            # 超时默认 approve
            return FeedbackResponse(task_id=task_id, action="approve", message="Auto-approved (timeout)")

        response = self._responses.pop(task_id, None)
        self._events.pop(task_id, None)
        return response

    def get_pending_feedback(self, task_id: str) -> Optional[FeedbackRequest]:
        """获取待处理的反馈请求（供前端轮询）"""
        return self._pending.get(task_id)

    def get_all_pending(self) -> List[FeedbackRequest]:
        """获取所有待处理的反馈请求"""
        return list(self._pending.values())
