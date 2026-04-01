"""Context Manager - 任务上下文管理"""
from typing import Dict, Optional
from .state_manager import StateManager


class ContextManager:
    """上下文管理器 - 任务间信息传递"""

    def __init__(self, state: StateManager):
        self.state = state
        self._context: Dict[str, str] = {}

    def set_context(self, key: str, value: str) -> None:
        """设置上下文"""
        self._context[key] = value

    def get_context(self, key: str) -> Optional[str]:
        """获取上下文"""
        return self._context.get(key)

    def build_prompt_with_context(self, task_id: str) -> str:
        """构建带上下文的prompt"""
        task = self.state.get_task(task_id)
        if not task:
            return ""

        prompt_parts = [task.prompt]

        # 添加依赖任务的结果作为上下文
        for dep_id in task.dependencies:
            dep_task = self.state.get_task(dep_id)
            if dep_task and dep_task.result:
                prompt_parts.append(f"\nContext from previous task: {dep_task.result[:200]}")

        return '\n'.join(prompt_parts)
