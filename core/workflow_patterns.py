"""Workflow Patterns - 工作流模式"""
from typing import List
from .state_manager import TaskState
import uuid


class WorkflowPattern:
    """工作流模式基类"""

    @staticmethod
    def chain(tasks: List[TaskState]) -> List[TaskState]:
        """链式执行 - 顺序依赖"""
        for i in range(1, len(tasks)):
            tasks[i].dependencies = [tasks[i-1].task_id]
        return tasks

    @staticmethod
    def group(tasks: List[TaskState]) -> List[TaskState]:
        """组执行 - 并行无依赖"""
        for task in tasks:
            task.dependencies = []
        return tasks

    @staticmethod
    def map_reduce(map_tasks: List[TaskState], reduce_task: TaskState) -> List[TaskState]:
        """Map-Reduce模式"""
        # Map阶段并行
        for task in map_tasks:
            task.dependencies = []

        # Reduce依赖所有Map
        reduce_task.dependencies = [t.task_id for t in map_tasks]

        return map_tasks + [reduce_task]
