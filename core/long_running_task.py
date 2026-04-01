"""Long Running Task - 长期任务管理"""
from typing import Callable, Optional
from datetime import datetime
from .state_manager import StateManager, TaskState
from .agent_pool import AgentPool
import asyncio
import uuid


class LongRunningTask:
    """长期任务管理器"""

    def __init__(self, pool: AgentPool, state: StateManager):
        self.pool = pool
        self.state = state
        self.running = False

    async def monitor_and_collect(
        self,
        collection_prompt: str,
        work_dir: str,
        interval_seconds: int = 60,
        duration_seconds: int = 300,
        on_complete: Optional[Callable] = None
    ) -> str:
        """监控并收集数据"""
        self.running = True
        start_time = datetime.now()
        collections = []

        while self.running:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= duration_seconds:
                break

            # 收集数据
            task = TaskState(
                task_id=str(uuid.uuid4()),
                status='pending',
                prompt=collection_prompt,
                agent_type='kimi',
                work_dir=work_dir
            )
            self.state.create_task(task)

            result = await self.pool.execute(
                task.agent_type,
                task.prompt,
                task.work_dir
            )

            if result.success:
                collections.append(result.output)

            await asyncio.sleep(interval_seconds)

        # 分析收集的数据
        if on_complete:
            return await on_complete(collections)

        return f"Collected {len(collections)} samples"

    def stop(self):
        """停止监控"""
        self.running = False
