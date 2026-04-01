"""Task Coordinator - 任务执行协调"""
import asyncio
from typing import List, Optional
from .agent_pool import AgentPool, AgentType
from .state_manager import StateManager, TaskState


class TaskCoordinator:
    """任务协调器"""

    def __init__(self, pool: AgentPool, state: StateManager):
        self.pool = pool
        self.state = state

    def _build_context_prompt(self, task: TaskState) -> str:
        """构建带上下文的prompt"""
        parts = [task.prompt]

        # 添加依赖任务结果
        for dep_id in task.dependencies:
            dep = self.state.get_task(dep_id)
            if dep and dep.result:
                parts.append(f"\nPrevious step result: {dep.result[:150]}")

        return '\n'.join(parts)

    async def execute_task(self, task_id: str) -> bool:
        """执行单个任务"""
        task = self.state.get_task(task_id)
        if not task:
            return False

        self.state.update_status(task_id, 'running')

        try:
            prompt = self._build_context_prompt(task)
            result = await self.pool.execute(
                agent_type=task.agent_type,
                prompt=prompt,
                work_dir=task.work_dir
            )

            if result.success:
                self.state.update_status(task_id, 'completed', result=result.output)
                return True
            else:
                self.state.update_status(task_id, 'failed', error=result.error)
                return False

        except Exception as e:
            self.state.update_status(task_id, 'failed', error=str(e))
            return False

    async def run_workflow(self, task_ids: List[str]) -> None:
        """执行工作流"""
        while True:
            ready = self.state.get_ready_tasks()
            ready = [t for t in ready if t.task_id in task_ids]

            if not ready:
                break

            await asyncio.gather(*[self.execute_task(t.task_id) for t in ready])
