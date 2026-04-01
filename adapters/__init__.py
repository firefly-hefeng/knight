"""Agent Adapters - 商用Agent适配器"""
from .claude_adapter import ClaudeAdapter, TaskResult
from .kimi_adapter import KimiAdapter

__all__ = ['ClaudeAdapter', 'KimiAdapter', 'TaskResult']
