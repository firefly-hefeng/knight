# Knight API Server

## 启动方式

```bash
# 方式1: 使用启动脚本
./start.sh

# 方式2: 直接运行
cd /mnt/d/lancer/knight
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API端点

- `GET /` - 健康检查
- `POST /api/tasks` - 创建任务
- `GET /api/tasks` - 获取所有任务
- `GET /api/tasks/{task_id}` - 获取单个任务
- `GET /api/agents` - 获取所有agents

## 环境变量

无需配置,使用默认设置即可。
