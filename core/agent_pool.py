"""Agent Pool - 管理商用Agent实例

向后兼容层：保留原有 AgentPool 接口，内部委托给 AgentRegistry。
新代码应直接使用 AgentRegistry。
"""
import asyncio
import sys
import os
from typing import Literal, Optional, Dict, Any, List

try:
    # 相对导入
    from ..adapters.claude_adapter import ClaudeAdapter, TaskResult
    from ..adapters.kimi_adapter import KimiAdapter
except ImportError:
    # 绝对导入
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from adapters.claude_adapter import ClaudeAdapter, TaskResult
    from adapters.kimi_adapter import KimiAdapter

from .agent_registry import AgentRegistry, AgentDefinition, AgentHealth


AgentType = Literal['claude', 'kimi']


class AgentPool:
    """
    Agent池 — 向后兼容接口 + AgentRegistry 集成

    旧用法（仍然支持）：
        pool = AgentPool()
        result = await pool.execute("claude", prompt, work_dir)

    新用法（推荐）：
        pool = AgentPool()
        pool.registry.register(AgentDefinition(name="codex", ...))
        result = await pool.execute("codex", prompt, work_dir)
    """

    def __init__(self, claude_concurrency: int = 2, kimi_concurrency: int = 3):
        # 旧适配器（保留用于旧代码直接引用）
        self.claude = ClaudeAdapter()
        self.kimi = KimiAdapter()

        # 新注册表
        self.registry = AgentRegistry()

        # 覆盖内置 Agent 的并发配置
        if claude_concurrency != 2:
            claude_def = self.registry.get("claude")
            if claude_def:
                claude_def.concurrency = claude_concurrency
                self.registry._semaphores["claude"] = asyncio.Semaphore(claude_concurrency)
        if kimi_concurrency != 3:
            kimi_def = self.registry.get("kimi")
            if kimi_def:
                kimi_def.concurrency = kimi_concurrency
                self.registry._semaphores["kimi"] = asyncio.Semaphore(kimi_concurrency)

        # 旧的 semaphore（兼容）
        self._semaphores = self.registry._semaphores

    async def execute(
        self,
        agent_type: str,
        prompt: str,
        work_dir: str,
        timeout: int = 300
    ) -> TaskResult:
        """执行任务 — 委托给 Registry（兼容旧接口）"""
        # 如果是注册表中的 Agent，走通用路径
        if self.registry.get(agent_type):
            return await self.registry.execute(agent_type, prompt, work_dir, timeout)

        # 降级：旧适配器直接调用
        if agent_type == "claude":
            async with self._semaphores.get("claude", asyncio.Semaphore(2)):
                return await self.claude.execute(prompt, work_dir, timeout)
        elif agent_type == "kimi":
            async with self._semaphores.get("kimi", asyncio.Semaphore(3)):
                return await self.kimi.execute(prompt, work_dir, timeout)
        else:
            return TaskResult(success=False, output="", error=f"Unknown agent: {agent_type}")

    async def execute_batch(
        self,
        tasks: list,
    ) -> list:
        """并行执行多个任务: tasks = [(agent_type, prompt, work_dir, timeout), ...]"""
        return await asyncio.gather(
            *(self.execute(at, p, wd, to) for at, p, wd, to in tasks),
            return_exceptions=True,
        )

    async def check_health(self, agent_type: str) -> bool:
        """检查 Agent 是否可用"""
        return await self.registry.check_health(agent_type)

    # ==================== Registry 代理方法 ====================

    def register_agent(self, definition: AgentDefinition) -> None:
        """注册新 Agent"""
        self.registry.register(definition)

    def unregister_agent(self, name: str) -> bool:
        """注销 Agent"""
        return self.registry.unregister(name)

    def list_registered(self) -> List[AgentDefinition]:
        """列出所有注册的 Agent"""
        return self.registry.list_agents()

    def list_healthy(self) -> List[str]:
        """列出所有健康的 Agent"""
        return self.registry.list_healthy()

    def get_agent_health(self, name: str) -> Optional[AgentHealth]:
        return self.registry.get_health(name)

    def get_registry_stats(self) -> Dict[str, Any]:
        return self.registry.get_stats()
