"""Observability - 监控与可观测性"""
from typing import Dict, List
from datetime import datetime
from .state_manager import StateManager


class ObservabilityManager:
    """可观测性管理器"""

    def __init__(self, state: StateManager):
        self.state = state
        self.metrics: Dict[str, int] = {
            'total_tasks': 0,
            'completed': 0,
            'failed': 0
        }

    def record_task_start(self, task_id: str) -> None:
        """记录任务开始"""
        self.metrics['total_tasks'] += 1

    def record_task_complete(self, task_id: str) -> None:
        """记录任务完成"""
        self.metrics['completed'] += 1

    def record_task_fail(self, task_id: str) -> None:
        """记录任务失败"""
        self.metrics['failed'] += 1

    def get_summary(self) -> Dict:
        """获取统计摘要"""
        return {
            'total': self.metrics['total_tasks'],
            'completed': self.metrics['completed'],
            'failed': self.metrics['failed'],
            'success_rate': f"{self.metrics['completed'] / max(1, self.metrics['total_tasks']) * 100:.1f}%"
        }
