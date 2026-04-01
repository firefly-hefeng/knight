#!/usr/bin/env python3
"""
Knight 启动脚本

四种启动模式：
1. web - 仅 Web 前端
2. cli - 仅终端 CLI
3. both - Gateway + Web 前端（默认）
4. gateway - 仅 Gateway
"""
import asyncio
import argparse
import subprocess
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def start_gateway(port: int = 8080, api_key: str = None):
    """启动 Gateway"""
    from gateway.http_gateway import HTTPGateway
    
    gateway = HTTPGateway(host="0.0.0.0", port=port, api_key=api_key)
    print(f"🚀 Starting Gateway on http://0.0.0.0:{port}")
    await gateway.start()


def start_web(port: int = 3000):
    """启动 Web 前端"""
    print(f"🌐 Starting Web Frontend on http://localhost:{port}")
    
    # 在 web 目录启动 Next.js
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    subprocess.run(
        ["npm", "run", "dev"],
        cwd=web_dir,
        env=env,
        check=False
    )


async def start_cli(request: str = None):
    """启动终端 CLI 模式"""
    from core import WorkflowEngine
    
    engine = WorkflowEngine()
    
    if request:
        # 直接执行单次任务
        print(f"🏰 Knight executing: {request}\n")
        result = await engine.execute(request)
        print(f"\n✅ Result:\n{result}")
    else:
        # 交互式 CLI
        print("🏰 Knight Terminal CLI")
        print("输入你的任务描述，或输入 'quit' 退出\n")
        while True:
            try:
                user_input = input("> ").strip()
                if user_input.lower() in ('quit', 'exit', 'q'):
                    break
                if not user_input:
                    continue
                print()
                result = await engine.execute(user_input)
                print(f"\n✅ Result:\n{result}\n")
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                break


async def start_both(gateway_port: int = 8080, web_port: int = 3000):
    """同时启动 Gateway 和 Web"""
    # 启动 Gateway（异步）
    gateway_task = asyncio.create_task(
        start_gateway(gateway_port)
    )
    
    # 等待几秒让 Gateway 启动
    await asyncio.sleep(2)
    
    # 启动 Web（同步，会阻塞）
    try:
        start_web(web_port)
    except KeyboardInterrupt:
        gateway_task.cancel()
        try:
            await gateway_task
        except asyncio.CancelledError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Knight Launcher")
    parser.add_argument(
        "mode",
        choices=["web", "cli", "both", "gateway"],
        default="both",
        nargs="?",
        help="启动模式: web (仅前端), cli (仅终端), both (网关+前端), gateway (仅网关)"
    )
    parser.add_argument(
        "--request",
        type=str,
        default=None,
        help="CLI 模式下直接执行的单次任务请求"
    )
    parser.add_argument(
        "--gateway-port",
        type=int,
        default=8080,
        help="Gateway 端口 (默认: 8080)"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=3000,
        help="Web 前端端口 (默认: 3000)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Gateway API Key (可选)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🏰 Knight Unified Gateway System")
    print("=" * 60)
    print()
    
    if args.mode == "web":
        print("Mode: Web Frontend Only")
        print(f"Web URL: http://localhost:{args.web_port}")
        print()
        start_web(args.web_port)
    
    elif args.mode == "cli":
        print("Mode: Terminal CLI")
        print()
        if args.request:
            asyncio.run(start_cli(args.request))
        else:
            asyncio.run(start_cli())
    
    elif args.mode == "gateway":
        print("Mode: Gateway Only")
        print(f"API Endpoint: http://localhost:{args.gateway_port}")
        print()
        asyncio.run(start_gateway(args.gateway_port, args.api_key))
    
    else:  # both
        print("Mode: Gateway + Web Frontend")
        print(f"Gateway API: http://localhost:{args.gateway_port}")
        print(f"Web URL:     http://localhost:{args.web_port}")
        print()
        print("Note: Web frontend will connect to KnightCore directly")
        print()
        
        try:
            asyncio.run(start_both(args.gateway_port, args.web_port))
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")


if __name__ == "__main__":
    main()
