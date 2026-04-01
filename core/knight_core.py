"""
Knight Core - 统一管理层

所有请求（前端、网关、内部）都通过 KnightCore 处理
然后由 KnightCore 分配给具体的 Agent
"""
import asyncio
import uuid
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field

from .schemas import (
    CreateTaskRequest, TaskResponse, TaskStatus, AgentType,
    AgentInfo, SessionInfo, Message, StreamChunk, SendMessageRequest,
    CancelTaskRequest, TaskStep
)
from .state_manager import StateManager, TaskState
from .agent_pool import AgentPool
from .task_coordinator import TaskCoordinator
from .signal import Signal
from .file_cache import FileStateCache
from .profiler import QueryProfiler
from .command_queue import CommandQueue

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """会话对象"""
    id: str
    created_at: datetime
    updated_at: datetime
    messages: List[Message] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"


class KnightCore:
    """
    Knight 核心管理层
    
    职责：
    1. 统一管理所有任务（前端和网关的任务都在这里）
    2. 统一管理会话
    3. 路由决策（选择哪个 Agent）
    4. 流控和限流
    5. 监控和日志
    
    使用方式：
        core = KnightCore()
        
        # 创建任务（前端和网关都用这个）
        task = await core.create_task(CreateTaskRequest(...))
        
        # 查询任务
        task = await core.get_task(task_id)
        
        # 流式执行
        async for chunk in core.stream_task(task_id):
            print(chunk.content)
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式 - 确保只有一个 KnightCore 实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, enable_persistence: bool = True, db_path: str = "knight.db"):
        if self._initialized:
            return
        
        self._initialized = True
        
        # 核心组件
        self.state = StateManager(enable_persistence=enable_persistence, db_path=db_path)
        self.agent_pool = AgentPool()
        self.coordinator = TaskCoordinator(self.agent_pool, self.state)

        # 新增核心组件
        self.file_cache = FileStateCache(max_entries=100, max_size_mb=25)
        self.command_queue = CommandQueue()
        self.task_status_changed = Signal[str]()
        self.agent_status_changed = Signal[str]()

        # 会话管理
        self._sessions: Dict[str, Session] = {}
        self._session_lock = asyncio.Lock()

        # 统计
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "active_sessions": 0
        }

        # 事件监听
        self._listeners: List[callable] = []
        
        logger.info("KnightCore initialized")
    
    # ==================== 任务管理 ====================
    
    async def create_task(self, request: CreateTaskRequest) -> TaskResponse:
        """
        创建任务 - 所有入口（前端/Gateway）都调用这个
        
        Args:
            request: 创建任务请求
            
        Returns:
            TaskResponse: 创建的任务信息
        """
        task_id = str(uuid.uuid4())[:8]
        
        # 自动选择 Agent
        agent_type = request.agent_type
        if agent_type == AgentType.AUTO:
            agent_type = self._select_agent(request.description)
        
        # 创建任务状态
        task_state = TaskState(
            task_id=task_id,
            status=TaskStatus.PENDING,
            prompt=request.description,
            agent_type=agent_type.value,
            work_dir=request.work_dir
        )
        
        # 保存到状态管理器
        self.state.create_task(task_state)
        
        # 关联到会话
        if request.session_id:
            await self._associate_task_with_session(request.session_id, task_id)
        
        # 触发事件
        await self._emit_event("task_created", {"task_id": task_id, "agent_type": agent_type.value})
        self.task_status_changed.emit(task_id)

        logger.info(f"Task {task_id} created with agent {agent_type.value}")
        
        return self._to_task_response(task_state)
    
    async def start_task(self, task_id: str) -> TaskResponse:
        """
        启动任务执行
        
        Args:
            task_id: 任务ID
            
        Returns:
            TaskResponse: 更新后的任务信息
        """
        task = self.state.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Task {task_id} is not pending")
        
        # 异步执行任务
        asyncio.create_task(self._execute_task(task_id))
        
        return self._to_task_response(task)
    
    async def _execute_task(self, task_id: str):
        """实际执行任务"""
        try:
            await self.coordinator.execute_task(task_id)
            self._stats["completed_tasks"] += 1
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self._stats["failed_tasks"] += 1
    
    async def stream_task(self, task_id: str) -> AsyncGenerator[StreamChunk, None]:
        """
        流式获取任务执行结果
        
        Args:
            task_id: 任务ID
            
        Yields:
            StreamChunk: 流式数据块
        """
        task = self.state.get_task(task_id)
        if not task:
            yield StreamChunk(type="error", content=f"Task {task_id} not found")
            return
        
        # 启动任务
        if task.status == TaskStatus.PENDING:
            await self.start_task(task_id)
        
        # 流式监听状态变化
        last_logs = 0
        while task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            # 获取新日志
            if len(task.logs) > last_logs:
                for log in task.logs[last_logs:]:
                    yield StreamChunk(
                        type="text",
                        content=log,
                        task_id=task_id
                    )
                last_logs = len(task.logs)
            
            # 获取进度
            yield StreamChunk(
                type="progress",
                content="",
                task_id=task_id,
                metadata={"progress": task.progress, "status": task.status}
            )
            
            await asyncio.sleep(0.5)
            task = self.state.get_task(task_id)  # 刷新状态
        
        # 最终结果
        if task.status == TaskStatus.COMPLETED:
            yield StreamChunk(
                type="done",
                content=task.result or "",
                task_id=task_id,
                metadata={"status": "completed"}
            )
        elif task.status == TaskStatus.FAILED:
            yield StreamChunk(
                type="error",
                content=task.error or "Unknown error",
                task_id=task_id
            )
    
    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务信息"""
        task = self.state.get_task(task_id)
        if not task:
            return None
        return self._to_task_response(task)
    
    async def list_tasks(
        self,
        session_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        agent_type: Optional[AgentType] = None
    ) -> List[TaskResponse]:
        """列出任务"""
        tasks = []
        for task in self.state.tasks.values():
            # 过滤
            if session_id and task.task_id not in self._get_session_tasks(session_id):
                continue
            if status and task.status != status:
                continue
            if agent_type and task.agent_type != agent_type.value:
                continue
            
            tasks.append(self._to_task_response(task))
        
        # 按时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks
    
    async def cancel_task(self, request: CancelTaskRequest) -> TaskResponse:
        """取消任务"""
        task = self.state.get_task(request.task_id)
        if not task:
            raise ValueError(f"Task {request.task_id} not found")
        
        # 更新状态
        self.state.update_status(
            request.task_id,
            TaskStatus.CANCELLED,
            error=f"Cancelled by user: {request.reason or 'No reason'}"
        )
        
        return self._to_task_response(self.state.get_task(request.task_id))
    
    # ==================== Agent 管理 ====================
    
    async def list_agents(self) -> List[AgentInfo]:
        """列出所有 Agent 状态"""
        # 计算每个 agent 的负载
        claude_busy = sum(1 for t in self.state.tasks.values() 
                         if t.status == TaskStatus.RUNNING and t.agent_type == "claude")
        kimi_busy = sum(1 for t in self.state.tasks.values() 
                       if t.status == TaskStatus.RUNNING and t.agent_type == "kimi")
        
        return [
            AgentInfo(
                id="claude",
                name="Claude Agent",
                type=AgentType.CLAUDE,
                status="busy" if claude_busy > 0 else "idle",
                capabilities=["coding", "analysis", "writing", "long_context"],
                current_task_id=next((t.task_id for t in self.state.tasks.values() 
                                     if t.status == TaskStatus.RUNNING and t.agent_type == "claude"), None),
                queue_length=claude_busy
            ),
            AgentInfo(
                id="kimi",
                name="Kimi Agent",
                type=AgentType.KIMI,
                status="busy" if kimi_busy > 0 else "idle",
                capabilities=["search", "translation", "fast_response"],
                current_task_id=next((t.task_id for t in self.state.tasks.values() 
                                     if t.status == TaskStatus.RUNNING and t.agent_type == "kimi"), None),
                queue_length=kimi_busy
            )
        ]
    
    # ==================== 会话管理 ====================
    
    async def create_session(self, metadata: Optional[Dict] = None) -> SessionInfo:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:12]
        now = datetime.now()
        
        session = Session(
            id=session_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        async with self._session_lock:
            self._sessions[session_id] = session
        
        self._stats["active_sessions"] += 1
        
        return SessionInfo(
            id=session_id,
            status="active",
            created_at=now,
            updated_at=now
        )
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        return SessionInfo(
            id=session.id,
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
            task_count=len(session.task_ids),
            message_count=len(session.messages),
            metadata=session.metadata
        )
    
    async def send_message(self, request: SendMessageRequest) -> Message:
        """在会话中发送消息"""
        session = self._sessions.get(request.session_id)
        if not session:
            raise ValueError(f"Session {request.session_id} not found")
        
        message = Message(
            id=str(uuid.uuid4())[:8],
            session_id=request.session_id,
            role="user",
            content=request.content,
            created_at=datetime.now(),
            metadata=request.attachments
        )
        
        session.messages.append(message)
        session.updated_at = datetime.now()
        
        return message
    
    # ==================== 内部方法 ====================
    
    def _select_agent(self, prompt: str) -> AgentType:
        """根据提示词智能选择 Agent"""
        # 简单启发式规则
        prompt_lower = prompt.lower()
        
        # 代码相关 -> Claude
        if any(kw in prompt_lower for kw in ["code", "program", "function", "class", "debug", "fix"]):
            return AgentType.CLAUDE
        
        # 搜索相关 -> Kimi
        if any(kw in prompt_lower for kw in ["search", "find", "lookup", "translate"]):
            return AgentType.KIMI
        
        # 长文本分析 -> Claude
        if len(prompt) > 500:
            return AgentType.CLAUDE
        
        return AgentType.CLAUDE
    
    def _to_task_response(self, task: TaskState) -> TaskResponse:
        """转换 TaskState 为 TaskResponse"""
        # 生成步骤
        steps = [
            TaskStep(
                id="1",
                name="Initialize",
                status=TaskStatus.COMPLETED if task.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED] else TaskStatus.PENDING,
                agent=task.agent_type
            ),
            TaskStep(
                id="2",
                name="Execute",
                status=TaskStatus.RUNNING if task.status == TaskStatus.RUNNING else (
                    TaskStatus.COMPLETED if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else TaskStatus.PENDING
                ),
                agent=task.agent_type
            ),
            TaskStep(
                id="3",
                name="Complete",
                status=TaskStatus.COMPLETED if task.status == TaskStatus.COMPLETED else (
                    TaskStatus.FAILED if task.status == TaskStatus.FAILED else TaskStatus.PENDING
                ),
                agent=task.agent_type
            )
        ]
        
        return TaskResponse(
            task_id=task.task_id,
            name=f"Task {task.task_id}",
            description=task.prompt,
            status=task.status,
            agent_type=AgentType(task.agent_type),
            work_dir=task.work_dir,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.updated_at if task.status != TaskStatus.PENDING else None,
            result=task.result,
            error=task.error,
            progress=task.progress,
            steps=steps,
            logs=task.logs[-10:] if task.logs else []
        )
    
    async def _associate_task_with_session(self, session_id: str, task_id: str):
        """关联任务到会话"""
        session = self._sessions.get(session_id)
        if session:
            session.task_ids.append(task_id)
            session.updated_at = datetime.now()
    
    def _get_session_tasks(self, session_id: str) -> List[str]:
        """获取会话的所有任务ID"""
        session = self._sessions.get(session_id)
        return session.task_ids if session else []
    
    async def _emit_event(self, event_type: str, data: Dict):
        """触发事件"""
        for listener in self._listeners:
            try:
                await listener(event_type, data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
    
    def add_event_listener(self, listener: callable):
        """添加事件监听器"""
        self._listeners.append(listener)
    
    # ==================== 统计 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计数据"""
        return {
            **self._stats,
            "pending_tasks": len([t for t in self.state.tasks.values() if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in self.state.tasks.values() if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in self.state.tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.state.tasks.values() if t.status == TaskStatus.FAILED]),
            "total_tasks_in_db": len(self.state.tasks),
            "file_cache": self.file_cache.get_stats(),
            "command_queue_length": self.command_queue.length
        }
