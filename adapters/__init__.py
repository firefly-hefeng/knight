"""Agent Adapters - 商用Agent适配器和第三方平台适配器"""
from .claude_adapter import ClaudeAdapter, TaskResult
from .kimi_adapter import KimiAdapter

# 飞书适配器（可选依赖）
try:
    from .feishu_adapter import (
        FeishuAdapter, 
        FeishuWebSocketGateway,
        FeishuKnightBridge,
        FeishuMessage,
        FeishuReply,
        start_feishu_gateway
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False

__all__ = ['ClaudeAdapter', 'KimiAdapter', 'TaskResult']

if FEISHU_AVAILABLE:
    __all__.extend([
        'FeishuAdapter',
        'FeishuWebSocketGateway', 
        'FeishuKnightBridge',
        'FeishuMessage',
        'FeishuReply',
        'start_feishu_gateway'
    ])
