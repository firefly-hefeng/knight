"""大规模任务测试"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator, TaskState
from knight.core.workflow_patterns import WorkflowPattern
from knight.core.observability import ObservabilityManager
import uuid
import time


async def test_large_scale():
    """测试大规模任务处理"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)
    obs = ObservabilityManager(state)

    print("🏰 Large Scale Test (10 parallel tasks)\n")

    # 创建10个并行任务
    tasks = [
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt=f"Create file_{i}.txt with content 'Task {i}'",
            agent_type='kimi',  # 使用Kimi提速
            work_dir='/tmp/knight_scale'
        )
        for i in range(1, 11)
    ]

    # 应用并行模式
    tasks = WorkflowPattern.group(tasks)

    for task in tasks:
        state.create_task(task)
        obs.record_task_start(task.task_id)

    start = time.time()
    await coordinator.run_workflow([t.task_id for t in tasks])
    duration = time.time() - start

    # 统计
    for task in tasks:
        t = state.get_task(task.task_id)
        if t.status == 'completed':
            obs.record_task_complete(task.task_id)
        else:
            obs.record_task_fail(task.task_id)

    summary = obs.get_summary()
    print(f"Duration: {duration:.1f}s")
    print(f"Summary: {summary}")
    print(f"Throughput: {summary['completed'] / duration:.1f} tasks/sec")


if __name__ == '__main__':
    asyncio.run(test_large_scale())
