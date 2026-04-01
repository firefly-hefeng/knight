# Knight 统一网关架构设计

## 核心思想

**所有请求（前端、网关、内部）都通过 KnightCore 管理层，然后由 KnightCore 分配给 Agent。**

```
前端请求 ──────┐
              │
网关请求 ──────┼──▶ KnightCore ──▶ Agent Pool ──▶ Claude/Kimi
              │
内部调用 ──────┘
```

## 架构层次

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: 接入层 (Entry Points)                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │   Web Frontend  │    │  HTTP Gateway   │    │   CLI / SDK     │  │
│  │   (Next.js)     │    │   (JSON API)    │    │   (Python)      │  │
│  │                 │    │                 │    │                 │  │
│  │  - 网页交互      │    │  - REST API     │    │  - 命令行        │  │
│  │  - 表单提交      │    │  - WebSocket    │    │  - Python SDK   │  │
│  │  - 实时更新      │    │  - SSE 流式     │    │  - 脚本调用      │  │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘  │
│           │                      │                      │            │
│           │      ┌───────────────┴──────────────────────┘            │
│           │      │                                                  │
│           │      ▼                                                  │
│           │  ┌─────────────────────────────────────────────────────┐│
│           │  │  Unified Interface                                  ││
│           │  │  - 相同的请求模型 (CreateTaskRequest, etc.)         ││
│           │  │  - 相同的响应模型 (TaskResponse, etc.)              ││
│           │  │  - 相同的调用方式 (await core.create_task())       ││
│           └──┼─────────────────────────────────────────────────────┤│
└──────────────┼─────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: 核心管理层 (Knight Core)                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  KnightCore (单例)                                              ││
│  │                                                                 ││
│  │  职责：                                                         ││
│  │  1. 统一管理所有任务                                           ││
│  │     - create_task()                                            ││
│  │     - start_task()                                             ││
│  │     - get_task()                                               ││
│  │     - list_tasks()                                             ││
│  │     - cancel_task()                                            ││
│  │                                                                ││
│  │  2. 统一管理会话                                               ││
│  │     - create_session()                                         ││
│  │     - send_message()                                           ││
│  │                                                                ││
│  │  3. 智能路由                                                   ││
│  │     - _select_agent()  # 根据任务选择 Agent                    ││
│  │                                                                ││
│  │  4. 状态管理                                                   ││
│  │     - StateManager (任务状态)                                  ││
│  │     - SessionManager (会话状态)                                ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │  TaskService    │    │  SessionService │    │  AgentService   │  │
│  │  任务生命周期    │    │  会话管理       │    │  Agent 状态     │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: 执行层 (Agent Execution)                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Agent Pool                                                     ││
│  │                                                                 ││
│  │  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐ ││
│  │  │   Claude    │        │    Kimi     │        │   Custom    │ ││
│  │  │   Worker    │        │   Worker    │        │   Workers   │ ││
│  │  │             │        │             │        │             │ ││
│  │  │  - 编码     │        │  - 搜索     │        │  - 扩展     │ ││
│  │  │  - 分析     │        │  - 快速响应  │        │  - 插件     │ ││
│  │  └─────────────┘        └─────────────┘        └─────────────┘ ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 关键设计

### 1. 统一数据模型 (`core/schemas.py`)

```python
# 所有入口使用相同的请求模型
class CreateTaskRequest(BaseModel):
    name: str
    description: str
    agent_type: AgentType  # claude / kimi / auto
    work_dir: str
    session_id: Optional[str]

# 所有入口使用相同的响应模型
class TaskResponse(BaseModel):
    id: str
    name: str
    status: TaskStatus
    agent_type: AgentType
    result: Optional[str]
    progress: int
    steps: List[TaskStep]
```

### 2. Gateway 入口 (`gateway/http_gateway.py`)

```python
@app.post("/api/v1/tasks")
async def create_task(request: CreateTaskRequest):
    # 直接调用 KnightCore
    task = await core.create_task(request)
    return ApiResponse.ok(task)
```

### 3. Web 前端入口 (`web/adapter/core_client.py`)

```python
async def create_task(name, description, ...):
    # 同样的 KnightCore 调用
    request = CreateTaskRequest(...)
    return await core.create_task(request)
```

