"""工程化测试 - 实际开发场景"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import WorkflowEngine, StateManager, TaskState, TaskCoordinator, AgentPool
import uuid


async def test_real_project():
    """测试真实项目场景: 创建一个Python包"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)

    # 模拟真实项目任务分解
    tasks = []

    # Task 1: 创建项目结构
    t1 = TaskState(
        task_id=str(uuid.uuid4()),
        status='pending',
        prompt="Create a Python package structure: mylib/__init__.py, mylib/core.py, setup.py",
        agent_type='claude',
        work_dir='/tmp/knight_project'
    )
    tasks.append(t1)

    # Task 2: 实现核心功能 (依赖t1)
    t2 = TaskState(
        task_id=str(uuid.uuid4()),
        status='pending',
        prompt="In mylib/core.py, implement a Calculator class with add, subtract methods",
        agent_type='claude',
        work_dir='/tmp/knight_project',
        dependencies=[t1.task_id]
    )
    tasks.append(t2)

    # Task 3: 创建测试 (依赖t2)
    t3 = TaskState(
        task_id=str(uuid.uuid4()),
        status='pending',
        prompt="Create tests/test_core.py with unit tests for Calculator class",
        agent_type='claude',
        work_dir='/tmp/knight_project',
        dependencies=[t2.task_id]
    )
    tasks.append(t3)

    for task in tasks:
        state.create_task(task)

    print("🏰 Real Project Test: 创建Python包")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 检查结果
    for i, task in enumerate(tasks, 1):
        t = state.get_task(task.task_id)
        status_icon = "✅" if t.status == 'completed' else "❌"
        print(f"  {status_icon} Task {i}: {t.status}")


if __name__ == '__main__':
    asyncio.run(test_real_project())
