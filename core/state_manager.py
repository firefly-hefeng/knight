"""State Manager - 任务状态管理"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


# 统一使用字符串常量，与 schemas.TaskStatus Enum 的 value 保持一致
VALID_STATUSES = ('pending', 'running', 'completed', 'failed', 'cancelled', 'waiting_for_feedback', 'evaluating')


@dataclass
class TaskState:
    """任务状态"""
    task_id: str
    status: str  # pending | running | completed | failed | cancelled
    prompt: str
    agent_type: str
    work_dir: str = "/tmp"
    dependencies: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: int = 0
    logs: List[str] = field(default_factory=list)
    parent_task_id: Optional[str] = None
    dag_json: Optional[str] = None
    checkpoint_data: Optional[str] = None

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{self.status}', must be one of {VALID_STATUSES}")


class StateManager:
    """状态管理器 - 支持持久化"""

    def __init__(self, enable_persistence: bool = False, db_path: str = "knight.db"):
        self._tasks: Dict[str, TaskState] = {}
        self.enable_persistence = enable_persistence
        self.persistence = None

        if enable_persistence:
            from .persistence import TaskPersistence
            self.persistence = TaskPersistence(db_path)
            self._load_from_db()

    def _load_from_db(self):
        """从数据库加载任务"""
        if self.persistence:
            tasks = self.persistence.load_all_tasks()
            for task in tasks:
                self._tasks[task.task_id] = task

    @property
    def tasks(self) -> Dict[str, TaskState]:
        """获取所有任务"""
        return self._tasks

    def create_task(self, task: TaskState) -> None:
        """创建任务"""
        self._tasks[task.task_id] = task
        if self.persistence:
            self.persistence.save_task(task)

    def update_status(self, task_id: str, status: str,
                     result: Optional[str] = None, error: Optional[str] = None,
                     progress: Optional[int] = None, log: Optional[str] = None) -> None:
        """更新状态"""
        # 兼容 Enum 和字符串
        status_val = status.value if hasattr(status, 'value') else str(status)
        if status_val not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status_val}'")

        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = status_val
            task.updated_at = datetime.now()
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if progress is not None:
                task.progress = progress
            if log:
                task.logs.append(log)
            if self.persistence:
                self.persistence.save_task(task)

    def get_task(self, task_id: str) -> Optional[TaskState]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: str) -> List[TaskState]:
        """按状态查询任务"""
        status_val = status.value if hasattr(status, 'value') else str(status)
        return [t for t in self._tasks.values() if t.status == status_val]

    def get_subtasks(self, parent_id: str) -> List[TaskState]:
        """获取某个父任务的所有子任务"""
        return [t for t in self._tasks.values() if t.parent_task_id == parent_id]

    def get_parent_task(self, task_id: str) -> Optional[TaskState]:
        """获取父任务"""
        task = self._tasks.get(task_id)
        if task and task.parent_task_id:
            return self._tasks.get(task.parent_task_id)
        return None

    def get_ready_tasks(self) -> List[TaskState]:
        """获取可执行任务（pending 且依赖全部完成）"""
        ready = []
        for task in self._tasks.values():
            if task.status == 'pending':
                deps_done = all(
                    self._tasks.get(dep_id) and self._tasks[dep_id].status == 'completed'
                    for dep_id in task.dependencies
                )
                if deps_done:
                    ready.append(task)
        return ready

    def try_transition(self, task_id: str, from_status: str, to_status: str, **kwargs) -> bool:
        """
        原子状态转换 — 仅当当前状态等于 from_status 时才转换

        解决 stream_task 等场景的竞态条件：
        两个并发调用都检查 status == 'pending'，但只有第一个能成功转换。

        Returns True if transition succeeded, False if current status != from_status.
        """
        from_val = from_status.value if hasattr(from_status, 'value') else str(from_status)
        to_val = to_status.value if hasattr(to_status, 'value') else str(to_status)

        task = self._tasks.get(task_id)
        if not task or task.status != from_val:
            return False

        task.status = to_val
        task.updated_at = datetime.now()
        for key, val in kwargs.items():
            if val is not None and hasattr(task, key):
                setattr(task, key, val)
        if self.persistence:
            self.persistence.save_task(task)
        return True

    def recover_stale_tasks(self) -> List[str]:
        """
        崩溃恢复 — 检测卡在 running/waiting_for_feedback 的任务

        启动时调用，将卡住的任务标记为 failed。
        返回恢复的任务 ID 列表。
        """
        recovered = []
        for task in self._tasks.values():
            if task.status in ('running', 'evaluating', 'waiting_for_feedback'):
                task.status = 'failed'
                task.error = f"Recovered from stale '{task.status}' state after restart"
                task.logs.append(f"Crash recovery: was {task.status}, marked failed")
                task.updated_at = datetime.now()
                if self.persistence:
                    self.persistence.save_task(task)
                recovered.append(task.task_id)
        return recovered
