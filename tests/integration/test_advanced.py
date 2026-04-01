"""Knight 进阶测试 - 多任务协调"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import WorkflowEngine, StateManager, TaskState, TaskCoordinator, AgentPool
import uuid


async def test_parallel_tasks():
    """测试并行任务执行"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)

    # 创建3个独立任务
    tasks = [
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt=f"Create file{i}.txt with content 'Task {i}'",
            agent_type='claude',
            work_dir='/tmp/knight_test'
        )
        for i in range(1, 4)
    ]

    for task in tasks:
        state.create_task(task)

    print("🏰 Test: 并行执行3个任务")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 检查结果
    for task in tasks:
        t = state.get_task(task.task_id)
        print(f"  Task {task.prompt[:20]}... -> {t.status}")


async def test_dependency_tasks():
    """测试依赖任务执行"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)

    # 创建依赖链: task1 -> task2 -> task3
    task1_id = str(uuid.uuid4())
    task2_id = str(uuid.uuid4())
    task3_id = str(uuid.uuid4())

    tasks = [
        TaskState(
            task_id=task1_id,
            status='pending',
            prompt="Create base.txt with 'Base'",
            agent_type='claude',
            work_dir='/tmp/knight_test'
        ),
        TaskState(
            task_id=task2_id,
            status='pending',
            prompt="Read base.txt and create derived.txt with its content + ' Derived'",
            agent_type='claude',
            work_dir='/tmp/knight_test',
            dependencies=[task1_id]
        ),
        TaskState(
            task_id=task3_id,
            status='pending',
            prompt="Read derived.txt and create final.txt with its content + ' Final'",
            agent_type='claude',
            work_dir='/tmp/knight_test',
            dependencies=[task2_id]
        )
    ]

    for task in tasks:
        state.create_task(task)

    print("\n🏰 Test: 依赖任务链执行")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 检查结果
    for task in tasks:
        t = state.get_task(task.task_id)
        print(f"  {task.prompt[:30]}... -> {t.status}")


if __name__ == '__main__':
    asyncio.run(test_parallel_tasks())
    asyncio.run(test_dependency_tasks())
