"""Workflow Engine - 工作流引擎"""
from typing import List
from .task_planner import TaskPlanner
from .task_coordinator import TaskCoordinator
from .state_manager import StateManager
from .agent_pool import AgentPool
from .result_aggregator import ResultAggregator


class WorkflowEngine:
    """工作流引擎"""

    def __init__(self):
        self.pool = AgentPool()
        self.state = StateManager()
        self.coordinator = TaskCoordinator(self.pool, self.state)
        self.planner = TaskPlanner()
        self.aggregator = ResultAggregator(self.state)

    async def execute(self, user_request: str, work_dir: str = '.') -> str:
        """执行工作流"""
        # 1. 规划任务
        tasks = self.planner.plan(user_request, work_dir)

        # 2. 注册任务
        for task in tasks:
            self.state.create_task(task)

        # 3. 执行任务
        task_ids = [t.task_id for t in tasks]
        await self.coordinator.run_workflow(task_ids)

        # 4. 聚合结果
        results = self.aggregator.aggregate(task_ids)
        return '\n'.join(results.values()) if results else ''
