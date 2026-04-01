"""扩展场景测试 - 多Agent协作"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskCoordinator, TaskState
from knight.core.smart_planner import SmartTaskPlanner
from knight.core.observability import ObservabilityManager
import uuid


async def test_multi_agent_collaboration():
    """测试多Agent协作场景"""
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)
    obs = ObservabilityManager(state)

    print("🏰 Multi-Agent Collaboration Test\n")

    # 场景: 构建一个完整的Web应用
    # Claude负责架构和复杂逻辑
    # Kimi负责简单文件操作
    tasks = [
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt="Create project structure: app/, templates/, static/, requirements.txt",
            agent_type='kimi',  # 简单文件操作用Kimi
            work_dir='/tmp/knight_webapp'
        ),
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt="Create Flask app in app/__init__.py with routes for home and about",
            agent_type='claude',  # 复杂逻辑用Claude
            work_dir='/tmp/knight_webapp'
        ),
        TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt="Create HTML templates: base.html, home.html, about.html",
            agent_type='kimi',
            work_dir='/tmp/knight_webapp'
        )
    ]

    # 设置依赖
    tasks[1].dependencies = [tasks[0].task_id]
    tasks[2].dependencies = [tasks[1].task_id]

    for task in tasks:
        state.create_task(task)
        obs.record_task_start(task.task_id)

    print("Executing workflow...")
    await coordinator.run_workflow([t.task_id for t in tasks])

    # 统计
    for task in tasks:
        t = state.get_task(task.task_id)
        if t.status == 'completed':
            obs.record_task_complete(task.task_id)
        else:
            obs.record_task_fail(task.task_id)
        icon = "✅" if t.status == 'completed' else "❌"
        agent_name = "Claude" if task.agent_type == 'claude' else "Kimi"
        print(f"  {icon} [{agent_name}] {task.prompt[:50]}...")

    print(f"\nSummary: {obs.get_summary()}")


if __name__ == '__main__':
    asyncio.run(test_multi_agent_collaboration())
