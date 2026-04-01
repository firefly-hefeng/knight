"""Knight CLI - 命令行入口"""
import asyncio
import sys
from .core import WorkflowEngine


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m knight '<your request>'")
        sys.exit(1)

    request = sys.argv[1]
    engine = WorkflowEngine()

    print(f"🏰 Knight executing: {request}\n")
    result = await engine.execute(request)
    print(f"\n✅ Result:\n{result}")


if __name__ == '__main__':
    asyncio.run(main())
