# Knight System Backend

功能健全的 FastAPI 后端，集成核心 Agent 系统。

## 架构

```
api/main.py          # FastAPI 服务器
├── AgentPool        # Agent 管理
├── StateManager     # 状态管理
└── TaskCoordinator  # 任务协调
```

## API 端点

### 任务管理
- `POST /api/tasks` - 创建任务
- `GET /api/tasks` - 获取所有任务
- `GET /api/tasks/{id}` - 获取单个任务

### Agent 管理
- `GET /api/agents` - 获取所有 Agent

## 启动

```bash
cd api
pip install -r requirements.txt
./start.sh
```

访问: http://localhost:8000/docs
