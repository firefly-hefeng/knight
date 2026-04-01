"""Agent Pool - 管理商用Agent实例"""
import asyncio
import sys
import os
from typing import Literal

try:
    # 相对导入
    from ..adapters.claude_adapter import ClaudeAdapter, TaskResult
    from ..adapters.kimi_adapter import KimiAdapter
except ImportError:
    # 绝对导入
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from adapters.claude_adapter import ClaudeAdapter, TaskResult
    from adapters.kimi_adapter import KimiAdapter


AgentType = Literal['claude', 'kimi']


class AgentPool:
    """Agent池 - 简单轮询调度"""

    def __init__(self):
        self.claude = ClaudeAdapter()
        self.kimi = KimiAdapter()
        self._locks = {'claude': asyncio.Lock(), 'kimi': asyncio.Lock()}

    async def execute(
        self,
        agent_type: AgentType,
        prompt: str,
        work_dir: str,
        timeout: int = 300
    ) -> TaskResult:
        """执行任务"""
        async with self._locks[agent_type]:
            adapter = self.claude if agent_type == 'claude' else self.kimi
            return await adapter.execute(prompt, work_dir, timeout)
