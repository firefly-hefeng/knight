"""端到端测试 - 使用智能分解器"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator
from knight.core.smart_planner import SmartTaskPlanner


async def test_e2e_with_smart_planner():
    """端到端测试"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)
    planner = SmartTaskPlanner(pool)

    request = "Create a simple calculator CLI in Python with add and subtract commands"
    work_dir = '/tmp/knight_calculator'

    print("🏰 End-to-End Test with Smart Planner")
    print(f"Request: {request}\n")

    # 1. 智能分解
    print("Step 1: Planning tasks...")
    tasks = await planner.plan(request, work_dir)
    print(f"  Generated {len(tasks)} tasks\n")

    # 2. 注册任务
    for task in tasks:
        state.create_task(task)

    # 3. 执行工作流
    print("Step 2: Executing workflow...")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 4. 检查结果
    print("\nStep 3: Results")
    for i, task in enumerate(tasks, 1):
        t = state.get_task(task.task_id)
        icon = "✅" if t.status == 'completed' else "❌"
        print(f"  {icon} Task {i}: {t.status}")


if __name__ == '__main__':
    asyncio.run(test_e2e_with_smart_planner())
