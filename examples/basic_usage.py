"""Knight 基础使用示例"""
import asyncio
from knight import WorkflowEngine


async def main():
    engine = WorkflowEngine()

    # 示例: 让Claude创建一个Python文件
    result = await engine.execute(
        user_request="Create a hello.py file that prints 'Hello from Knight!'",
        work_dir="/tmp/knight_test"
    )

    print(result)


if __name__ == '__main__':
    asyncio.run(main())
