"""Error Handler - 错误处理与重试"""
from typing import Optional
from .state_manager import StateManager, TaskState
from .agent_pool import AgentPool
import asyncio


class ErrorHandler:
    """错误处理器"""

    def __init__(self, pool: AgentPool, state: StateManager, max_retries: int = 2):
        self.pool = pool
        self.state = state
        self.max_retries = max_retries

    async def execute_with_retry(self, task_id: str) -> bool:
        """带重试的执行"""
        task = self.state.get_task(task_id)
        if not task:
            return False

        for attempt in range(self.max_retries + 1):
            self.state.update_status(task_id, 'running')

            try:
                result = await self.pool.execute(
                    agent_type=task.agent_type,
                    prompt=task.prompt,
                    work_dir=task.work_dir
                )

                if result.success:
                    self.state.update_status(task_id, 'completed', result=result.output)
                    return True
                else:
                    if attempt < self.max_retries:
                        await asyncio.sleep(1)
                        continue
                    self.state.update_status(task_id, 'failed', error=result.error)
                    return False

            except Exception as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(1)
                    continue
                self.state.update_status(task_id, 'failed', error=str(e))
                return False

        return False
