"""State Manager - 任务状态管理"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from datetime import datetime


TaskStatus = Literal['pending', 'running', 'completed', 'failed']


@dataclass
class TaskState:
    """任务状态"""
    task_id: str
    status: TaskStatus
    prompt: str
    agent_type: str
    work_dir: str
    dependencies: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: int = 0
    logs: List[str] = field(default_factory=list)


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

    def update_status(self, task_id: str, status: TaskStatus,
                     result: Optional[str] = None, error: Optional[str] = None,
                     progress: Optional[int] = None, log: Optional[str] = None) -> None:
        """更新状态"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = status
            task.updated_at = datetime.now()
            if result:
                task.result = result
            if error:
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

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskState]:
        """按状态查询任务"""
        return [t for t in self._tasks.values() if t.status == status]

    def get_ready_tasks(self) -> List[TaskState]:
        """获取可执行任务"""
        ready = []
        for task in self._tasks.values():
            if task.status == 'pending':
                deps_done = all(
                    self._tasks.get(dep_id, TaskState('', 'failed', '', '', '')).status == 'completed'
                    for dep_id in task.dependencies
                )
                if deps_done:
                    ready.append(task)
        return ready
