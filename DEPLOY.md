# Knight System - 启动指南

## 后端启动

```bash
cd /mnt/d/lancer/knight/api
./start.sh
```

或者:

```bash
cd /mnt/d/lancer/knight
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## 前端启动

```bash
cd /mnt/d/lancer/knight/web
npm run dev
```

访问: http://localhost:3000

## API文档

访问: http://localhost:8000/docs
