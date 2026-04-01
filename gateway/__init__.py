"""Knight Gateway - 统一网关入口

提供多种网关接入方式:
- HTTPGateway: REST API + SSE 流式响应
- FeishuWebSocketGateway: 飞书长连接（基于 WebSocket）
"""
from .http_gateway import HTTPGateway

# 飞书网关（可选依赖）
try:
    from ..adapters.feishu_adapter import FeishuWebSocketGateway, FeishuKnightBridge
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False

__all__ = ['HTTPGateway']

if FEISHU_AVAILABLE:
    __all__.extend(['FeishuWebSocketGateway', 'FeishuKnightBridge'])
