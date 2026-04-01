"""
Gateway 使用示例

演示如何通过 Gateway API 和直接调用 KnightCore 来创建任务
两者最终都会通过 KnightCore 管理层
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knight.core import KnightCore
from knight.core.schemas import CreateTaskRequest, AgentType


async def demo_direct_core():
    """直接调用 KnightCore（与 Gateway 最终调用相同）"""
    print("=" * 60)
    print("Demo 1: Direct KnightCore Usage")
    print("=" * 60)
    
    # 获取 KnightCore 实例（与 Gateway 共享）
    core = KnightCore(enable_persistence=True)
    
    # 创建任务
    request = CreateTaskRequest(
        name="Test Task",
        description="Say hello world",
        agent_type=AgentType.CLAUDE,
        work_dir="/tmp"
    )
    
    task = await core.create_task(request)
    print(f"✅ Task created: {task.id}")
    print(f"   Name: {task.name}")
    print(f"   Status: {task.status}")
    print(f"   Agent: {task.agent_type}")
    
    # 查询任务
    fetched = await core.get_task(task.id)
    print(f"\n📋 Fetched task: {fetched.id}")
    
    # 列出所有任务
    tasks = await core.list_tasks()
    print(f"\n📊 Total tasks: {len(tasks)}")
    
    # 获取统计
    stats = core.get_stats()
    print(f"\n📈 Stats: {stats}")
    
    return task.id


async def demo_gateway_api():
    """通过 Gateway API 调用（Gateway 内部调用 KnightCore）"""
    print("\n" + "=" * 60)
    print("Demo 2: Gateway API Usage (HTTP)")
    print("=" * 60)
    
    import aiohttp
    
    base_url = "http://localhost:8080"
    
    async with aiohttp.ClientSession() as session:
        # 健康检查
        async with session.get(f"{base_url}/health") as resp:
            health = await resp.json()
            print(f"✅ Gateway health: {health['data']['status']}")
        
        # 创建任务
        task_data = {
            "name": "API Task",
            "description": "Create a hello world script",
            "agent_type": "claude",
            "work_dir": "/tmp"
        }
        
        async with session.post(
            f"{base_url}/api/v1/tasks",
            json=task_data
        ) as resp:
            result = await resp.json()
            if result['success']:
                task = result['data']
                print(f"✅ Task created via API: {task['id']}")
                print(f"   Status: {task['status']}")
            else:
                print(f"❌ Error: {result['error']}")
                return None
        
        # 列出任务
        async with session.get(f"{base_url}/api/v1/tasks") as resp:
            result = await resp.json()
            print(f"\n📊 Tasks via API: {len(result['data'])}")
        
        # 列出 Agents
        async with session.get(f"{base_url}/api/v1/agents") as resp:
            result = await resp.json()
            print(f"\n🤖 Agents:")
            for agent in result['data']:
                print(f"   - {agent['name']}: {agent['status']}")


async def demo_shared_state():
    """演示 Gateway 和 KnightCore 共享状态"""
    print("\n" + "=" * 60)
    print("Demo 3: Shared State Between Gateway and Core")
    print("=" * 60)
    
    core = KnightCore(enable_persistence=True)
    
    # 1. 通过 KnightCore 创建任务
    task1 = await core.create_task(CreateTaskRequest(
        name="Core Task",
        description="Task from core",
        agent_type=AgentType.CLAUDE
    ))
    print(f"✅ Created via Core: {task1.id}")
    
    # 2. 通过 Gateway API 查询（应该能看到刚创建的任务）
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8080/api/v1/tasks") as resp:
            result = await resp.json()
            task_ids = [t['id'] for t in result['data']]
            
            if task1.id in task_ids:
                print(f"✅ Gateway sees Core task: {task1.id}")
            else:
                print(f"❌ Gateway doesn't see Core task!")
    
    # 3. 统计
    stats = core.get_stats()
    print(f"\n📈 Total tasks in system: {stats['total_tasks_in_db']}")


async def main():
    """运行所有示例"""
    print("🏰 Knight Gateway Usage Examples")
    print()
    
    # Demo 1: 直接调用 KnightCore
    await demo_direct_core()
    
    # Demo 2: 通过 Gateway API
    try:
        await demo_gateway_api()
    except Exception as e:
        print(f"\n⚠️  Gateway demo skipped (is Gateway running?): {e}")
    
    # Demo 3: 共享状态
    try:
        await demo_shared_state()
    except Exception as e:
        print(f"\n⚠️  Shared state demo skipped: {e}")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
