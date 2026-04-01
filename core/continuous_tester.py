"""Continuous Testing - 持续测试"""
from typing import Optional
from .agent_pool import AgentPool
from .state_manager import StateManager, TaskState
import uuid


class ContinuousTester:
    """持续测试器"""

    def __init__(self, pool: AgentPool, state: StateManager):
        self.pool = pool
        self.state = state

    async def test_and_fix(self, code_path: str, max_iterations: int = 3) -> bool:
        """测试并修复代码"""
        for i in range(max_iterations):
            # 运行测试
            test_task = TaskState(
                task_id=str(uuid.uuid4()),
                status='pending',
                prompt=f"Run tests in {code_path} and report failures",
                agent_type='claude',
                work_dir=code_path
            )
            self.state.create_task(test_task)

            result = await self.pool.execute(
                test_task.agent_type,
                test_task.prompt,
                test_task.work_dir
            )

            if "all tests passed" in result.output.lower() or "0 failed" in result.output.lower():
                return True

            # 修复失败
            fix_task = TaskState(
                task_id=str(uuid.uuid4()),
                status='pending',
                prompt=f"Fix test failures: {result.output[:200]}",
                agent_type='claude',
                work_dir=code_path
            )
            self.state.create_task(fix_task)

            await self.pool.execute(
                fix_task.agent_type,
                fix_task.prompt,
                fix_task.work_dir
            )

        return False
