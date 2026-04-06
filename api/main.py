"""Knight System - FastAPI Backend (统一使用 KnightCore)"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

from knight.core.knight_core import KnightCore
from knight.core.schemas import (
    CreateTaskRequest, AgentType, TaskStatus as SchemaTaskStatus
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Knight System API")

# CORS: configurable via KNIGHT_CORS_ORIGINS env var (comma-separated)
# Default: localhost dev origins. Set to "*" to allow all (not recommended for production).
_cors_env = os.environ.get("KNIGHT_CORS_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else ["http://localhost:3000", "http://localhost:3001", "http://localhost:8080"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 统一使用 KnightCore 单例
core = KnightCore(enable_persistence=True, db_path="knight.db")


# ==================== 请求/响应模型 ====================

class TaskCreateRequest(BaseModel):
    name: str
    description: str
    agent_type: str = "auto"
    work_dir: str = "/tmp"


class TaskResponseModel(BaseModel):
    id: str
    name: str
    description: str
    status: str
    createdAt: str
    updatedAt: Optional[str] = None
    agentId: Optional[str] = None
    agentName: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    steps: Optional[List[dict]] = None
    progress: int = 0
    logs: Optional[List[str]] = None


class AgentResponseModel(BaseModel):
    id: str
    name: str
    status: str
    capabilities: List[str]
    currentTask: Optional[str] = None
    description: Optional[str] = None
    completedTasks: int = 0


# ==================== 辅助函数 ====================

def _task_to_response(task_resp) -> dict:
    """将 KnightCore 的 TaskResponse 转为前端格式"""
    agent_names = {"claude": "Claude Agent", "kimi": "Kimi Agent"}
    agent_type_str = task_resp.agent_type.value if hasattr(task_resp.agent_type, 'value') else str(task_resp.agent_type)

    return TaskResponseModel(
        id=task_resp.id,
        name=task_resp.name,
        description=task_resp.description,
        status=task_resp.status.value if hasattr(task_resp.status, 'value') else str(task_resp.status),
        createdAt=task_resp.created_at.isoformat() if hasattr(task_resp.created_at, 'isoformat') else str(task_resp.created_at),
        updatedAt=task_resp.updated_at.isoformat() if hasattr(task_resp.updated_at, 'isoformat') else None,
        agentId=agent_type_str,
        agentName=agent_names.get(agent_type_str, agent_type_str),
        result=task_resp.result,
        error=task_resp.error,
        steps=[
            {"id": s.id, "name": s.name, "status": s.status.value if hasattr(s.status, 'value') else str(s.status), "agent": s.agent}
            for s in (task_resp.steps or [])
        ],
        progress=task_resp.progress or 0,
        logs=task_resp.logs or []
    )


# ==================== API 路由 ====================

@app.get("/")
async def root():
    return {"message": "Knight System API", "version": "2.0", "engine": "KnightCore"}


@app.get("/health")
async def health():
    return {"status": "healthy", "engine": "KnightCore"}


@app.get("/stats")
async def stats():
    return core.get_stats()


@app.post("/api/tasks")
async def create_task(task: TaskCreateRequest):
    try:
        agent_type = AgentType(task.agent_type) if task.agent_type in [e.value for e in AgentType] else AgentType.AUTO
    except ValueError:
        agent_type = AgentType.AUTO

    request = CreateTaskRequest(
        name=task.name,
        description=task.description,
        agent_type=agent_type,
        work_dir=task.work_dir
    )

    task_resp = await core.create_task(request)

    # 自动启动任务
    try:
        await core.start_task(task_resp.id)
    except Exception as e:
        logger.warning(f"Auto-start failed for task {task_resp.id}: {e}")

    return _task_to_response(task_resp)


@app.get("/api/tasks")
async def get_tasks():
    tasks = await core.list_tasks()
    return [_task_to_response(t) for t in tasks]


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = await core.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@app.get("/api/tasks/{task_id}/logs")
async def get_task_logs(task_id: str):
    task = await core.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"logs": task.logs or []}


@app.get("/api/tasks/{task_id}/dag")
async def get_task_dag(task_id: str):
    dag = await core.get_task_dag(task_id)
    if not dag:
        raise HTTPException(status_code=404, detail="No DAG found for this task")
    return dag


@app.get("/api/tasks/{task_id}/attempts")
async def get_task_attempts(task_id: str):
    if core.state.persistence:
        attempts = core.state.persistence.load_attempts(task_id)
        return {"attempts": attempts}
    return {"attempts": []}


@app.post("/api/tasks/{task_id}/feedback")
async def submit_feedback(task_id: str, body: dict):
    action = body.get("action", "approve")
    message = body.get("message", "")
    try:
        await core.submit_feedback(task_id, action, message)
        return {"success": True, "action": action}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/tasks/{task_id}/feedback-request")
async def get_feedback_request(task_id: str):
    req = await core.get_pending_feedback(task_id)
    if not req:
        return {"pending": False}
    return {"pending": True, **req}


@app.get("/api/agents")
async def get_agents():
    agents = await core.list_agents()
    agent_descriptions = {
        "claude": "Advanced AI agent for coding, analysis, and long-context tasks",
        "kimi": "Fast AI agent for search, translation, and quick responses"
    }
    completed_counts = {}
    for t in core.state.tasks.values():
        if t.status in ('completed', 'failed'):
            agent = t.agent_type
            completed_counts[agent] = completed_counts.get(agent, 0) + (1 if t.status == 'completed' else 0)

    return [
        AgentResponseModel(
            id=a.id,
            name=a.name,
            status=a.status,
            capabilities=a.capabilities,
            currentTask=a.current_task_id,
            description=agent_descriptions.get(a.id, "AI Agent"),
            completedTasks=completed_counts.get(a.id, 0)
        )
        for a in agents
    ]


# ==================== Agent 注册 API ====================

@app.get("/api/agents/registry")
async def get_agent_registry():
    """获取所有注册的 Agent（包含健康状态）"""
    return core.get_registered_agents()


@app.post("/api/agents/register")
async def register_agent(body: dict):
    """动态注册新 Agent"""
    try:
        core.register_agent(body)
        return {"success": True, "name": body.get("name")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/agents/{agent_name}")
async def unregister_agent(agent_name: str):
    """注销 Agent"""
    if core.unregister_agent(agent_name):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Agent not found")


@app.post("/api/agents/{agent_name}/health")
async def check_agent_health(agent_name: str):
    """手动触发健康检查"""
    result = await core.check_agent_health(agent_name)
    return result


@app.post("/api/agents/health")
async def check_all_health():
    """检查所有 Agent 健康"""
    return await core.check_agent_health()


# ==================== 记忆 API ====================

@app.get("/api/memory")
async def get_memories(scope: str = None):
    """获取记忆"""
    return core.get_memories(scope)


@app.post("/api/memory")
async def add_memory(body: dict):
    """添加记忆"""
    core.add_memory(
        content=body["content"],
        scope=body.get("scope", "project"),
        tags=body.get("tags"),
        source=body.get("source", ""),
    )
    return {"success": True}


@app.get("/api/memory/search")
async def search_memories(q: str):
    """搜索记忆"""
    return core.search_memories(q)


# ==================== 成本 API ====================

@app.get("/api/costs")
async def get_costs():
    """获取成本统计"""
    registry = core.agent_pool.registry
    return {
        "total_cost_usd": round(registry.get_total_cost(), 4),
        "breakdown": {k: round(v, 4) for k, v in registry.get_cost_breakdown().items()},
        "ceiling_usd": core.cost_ceiling_usd,
        "remaining_usd": round(core.cost_ceiling_usd - registry.get_total_cost(), 4)
            if core.cost_ceiling_usd > 0 else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
