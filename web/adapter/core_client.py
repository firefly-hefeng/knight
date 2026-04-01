"""
KnightCore Client - Web 前端与 KnightCore 的桥梁

这个模块让 Web 前端直接调用 KnightCore 的方法
而不需要经过 HTTP API

与 Gateway 的区别：
- Gateway: 接收 HTTP JSON 请求 → 调用 KnightCore
- Web Client: 直接导入 KnightCore → 调用方法

两者最终都调用相同的 KnightCore 方法！
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List, Optional, Dict, Any
from datetime import datetime

from ...core.knight_core import KnightCore
from ...core.schemas import (
    CreateTaskRequest, TaskResponse, TaskStatus, AgentType,
    AgentInfo, SessionInfo, Message, SendMessageRequest,
    CancelTaskRequest, StreamChunk
)


class KnightCoreClient:
    """
    KnightCore 客户端 - 供 Web 前端使用
    
    使用方式（在 Next.js API Route 中）：
        import { KnightCoreClient } from '@/adapter/core_client'
        
        const client = new KnightCoreClient();
        const task = await client.createTask({
            name: "My Task",
            description: "Do something"
        });
    
    实际这里使用的是 Python，前端通过 API Route 调用
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """单例 - 与 Gateway 共享同一个 KnightCore"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        # 获取 KnightCore 单例（与 Gateway 共享）
        self.core = KnightCore(enable_persistence=True)
    
    # ==================== 任务管理 ====================
    
    async def create_task(
        self,
        name: str,
        description: str,
        agent_type: str = "auto",
        work_dir: str = "/tmp",
        session_id: Optional[str] = None
    ) -> TaskResponse:
        """
        创建任务
        
        这与 Gateway 的 POST /api/v1/tasks 调用的是同一个 core.create_task()
        """
        request = CreateTaskRequest(
            name=name,
            description=description,
            agent_type=AgentType(agent_type) if agent_type else AgentType.AUTO,
            work_dir=work_dir,
            session_id=session_id
        )
        return await self.core.create_task(request)
    
    async def start_task(self, task_id: str) -> TaskResponse:
        """启动任务"""
        return await self.core.start_task(task_id)
    
    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务详情"""
        return await self.core.get_task(task_id)
    
    async def list_tasks(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[TaskResponse]:
        """列出任务"""
        status_enum = TaskStatus(status) if status else None
        return await self.core.list_tasks(
            session_id=session_id,
            status=status_enum
        )
    
    async def cancel_task(self, task_id: str, reason: Optional[str] = None) -> TaskResponse:
        """取消任务"""
        request = CancelTaskRequest(task_id=task_id, reason=reason)
        return await self.core.cancel_task(request)
    
    async def stream_task(self, task_id: str):
        """流式获取任务结果"""
        async for chunk in self.core.stream_task(task_id):
            yield chunk
    
    # ==================== Agent 管理 ====================
    
    async def list_agents(self) -> List[AgentInfo]:
        """列出所有 Agent"""
        return await self.core.list_agents()
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """获取 Agent 详情"""
        agents = await self.core.list_agents()
        return next((a for a in agents if a.id == agent_id), None)
    
    # ==================== 会话管理 ====================
    
    async def create_session(self, metadata: Optional[Dict] = None) -> SessionInfo:
        """创建会话"""
        return await self.core.create_session(metadata)
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话"""
        return await self.core.get_session(session_id)
    
    async def send_message(self, session_id: str, content: str) -> Message:
        """发送消息"""
        request = SendMessageRequest(session_id=session_id, content=content)
        return await self.core.send_message(request)
    
    # ==================== 统计 ====================
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.core.get_stats()
