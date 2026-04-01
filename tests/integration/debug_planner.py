"""调试智能分解器"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from knight.core import AgentPool


async def debug_decompose():
    """调试分解输出"""
    pool = AgentPool()

    prompt = """Break this into 3-5 sequential implementation steps:
"Create a REST API with Flask: user registration, login, and profile endpoints"

Output format (numbered list only):
1. First step
2. Second step
3. Third step"""

    result = await pool.execute('claude', prompt, '/tmp/knight_api')

    print(f"Success: {result.success}")
    print(f"Output:\n{result.output}")
    print(f"Error: {result.error}")


if __name__ == '__main__':
    asyncio.run(debug_decompose())
