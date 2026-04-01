"""Knight 实际测试"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight import WorkflowEngine


async def test_basic():
    """测试基础功能"""
    engine = WorkflowEngine()

    print("🏰 Test 1: 简单文件创建")
    result = await engine.execute(
        user_request="Create a test.txt file with content 'Hello Knight'",
        work_dir="/tmp/knight_test"
    )
    print(f"Result length: {len(result)}")
    print(f"Result: {result}")

    # 检查任务状态
    tasks = engine.state._tasks
    print(f"\nTasks: {len(tasks)}")
    for tid, task in tasks.items():
        print(f"  {tid}: {task.status} - {task.error}")


if __name__ == '__main__':
    asyncio.run(test_basic())
