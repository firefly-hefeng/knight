"""Agent Selector - 智能Agent选择"""
from typing import Literal
from .agent_pool import AgentType


class AgentSelector:
    """Agent选择策略"""

    @staticmethod
    def select_by_cost(task_complexity: str) -> AgentType:
        """基于成本选择 - Kimi免费优先"""
        if task_complexity in ['simple', 'medium']:
            return 'kimi'
        return 'claude'

    @staticmethod
    def select_by_speed(task_type: str) -> AgentType:
        """基于速度选择 - Kimi更快"""
        if task_type in ['file_ops', 'simple_code']:
            return 'kimi'
        return 'claude'

    @staticmethod
    def select_by_quality(task_type: str) -> AgentType:
        """基于质量选择 - Claude更强"""
        if task_type in ['complex_logic', 'architecture']:
            return 'claude'
        return 'kimi'
