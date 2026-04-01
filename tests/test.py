#!/usr/bin/env python3
"""Knight 测试脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from knight.core.agent_pool import AgentPool
from knight.core.state_manager import StateManager, TaskState
from knight.core.task_coordinator import TaskCoordinator
import uuid

async def test():
    print("🏰 Knight Test\n")
    pool = AgentPool()
    state = StateManager()
    coordinator = TaskCoordinator(pool, state)

    task = TaskState(
        task_id=str(uuid.uuid4()),
        status='pending',
        prompt="Create test.txt with 'Hello'",
        agent_type='claude',
        work_dir='/tmp/knight_test'
    )

    state.create_task(task)
    await coordinator.run_workflow([task.task_id])

    result = state.get_task(task.task_id)
    print(f"Status: {result.status}")
    print("✅ Pass" if result.status == 'completed' else "❌ Fail")

if __name__ == '__main__':
    asyncio.run(test())
