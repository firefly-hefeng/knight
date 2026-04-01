"""Task Planner - 任务分解"""
from typing import List
from .state_manager import TaskState
import uuid


class TaskPlanner:
    """任务规划器 - 简单分解"""

    def plan(self, user_request: str, work_dir: str) -> List[TaskState]:
        """分解任务"""
        # 最小实现: 单任务执行
        task_id = str(uuid.uuid4())
        return [
            TaskState(
                task_id=task_id,
                status='pending',
                prompt=user_request,
                agent_type='claude',
                work_dir=work_dir
            )
        ]
