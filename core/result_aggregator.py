"""Result Aggregator - 结果聚合器"""
from typing import List, Dict
from .state_manager import StateManager


class ResultAggregator:
    """结果聚合 - 最小实现"""

    def __init__(self, state: StateManager):
        self.state = state

    def aggregate(self, task_ids: List[str]) -> Dict[str, str]:
        """聚合任务结果"""
        results = {}
        for tid in task_ids:
            task = self.state.get_task(tid)
            if task and task.status == 'completed':
                results[tid] = task.result or ''
        return results

    def summarize(self, task_ids: List[str]) -> str:
        """生成摘要"""
        results = self.aggregate(task_ids)
        completed = len(results)
        total = len(task_ids)

        summary = [f"Completed: {completed}/{total}"]
        for tid, result in results.items():
            summary.append(f"- {result[:100]}")

        return '\n'.join(summary)