### 4. 两者共享同一个 KnightCore 实例（单例模式）

```python
# Gateway 中
core = KnightCore(enable_persistence=True)

# Web Client 中（同一个实例）
core = KnightCore(enable_persistence=True)  # 返回已存在的实例
```

## 接口对比

| 功能 | Gateway (JSON) | Web Frontend (Function) |
|------|----------------|------------------------|
| 创建任务 | `POST /api/v1/tasks` | `client.create_task()` |
| 查询任务 | `GET /api/v1/tasks/{id}` | `client.get_task()` |
| 列出任务 | `GET /api/v1/tasks` | `client.list_tasks()` |
| 取消任务 | `POST /api/v1/tasks/{id}/cancel` | `client.cancel_task()` |
| 流式结果 | `GET /api/v1/tasks/{id}/stream` | `client.stream_task()` |
| 列出 Agents | `GET /api/v1/agents` | `client.list_agents()` |

**核心点**：两者最终都调用 `KnightCore` 的同一个方法！

## 使用示例

### Gateway 使用

```bash
# 创建任务
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Task",
    "description": "Write a Python script",
    "agent_type": "claude"
  }'

# 获取任务
curl http://localhost:8080/api/v1/tasks/{task_id}

# 流式获取结果
curl http://localhost:8080/api/v1/tasks/{task_id}/stream
```

### Web 前端使用

```typescript
// app/api/tasks/route.ts
import { KnightCoreClient } from '@/adapter/core_client'

const client = new KnightCoreClient();

export async function POST(request: Request) {
  const body = await request.json();
  
  // 直接调用 KnightCore，与 Gateway 相同！
  const task = await client.create_task({
    name: body.name,
    description: body.description,
    agent_type: body.agent_type
  });
  
  return Response.json(task);
}
```

### Python SDK 使用

```python
from knight.core import KnightCore
from knight.core.schemas import CreateTaskRequest

# 直接访问 KnightCore（与 Gateway、Web 相同）
core = KnightCore(enable_persistence=True)

task = await core.create_task(CreateTaskRequest(
    name="My Task",
    description="Write code",
    agent_type="claude"
))
```

## 数据流

```
1. 用户通过 Gateway 创建任务
   
   Gateway ──▶ KnightCore.create_task() ──▶ StateManager
                                          
2. Web 前端查询任务状态
   
   Web ──▶ KnightCore.get_task() ──▶ StateManager
                                    
3. 两者访问的是同一个 StateManager！
```

## 启动方式

### 1. 单独启动 Gateway

```bash
python -m knight.gateway.http_gateway 8080
```

### 2. 单独启动 Web 前端

```bash
cd web && npm run dev  # 使用 KnightCoreClient
```

### 3. 同时启动（推荐）

```bash
# Gateway 在 8080 端口
python -m knight.gateway.http_gateway 8080 &

# Web 前端在 3000 端口  
cd web && npm run dev
```

## 优势

1. **统一管理层**：所有请求都经过 KnightCore，便于监控、限流、审计
2. **代码复用**：Gateway 和 Web 前端共享相同的业务逻辑
3. **一致体验**：无论通过 API 还是网页，行为完全一致
4. **易于扩展**：新增接入方式只需调用 KnightCore 方法
5. **状态共享**：任务状态、会话状态在所有接入点间同步

## 文件结构

```
knight/
├── core/
│   ├── __init__.py
│   ├── schemas.py          # 统一数据模型
│   ├── knight_core.py      # 核心管理层
│   ├── state_manager.py    # 状态管理
│   ├── agent_pool.py       # Agent 池
│   └── ...
├── gateway/
│   ├── __init__.py
│   └── http_gateway.py     # HTTP 网关入口
├── web/
│   ├── adapter/
│   │   └── core_client.py  # Web 前端适配器
│   └── app/                # Next.js 应用
└── ...
```

## 总结

**KnightCore 是所有请求的唯一入口**，无论是：
- HTTP Gateway 的 JSON 请求
- Web 前端的网页请求  
- Python SDK 的直接调用

都通过 **KnightCore** 统一管理，然后由 KnightCore 分配给具体的 Agent 执行。
