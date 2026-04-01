"""
Knight Core API 统一数据模型

所有接口（前端、网关、内部）都使用这些模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    """Agent类型"""
    CLAUDE = "claude"
    KIMI = "kimi"
    AUTO = "auto"  # 自动选择


# ==================== 请求模型 ====================

class CreateTaskRequest(BaseModel):
    """创建任务请求 - 前端和网关使用相同的请求"""
    name: str = Field(..., description="任务名称")
    description: str = Field(..., description="任务描述/提示词")
    agent_type: AgentType = Field(default=AgentType.AUTO, description="使用的Agent类型")
    work_dir: str = Field(default="/tmp", description="工作目录")
    session_id: Optional[str] = Field(default=None, description="关联的会话ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="消息内容")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="附件")


class CancelTaskRequest(BaseModel):
    """取消任务请求"""
    task_id: str = Field(..., description="任务ID")
    reason: Optional[str] = Field(default=None, description="取消原因")


# ==================== 响应模型 ====================

class TaskStep(BaseModel):
    """任务步骤"""
    id: str
    name: str
    status: TaskStatus
    agent: Optional[str] = None
    result: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    """任务响应 - 统一的任务数据结构"""
    id: str = Field(..., alias="task_id")
    name: str
    description: str
    status: TaskStatus
    agent_type: AgentType
    work_dir: str
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果
    result: Optional[str] = None
    error: Optional[str] = None
    
    # 进度
    progress: int = Field(default=0, ge=0, le=100)
    steps: List[TaskStep] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    
    # 关联
    session_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    sub_tasks: List[str] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True


class AgentInfo(BaseModel):
    """Agent信息"""
    id: str
    name: str
    type: AgentType
    status: Literal["idle", "busy", "offline"]
    capabilities: List[str] = Field(default_factory=list)
    current_task_id: Optional[str] = None
    queue_length: int = 0
    avg_response_time: float = 0.0


class SessionInfo(BaseModel):
    """会话信息"""
    id: str
    status: Literal["active", "paused", "closed"]
    created_at: datetime
    updated_at: datetime
    task_count: int = 0
    message_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """消息"""
    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== 流式响应 ====================

class StreamChunk(BaseModel):
    """流式响应块"""
    type: Literal["text", "tool_use", "tool_result", "progress", "error", "done"]
    content: str
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== 统一 API 响应包装 ====================

class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    request_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def ok(cls, data: Any = None, request_id: str = None) -> "ApiResponse":
        return cls(
            success=True, 
            data=data, 
            request_id=request_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        )
    
    @classmethod
    def fail(cls, message: str, code: str = None, request_id: str = None) -> "ApiResponse":
        """创建错误响应（注意：方法名不能为 'error'，因为与字段名冲突）"""
        return cls(
            success=False, 
            error=message, 
            error_code=code, 
            request_id=request_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        )


# ==================== 网关特定模型 ====================

class GatewayAuthRequest(BaseModel):
    """网关认证请求"""
    api_key: str
    client_id: Optional[str] = None
    client_version: Optional[str] = None


class GatewayAuthResponse(BaseModel):
    """网关认证响应"""
    access_token: str
    expires_in: int
    session_id: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
