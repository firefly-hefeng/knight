"""测试长期任务"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager, TaskState
from knight.core.long_running_task import LongRunningTask
import uuid


async def analyze_collections(collections):
    """分析收集的数据"""
    pool = AgentPool()
    result = await pool.execute(
        'claude',
        f"Analyze these {len(collections)} data samples and provide summary",
        '/tmp/knight_monitor'
    )
    return result.output


async def test_long_running():
    """测试长期监控任务"""
    pool = AgentPool()
    state = StateManager()
    monitor = LongRunningTask(pool, state)

    print("🏰 Long Running Task Test\n")
    print("Monitoring for 10 seconds (collecting every 3s)...\n")

    result = await monitor.monitor_and_collect(
        collection_prompt="Check current timestamp and write to log.txt",
        work_dir='/tmp/knight_monitor',
        interval_seconds=3,
        duration_seconds=10,
        on_complete=analyze_collections
    )

    print(f"Result: {result}")


if __name__ == '__main__':
    asyncio.run(test_long_running())
