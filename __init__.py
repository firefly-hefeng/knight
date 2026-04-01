"""Knight System - Multi-Agent Orchestration Framework"""
try:
    from .core import WorkflowEngine, KnightCore
    __all__ = ['WorkflowEngine', 'KnightCore']
except ImportError:
    # 部分依赖可能未安装
    __all__ = []

__version__ = '0.1.0'
