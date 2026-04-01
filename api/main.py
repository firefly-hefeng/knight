"""Knight System - FastAPI Backend"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio
import logging
from knight.core.agent_pool import AgentPool
from knight.core.state_manager import StateManager, TaskState
from knight.core.task_coordinator import TaskCoordinator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Knight System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 初始化核心组件
pool = AgentPool()
state = StateManager(enable_persistence=True, db_path="knight.db")
coordinator = TaskCoordinator(pool, state)

class TaskCreate(BaseModel):
    name: str
    description: str
    agent_type: str = "claude"
    work_dir: str = "/tmp"

class TaskResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    createdAt: str
    agentId: Optional[str] = None
    result: Optional[str] = None
    steps: Optional[List[dict]] = None
    progress: Optional[int] = 0
    logs: Optional[List[str]] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    status: str
    capabilities: List[str]
    currentTask: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Knight System API", "version": "1.0"}

@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    import uuid
    task_id = str(uuid.uuid4())[:8]
    logger.info(f"Creating task {task_id}: {task.name}")

    task_state = TaskState(
        task_id=task_id,
        status='pending',
        prompt=task.description,
        agent_type=task.agent_type,
        work_dir=task.work_dir
    )
    state.create_task(task_state)

    # 异步执行任务
    asyncio.create_task(coordinator.execute_task(task_id))

    return TaskResponse(
        id=task_id,
        name=task.name,
        description=task.description,
        status="pending",
        createdAt=datetime.now().isoformat(),
        agentId=task.agent_type,
        steps=[
            {"id": "1", "name": "Initialize", "status": "pending"},
            {"id": "2", "name": "Execute", "status": "pending"},
            {"id": "3", "name": "Complete", "status": "pending"}
        ]
    )

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks():
    tasks = []
    for task_id, task in state.tasks.items():
        # 根据状态计算进度
        progress = 0
        if task.status == 'running':
            progress = 50
        elif task.status == 'completed':
            progress = 100
        elif task.status == 'failed':
            progress = task.progress or 0

        steps = [
            {"id": "1", "name": "Initialize", "status": "completed" if task.status in ['running', 'completed', 'failed'] else "pending", "agent": task.agent_type},
            {"id": "2", "name": "Execute", "status": "running" if task.status == 'running' else ("completed" if task.status in ['completed', 'failed'] else "pending"), "agent": task.agent_type},
            {"id": "3", "name": "Complete", "status": "completed" if task.status == 'completed' else ("failed" if task.status == 'failed' else "pending"), "agent": task.agent_type}
        ]
        tasks.append(TaskResponse(
            id=task_id,
            name=f"Task {task_id}",
            description=task.prompt[:100],
            status=task.status,
            createdAt=task.created_at.isoformat(),
            agentId=task.agent_type,
            result=task.result,
            steps=steps,
            progress=progress,
            logs=task.logs[-5:] if task.logs else []
        ))
    return tasks

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = state.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 根据任务状态生成steps
    steps = [
        {"id": "1", "name": "Initialize", "status": "completed" if task.status in ['running', 'completed', 'failed'] else "pending", "agent": task.agent_type},
        {"id": "2", "name": "Execute", "status": "running" if task.status == 'running' else ("completed" if task.status in ['completed', 'failed'] else "pending"), "agent": task.agent_type},
        {"id": "3", "name": "Complete", "status": "completed" if task.status == 'completed' else ("failed" if task.status == 'failed' else "pending"), "agent": task.agent_type}
    ]

    return TaskResponse(
        id=task_id,
        name=f"Task {task_id}",
        description=task.prompt,
        status=task.status,
        createdAt=task.created_at.isoformat(),
        agentId=task.agent_type,
        result=task.result,
        steps=steps
    )

@app.get("/api/agents", response_model=List[AgentResponse])
async def get_agents():
    # 检查agent是否有正在执行的任务
    claude_busy = any(t.status == 'running' and t.agent_type == 'claude' for t in state.tasks.values())
    kimi_busy = any(t.status == 'running' and t.agent_type == 'kimi' for t in state.tasks.values())

    agents = [
        AgentResponse(
            id="claude",
            name="Claude Agent",
            status="busy" if claude_busy else "idle",
            capabilities=["coding", "analysis", "writing"],
            currentTask=next((t.task_id for t in state.tasks.values() if t.status == 'running' and t.agent_type == 'claude'), None)
        ),
        AgentResponse(
            id="kimi",
            name="Kimi Agent",
            status="busy" if kimi_busy else "idle",
            capabilities=["search", "translation"],
            currentTask=next((t.task_id for t in state.tasks.values() if t.status == 'running' and t.agent_type == 'kimi'), None)
        )
    ]
    return agents

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
