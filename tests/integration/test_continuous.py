"""测试持续测试场景"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool, StateManager
from knight.core.continuous_tester import ContinuousTester


async def test_continuous_testing():
    """测试持续测试和修复"""
    pool = AgentPool()
    state = StateManager()
    tester = ContinuousTester(pool, state)

    print("🏰 Continuous Testing Test\n")

    # 先创建一个有bug的代码
    setup_result = await pool.execute(
        'claude',
        "Create calculator.py with add(a,b) that has a bug: returns a-b instead of a+b",
        '/tmp/knight_test_fix'
    )
    print(f"Setup: {setup_result.success}\n")

    # 持续测试和修复
    print("Running test-fix cycle...")
    success = await tester.test_and_fix('/tmp/knight_test_fix', max_iterations=2)

    print(f"\nResult: {'✅ Fixed' if success else '❌ Not fixed'}")


if __name__ == '__main__':
    asyncio.run(test_continuous_testing())
