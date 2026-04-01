#!/usr/bin/env python3
"""
Knight 启动脚本

同时启动 Gateway 和 Web 前端
或者单独启动其中之一
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
        choices=["gateway", "web", "both"],
        default="both",
        nargs="?",
        help="启动模式: gateway (仅网关), web (仅前端), both (两者)"
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
    
    if args.mode == "gateway":
        print("Mode: Gateway Only")
        print(f"API Endpoint: http://localhost:{args.gateway_port}")
        print()
        asyncio.run(start_gateway(args.gateway_port, args.api_key))
    
    elif args.mode == "web":
        print("Mode: Web Frontend Only")
        print(f"Web URL: http://localhost:{args.web_port}")
        print()
        start_web(args.web_port)
    
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
