"""测试智能任务分解"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator
from knight.core.smart_planner import SmartTaskPlanner


async def test_smart_planning():
    """测试智能任务分解"""
    pool = AgentPool()
    planner = SmartTaskPlanner(pool)

    request = "Create a REST API with Flask: user registration, login, and profile endpoints"

    print("🏰 Testing Smart Task Planner")
    print(f"Request: {request}\n")

    tasks = await planner.plan(request, '/tmp/knight_api')

    print(f"Generated {len(tasks)} tasks:")
    for i, task in enumerate(tasks, 1):
        deps = ""
        if task.dependencies:
            dep_idx = next((j for j, t in enumerate(tasks) if t.task_id == task.dependencies[0]), -1)
            if dep_idx >= 0:
                deps = f" (depends on task {dep_idx + 1})"
        print(f"{i}. {task.prompt}{deps}")


if __name__ == '__main__':
    asyncio.run(test_smart_planning())
