"""
HTTP Gateway - 直接暴露 Knight Core API

所有接口与 Web 前端调用的是完全相同的 KnightCore 方法
只是 Gateway 接收 JSON，Web 前端接收网页请求
"""
import asyncio
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

try:
    # 相对导入（当作为包的一部分时）
    from ..core.knight_core import KnightCore
    from ..core.schemas import (
        CreateTaskRequest, TaskResponse, TaskStatus, AgentType,
        ApiResponse, AgentInfo, SessionInfo, SendMessageRequest,
        CancelTaskRequest, StreamChunk, TaskStep
    )
except ImportError:
    # 绝对导入（当直接运行时）
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.knight_core import KnightCore
    from core.schemas import (
        CreateTaskRequest, TaskResponse, TaskStatus, AgentType,
        ApiResponse, AgentInfo, SessionInfo, SendMessageRequest,
        CancelTaskRequest, StreamChunk, TaskStep
    )

logger = logging.getLogger(__name__)


class HTTPGateway:
    """
    HTTP 网关 - 直接暴露 KnightCore 功能
    
    与 Web 前端的区别：
    - Gateway: 接收 JSON，返回 JSON
    - Web Frontend: 接收 form/页面交互，渲染 HTML
    
    但两者都调用相同的 KnightCore 方法！
    
    使用方式：
        gateway = HTTPGateway()
        await gateway.start()
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, api_key: Optional[str] = None):
        self.host = host
        self.port = port
        self.api_key = api_key
        
        # 获取 KnightCore 实例（单例）
        self.core = KnightCore(enable_persistence=True)
        
        # FastAPI 应用
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """创建 FastAPI 应用"""
        app = FastAPI(
            title="Knight Gateway API",
            description="统一网关接口 - 所有请求都路由到 Knight Core",
            version="1.0.0"
        )
        
        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 依赖：认证
        async def verify_auth(authorization: str = Header(None)):
            if not self.api_key:
                return True  # 未配置 API Key，跳过认证
            
            if not authorization:
                raise HTTPException(status_code=401, detail="Missing Authorization header")
            
            # 支持 "Bearer token" 或 "ApiKey key" 格式
            if authorization.startswith("Bearer "):
                token = authorization[7:]
            elif authorization.startswith("ApiKey "):
                token = authorization[7:]
            else:
                token = authorization
            
            if token != self.api_key:
                raise HTTPException(status_code=403, detail="Invalid API key")
            
            return True
        
        # ==================== 健康检查 ====================
        
        @app.get("/health")
        async def health_check():
            """健康检查"""
            stats = self.core.get_stats()
            return ApiResponse.ok({
                "status": "healthy",
                "version": "1.0.0",
                "stats": stats
            })
        
        # ==================== 任务管理 API ====================
        # 这些接口与 Web 前端调用的 KnightCore 方法完全一致
        
        @app.post("/api/v1/tasks", response_model=ApiResponse)
        async def create_task(
            request: CreateTaskRequest,
            _=Depends(verify_auth)
        ):
            """
            创建任务
            
            与 Web 前端调用的 core.create_task() 是同一个方法
            """
            try:
                task = await self.core.create_task(request)
                return ApiResponse.ok(task)
            except Exception as e:
                logger.error(f"Create task failed: {e}")
                return ApiResponse.fail(str(e), "CREATE_TASK_FAILED")
        
        @app.post("/api/v1/tasks/{task_id}/start", response_model=ApiResponse)
        async def start_task(task_id: str, _=Depends(verify_auth)):
            """启动任务"""
            try:
                task = await self.core.start_task(task_id)
                return ApiResponse.ok(task)
            except Exception as e:
                return ApiResponse.fail(str(e), "START_TASK_FAILED")
        
        @app.get("/api/v1/tasks/{task_id}", response_model=ApiResponse)
        async def get_task(task_id: str, _=Depends(verify_auth)):
            """获取任务详情"""
            task = await self.core.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return ApiResponse.ok(task)
        
        @app.get("/api/v1/tasks", response_model=ApiResponse)
        async def list_tasks(
            session_id: Optional[str] = None,
            status: Optional[TaskStatus] = None,
            agent_type: Optional[AgentType] = None,
            _=Depends(verify_auth)
        ):
            """列出任务"""
            tasks = await self.core.list_tasks(
                session_id=session_id,
                status=status,
                agent_type=agent_type
            )
            return ApiResponse.ok(tasks)
        
        @app.post("/api/v1/tasks/{task_id}/cancel", response_model=ApiResponse)
        async def cancel_task(
            task_id: str,
            request: CancelTaskRequest,
            _=Depends(verify_auth)
        ):
            """取消任务"""
            try:
                task = await self.core.cancel_task(request)
                return ApiResponse.ok(task)
            except Exception as e:
                return ApiResponse.fail(str(e), "CANCEL_TASK_FAILED")
        
        @app.get("/api/v1/tasks/{task_id}/stream")
        async def stream_task(task_id: str, _=Depends(verify_auth)):
            """
            流式获取任务执行结果
            
            返回 SSE (Server-Sent Events) 流
            """
            async def event_generator():
                async for chunk in self.core.stream_task(task_id):
                    yield f"data: {chunk.json()}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        
        # ==================== Agent 管理 API ====================
        
        @app.get("/api/v1/agents", response_model=ApiResponse)
        async def list_agents(_=Depends(verify_auth)):
            """列出所有 Agent"""
            agents = await self.core.list_agents()
            return ApiResponse.ok(agents)
        
        @app.get("/api/v1/agents/{agent_id}", response_model=ApiResponse)
        async def get_agent(agent_id: str, _=Depends(verify_auth)):
            """获取 Agent 详情"""
            agents = await self.core.list_agents()
            agent = next((a for a in agents if a.id == agent_id), None)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            return ApiResponse.ok(agent)
        
        # ==================== 会话管理 API ====================
        
        @app.post("/api/v1/sessions", response_model=ApiResponse)
        async def create_session(_=Depends(verify_auth)):
            """创建新会话"""
            session = await self.core.create_session()
            return ApiResponse.ok(session)
        
        @app.get("/api/v1/sessions/{session_id}", response_model=ApiResponse)
        async def get_session(session_id: str, _=Depends(verify_auth)):
            """获取会话信息"""
            session = await self.core.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return ApiResponse.ok(session)
        
        @app.post("/api/v1/sessions/{session_id}/messages", response_model=ApiResponse)
        async def send_message(
            session_id: str,
            content: str,
            _=Depends(verify_auth)
        ):
            """发送消息"""
            message = await self.core.send_message(
                SendMessageRequest(session_id=session_id, content=content)
            )
            return ApiResponse.ok(message)
        
        # ==================== 统计 API ====================
        
        @app.get("/api/v1/stats", response_model=ApiResponse)
        async def get_stats(_=Depends(verify_auth)):
            """获取系统统计"""
            stats = self.core.get_stats()
            return ApiResponse.ok(stats)
        
        return app
    
    async def start(self):
        """启动网关"""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        logger.info(f"Knight Gateway starting on http://{self.host}:{self.port}")
        await server.serve()


# 简单的启动脚本
if __name__ == "__main__":
    import sys
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    
    gateway = HTTPGateway(port=port, api_key=api_key)
    asyncio.run(gateway.start())
