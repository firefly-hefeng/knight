"""测试工作流模式"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator, TaskState
from knight.core.workflow_patterns import WorkflowPattern
import uuid


async def test_map_reduce():
    """测试Map-Reduce模式"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)

    # Map: 3个并行任务分析不同文件
    map_tasks = [
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt=f"Create data{i}.txt with numbers: {i}, {i+10}, {i+20}",
            agent_type='claude',
            work_dir='/tmp/knight_mapreduce'
        )
        for i in range(1, 4)
    ]

    # Reduce: 汇总结果
    reduce_task = TaskState(
        task_id=str(uuid.uuid4()),
        status='pending',
        prompt="Read all data*.txt files and create summary.txt with total count",
        agent_type='claude',
        work_dir='/tmp/knight_mapreduce'
    )

    # 应用Map-Reduce模式
    tasks = WorkflowPattern.map_reduce(map_tasks, reduce_task)

    for task in tasks:
        state.create_task(task)

    print("🏰 Map-Reduce Pattern Test")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 验证
    for i, task in enumerate(tasks, 1):
        t = state.get_task(task.task_id)
        icon = "✅" if t.status == 'completed' else "❌"
        print(f"  {icon} Task {i}: {t.status}")


if __name__ == '__main__':
    asyncio.run(test_map_reduce())
