from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskCreate(BaseModel):
    name: str
    description: str

class Task(BaseModel):
    id: str
    name: str
    description: str
    status: str
    createdAt: str
    agentId: Optional[str] = None

class Agent(BaseModel):
    id: str
    name: str
    status: str
    capabilities: List[str]
    currentTask: Optional[str] = None

tasks_db = []
agents_db = [
    {"id": "agent-1", "name": "Data Analyst", "status": "busy", "capabilities": ["analysis", "visualization"], "currentTask": "Data Analysis"},
    {"id": "agent-2", "name": "Code Reviewer", "status": "idle", "capabilities": ["code-review", "testing"]},
]

@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    new_task = {
        "id": str(len(tasks_db) + 1),
        "name": task.name,
        "description": task.description,
        "status": "pending",
        "createdAt": datetime.now().isoformat(),
    }
    tasks_db.append(new_task)
    return new_task

@app.get("/api/tasks")
async def get_tasks():
    return tasks_db

@app.get("/api/agents")
async def get_agents():
    return agents_db

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
