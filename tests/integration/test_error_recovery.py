"""错误恢复测试"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskState
from knight.core.error_handler import ErrorHandler


async def test_error_recovery():
    """测试错误恢复机制"""
    pool = AgentPool()
    state = StateManager()
    handler = ErrorHandler(pool, state, max_retries=2)

    print("🏰 Error Recovery Test\n")

    # 创建一个可能失败的任务
    task = TaskState(
        task_id='test-1',
        status='pending',
        prompt="Create a file with invalid path: /root/forbidden/test.txt",
        agent_type='claude',
        work_dir='/tmp/knight_error'
    )
    state.create_task(task)

    print("Test 1: Task with potential error")
    success = await handler.execute_with_retry('test-1')
    t = state.get_task('test-1')
    print(f"  Status: {t.status}")
    print(f"  Success: {success}\n")

    # 创建正常任务
    task2 = TaskState(
        task_id='test-2',
        status='pending',
        prompt="Create hello.txt with 'Hello World'",
        agent_type='claude',
        work_dir='/tmp/knight_error'
    )
    state.create_task(task2)

    print("Test 2: Normal task")
    success2 = await handler.execute_with_retry('test-2')
    t2 = state.get_task('test-2')
    print(f"  Status: {t2.status}")
    print(f"  Success: {success2}")


if __name__ == '__main__':
    asyncio.run(test_error_recovery())
