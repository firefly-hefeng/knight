<p align="center">
  <img src="web/public/logo.png" alt="Knight System" width="120"/>
</p>

<h1 align="center">🏰 Knight System</h1>

<p align="center">
  <strong>AI Agent Task Orchestration Platform</strong>
</p>

<p align="center">
  Build your AI agents army • Never stops working • Orchestrate complex workflows
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/Next.js-16-black.svg" alt="Next.js"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"/>
</p>

---

## 🎯 What is Knight System?

Knight System is a powerful **multi-agent task orchestration platform** that enables you to:

- 🤖 **Create & Manage AI Agents** - Build your own AI agent army with different capabilities
- 📋 **Orchestrate Complex Tasks** - Break down complex workflows into manageable tasks
- 🔄 **Real-time Monitoring** - Track task execution with live updates and detailed logs
- ⚡ **High Performance** - Handle 10+ parallel tasks with intelligent scheduling
- 🎨 **Beautiful UI** - Academic-themed web interface with real-time updates

---

## ✨ Key Features

### 🎯 Task Orchestration
- **Visual Task Board** - Drag-and-drop workflow design
- **Priority Queue** - NOW/NEXT/LATER task scheduling
- **Real-time Status** - Live execution monitoring
- **Auto Retry** - Intelligent error recovery

### 🤖 Agent Management
- **Multi-Agent Support** - Claude, Kimi, and custom agents
- **Capability Tracking** - Know what each agent can do
- **Load Balancing** - Automatic agent selection
- **Status Monitoring** - Idle/Busy/Offline tracking

### ⚡ Performance
- **High Throughput** - 6.6 tasks/second
- **Parallel Execution** - 10+ concurrent tasks
- **File Caching** - LRU cache with 50%+ hit rate
- **Performance Profiling** - Built-in query profiler

### 🔧 Developer Experience
- **Event System** - Subscribe to task/agent events
- **RESTful API** - Complete backend API
- **TypeScript Frontend** - Type-safe React components
- **Comprehensive Tests** - Unit, integration, and e2e tests

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.12+
python3 --version

# Node.js 18+ (for frontend)
node --version
```

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/knight.git
cd knight

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd web
npm install
cd ..
```

### Launch

```bash
# Start both backend and frontend
python3 launch.py both

# Or start separately
python3 launch.py web --web-port 3001    # Backend API
python3 launch.py gateway --gateway-port 8000  # Gateway
```

Visit `http://localhost:3000` to see the web interface.

---

## 💡 Usage Examples

### Create a Task via API

```python
import requests

response = requests.post('http://localhost:3001/tasks', json={
    'name': 'Build Calculator',
    'description': 'Create a Python calculator with add/subtract functions'
})

task = response.json()
print(f"Task created: {task['id']}")
```

### Subscribe to Events

```python
from core.knight_core import KnightCore

core = KnightCore()

# Subscribe to task status changes
core.task_status_changed.subscribe(
    lambda task_id: print(f"Task {task_id} status changed")
)
```

### Use File Cache

```python
from core.file_cache import FileStateCache

cache = FileStateCache()
cache.set('/path/to/file.txt', 'content')

# Later...
state = cache.get('/path/to/file.txt')
print(f"Cache hit rate: {cache.get_stats()['hit_rate']}")
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Frontend                         │
│              (Next.js + React + TypeScript)             │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────────┐
│                   API Gateway                           │
│              (FastAPI + WebSocket)                      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  Knight Core                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Task Coordinator  │  Agent Pool  │  State Mgr  │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  FileCache │ Signal │ Profiler │ CommandQueue   │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
   ┌─────────┐              ┌─────────┐
   │ Claude  │              │  Kimi   │
   │ Adapter │              │ Adapter │
   └─────────┘              └─────────┘
```

---

## 📁 Project Structure

```
knight/
├── core/                   # Core orchestration engine
│   ├── knight_core.py     # Main orchestrator
│   ├── signal.py          # Event system
│   ├── file_cache.py      # File state cache
│   ├── profiler.py        # Performance profiler
│   └── command_queue.py   # Priority queue
├── adapters/              # Agent adapters
│   ├── claude_adapter.py  # Claude integration
│   └── kimi_adapter.py    # Kimi integration
├── api/                   # REST API
├── gateway/               # API Gateway
├── web/                   # Next.js frontend
│   ├── app/              # Pages
│   ├── components/       # React components
│   └── public/           # Static assets
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── e2e/             # End-to-end tests
└── docs/                # Documentation
```

---

## 🧩 Core Components

### Signal - Event System
Lightweight pub/sub for task and agent events.

### FileStateCache - Smart Caching
LRU cache with TTL expiration, prevents redundant file reads.

### QueryProfiler - Performance Analysis
Track execution time, identify bottlenecks with checkpoint recording.

### CommandQueue - Priority Scheduling
Three-level priority (NOW/NEXT/LATER) with FIFO ordering.

See [Core Components Guide](docs/CORE_COMPONENTS.md) for details.

---

## 🧪 Testing

```bash
# Run unit tests
python3 tests/unit/test_new_components.py

# Run integration tests
python3 tests/integration/test_knight.py

# Run e2e tests (requires backend running)
python3 tests/e2e/test_e2e.py
```

**Test Coverage:**
- ✅ Signal event system
- ✅ File cache (50%+ hit rate)
- ✅ Query profiler
- ✅ Command queue
- ✅ Task orchestration
- ✅ Agent management

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Parallel Tasks | 10+ concurrent |
| Throughput | 6.6 tasks/sec |
| Cache Hit Rate | 50%+ |
| API Response | <100ms |

---

## 🔌 API Reference

### Tasks

```bash
# Create task
POST /tasks
{
  "name": "Task name",
  "description": "Task description"
}

# Get all tasks
GET /tasks

# Get task by ID
GET /tasks/{task_id}

# Get task logs
GET /tasks/{task_id}/logs
```

### Agents

```bash
# Get all agents
GET /agents

# Get agent by ID
GET /agents/{agent_id}
```

### System

```bash
# Health check
GET /health

# Get statistics
GET /stats
```

---

## 📖 Documentation

- [Quick Start Guide](QUICKSTART.md)
- [Core Components](docs/CORE_COMPONENTS.md)
- [Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)
- [Deployment Guide](DEPLOY.md)

---

## 🛠️ Development

### Environment Variables

```bash
# Enable performance profiling
export KNIGHT_PROFILE=1

# Set API key (if needed)
export ANTHROPIC_API_KEY=your_key
```

### Code Style

```bash
# Format code
black .

# Type checking
mypy core/
```

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- [Next.js](https://nextjs.org/) - React framework
- [FastAPI](https://fastapi.tiangolo.com/) - Python web framework
- [Claude](https://www.anthropic.com/) - AI assistant

---

<p align="center">
  Made with ❤️ by the Knight Team
</p>

<p align="center">
  <a href="https://github.com/yourusername/knight">⭐ Star us on GitHub</a>
</p>
