"""综合测试 - 所有优化功能"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator, TaskState
from knight.core.smart_planner import SmartTaskPlanner
from knight.core.workflow_patterns import WorkflowPattern
from knight.core.observability import ObservabilityManager
import uuid


async def test_comprehensive():
    """综合测试"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)
    planner = SmartTaskPlanner(pool)
    obs = ObservabilityManager(state)

    print("🏰 Comprehensive Test\n")

    # 测试1: 智能分解
    print("Test 1: Smart Planning")
    tasks = await planner.plan(
        "Create a TODO app with add, list, and delete commands",
        '/tmp/knight_todo'
    )
    print(f"  Generated {len(tasks)} tasks\n")

    # 测试2: 执行工作流
    print("Test 2: Workflow Execution")
    for task in tasks:
        state.create_task(task)
        obs.record_task_start(task.task_id)

    await coordinator.run_workflow([t.task_id for t in tasks])

    # 测试3: 统计结果
    for task in tasks:
        t = state.get_task(task.task_id)
        if t.status == 'completed':
            obs.record_task_complete(task.task_id)
        else:
            obs.record_task_fail(task.task_id)

    print("\nTest 3: Observability")
    summary = obs.get_summary()
    print(f"  Total: {summary['total']}")
    print(f"  Completed: {summary['completed']}")
    print(f"  Success Rate: {summary['success_rate']}")


if __name__ == '__main__':
    asyncio.run(test_comprehensive())
