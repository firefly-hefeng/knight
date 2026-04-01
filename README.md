<p align="center">
  <img src="assets/lodo-main1.png" alt="Knight System" width="140"/>
</p>

<h1 align="center">Build Your Own Agent Army</h1>

<p align="center">
  <strong>Knight System — Local AI Agent Cluster Orchestrator</strong>
</p>

<p align="center">
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/简体中文-2ea44f?style=for-the-badge&logo=googletranslate&logoColor=white" alt="简体中文"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/SSE-Streaming-FF6F61?style=flat-square&logo=serverfault&logoColor=white" alt="SSE Streaming"/>
  <img src="https://img.shields.io/badge/Agent-Cluster-8A2BE2?style=flat-square&logo=robotframework&logoColor=white" alt="Agent Cluster"/>
  <img src="https://img.shields.io/badge/Local-First-00C853?style=flat-square&logo=homeassistant&logoColor=white" alt="Local First"/>
  <img src="https://img.shields.io/badge/Mobile-Ready-FF9500?style=flat-square&logo=apple&logoColor=white" alt="Mobile Ready"/>
  <img src="https://img.shields.io/badge/Terminal+%20Web-007ACC?style=flat-square&logo=windowsterminal&logoColor=white" alt="Terminal + Web"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"/>
</p>

---

![Knight System Architecture](docs/pictures/0.png)

## What is Knight System?

**Knight System** is a local, engineering-optimized task orchestrator designed to identify, drive, and manage production-grade AI agents deployed on your own machine. It transforms scattered local agents into a unified, collaborative cluster—enabling a single person to command an army of agents to solve complex problems that exceed the capability of any single tool.

Think of it as the missing command layer between you and the powerful agents already running in your terminal (Claude Code, Kimi Code, Codex, and more). Knight does not redefine the agent itself; it redefines how agents are orchestrated.

---

## Design Philosophy

The core mission of Knight System is to **maximize the problem-solving power of local AI agent clusters** and **maximize the efficiency of a single operator managing that cluster**.

We address two critical gaps in today's ecosystem:
1. **Low engineering optimization** in existing multi-agent frameworks.
2. **Hard complexity ceilings** in single commercial agents like Claude Code when facing large, ambiguous tasks.

**We do not define rigid scenarios. We do not rewrite agents.**  
Instead, we focus purely on the engineering layer that makes agents work together at scale:

1. **AI Self-Starting & Driving** — The system autonomously decomposes goals, schedules subtasks, and delegates to the right agent without constant human babysitting.
2. **State & Memory Architecture** — A robust, compressed memory and state system that preserves context across long-running, multi-step workflows.
3. **Trial-and-Error & Pipeline Engineering** — Built-in retry loops, failure recovery, and iterative evaluation pipelines that let agent clusters explore, fail, learn, and converge on high-quality outputs.
4. **Active Learning** — The system continuously improves its planning and delegation strategies from execution history.
5. **Maximum Cluster Efficiency** — Intelligent load balancing, task parallelism, and agent selection ensure every agent in your cluster is utilized optimally.

> **In short:** Knight takes the best production agents already optimized by their vendors, re-arms them with superior coordination, memory, and trial-and-error infrastructure, and lets you outsource the heavy lifting of task management to the system itself.

---

## Key Capabilities

### 1. Re-Arm Your Existing Agents
Knight directly calls and drives the powerful agents already installed on your machine. Rather than building yet another agent from scratch, we treat Claude Code, Kimi Code, Codex, and others as specialized workers. Knight simulates the way a human expert would open a terminal window, assign a subtask, collect the result, evaluate it, and assign the next step—except it does this autonomously, in parallel, and at machine speed.

### 2. Intelligent Task Decomposition & Planning
Given a high-level goal, Knight automatically breaks it into an engineering pipeline, assigns subtasks to the most suitable agents, and iteratively evaluates progress. Human feedback is requested only at the most valuable inflection points.

### 3. Memory & State Management
A purpose-built memory layer compresses and surfaces the right context at the right time. Long-running projects do not lose coherence; previous attempts, partial results, and learned patterns are preserved and reused.

### 4. Engineering Best Practices by Default
Knight evolves by adopting robust software engineering patterns: structured task graphs, dependency management, health checks, rollback mechanisms, and observability—so that agent collaboration is reliable, not fragile.

### 5. Unified Gateway — Terminal, Web & Mobile
Knight exposes a single **Unified Gateway** that serves every client:
- **Terminal / CLI** — Control everything from the command line via `curl` or custom scripts.
- **Web Dashboard** — A radically simple two-page interface for task and agent management.
- **Mobile Access** — The gateway binds to `0.0.0.0` by default, so you can monitor and manage your agent army from any device on your network, including your phone or tablet.

---

## Workflow

![Minimal Human Input](docs/pictures/2.png)

1. **Receive Task Input**  
   You provide a natural-language goal and optional constraints. That is all.

2. **Auto-Split & Plan**  
   Knight analyzes the goal, constructs an execution plan, and breaks it into agent-sized subtasks. It asks for human feedback only when ambiguity would materially affect the outcome.

3. **Deploy the Agent Cluster**  
   Knight launches and directly calls the local agents installed on your machine, feeding each one the precise context it needs.

![Auto Task Split](docs/pictures/3.png)

4. **Iterate, Evaluate, Update**  
   Results are collected, evaluated against quality criteria, and the plan is updated. Failed steps are retried or rerouted. The loop continues until the output meets the defined standard.

5. **Deliver High-Quality Output**  
   The final result is synthesized, formatted, and presented—with full visibility into every step of the process.

---

## Scenarios

Knight excels wherever complexity outstrips the capacity of a single agent:

- **Research & Investigation** — Multi-source data gathering, synthesis, and report generation.
- **Software Development** — Large-scale refactoring, cross-module feature implementation, and architectural design.
- **Complex Design** — Systems that require iterative exploration, comparison of alternatives, and detailed documentation.

---

## Frontend Preview

![Frontend Agent Cluster Management](docs/pictures/1.png)

The web interface is designed for ultimate simplicity:

- **Task Page** — Publish missions, monitor live execution, inspect logs, and review outputs.
- **Agent Queue Page** — View all locally detected agents, their capabilities, and current availability.

No clutter. No unnecessary dashboards. Just the two things you actually need.

![Auto-Detect Local Agents](docs/pictures/4.png)

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the frontend)
- One or more local AI agents installed (e.g., Claude Code, Kimi Code)

### Install

```bash
# Clone the repository
git clone https://github.com/firefly-hefeng/knight.git
cd knight

# Install Python dependencies
pip install -r api/requirements.txt

# Install frontend dependencies
cd web && npm install && cd ..
```

### Launch

Knight provides three launch modes to fit your workflow:

#### 1. Gateway + Web (Recommended for Desktop)
Start both the unified gateway and the web dashboard:

```bash
python3 launch.py both
```
- Gateway API: `http://localhost:8080`
- Web Dashboard: `http://localhost:3000`

#### 2. Gateway Only (Headless / Terminal / Mobile Remote)
Run Knight as a headless orchestrator and control it entirely from the terminal or any HTTP client:

```bash
python3 launch.py gateway --gateway-port 8080 --api-key your_secret_key
```

Then interact via `curl`:

```bash
# Create a task
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_secret_key" \
  -d '{"name":"Refactor auth module","description":"Split the auth logic into a separate service"}'

# List agents
curl http://localhost:8080/api/v1/agents \
  -H "Authorization: Bearer your_secret_key"

# Stream task progress (SSE)
curl http://localhost:8080/api/v1/tasks/{task_id}/stream \
  -H "Authorization: Bearer your_secret_key"
```

Because the gateway binds to `0.0.0.0`, you can also open `http://<your-pc-ip>:8080` from your phone or tablet on the same network.

#### 3. Web Only
If you already have a gateway running elsewhere:

```bash
python3 launch.py web --web-port 3000
```

---

## Architecture at a Glance

```
         Terminal (curl / CLI scripts)
                    │
         Mobile / Tablet (same network)
                    │
    Web Dashboard (Next.js · Tasks · Agent Queue)
                    │
                    ▼
        ┌───────────────────────┐
        │   Unified Gateway     │
        │  (FastAPI · 0.0.0.0)  │
        │  Auth · Routing · SSE │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │      Knight Core      │
        │  ┌─────┐ ┌─────┐ ┌────┐│
        │  │Plan │ │Mem  │ │Pipe││
        │  └─────┘ └─────┘ └────┘│
        │  ┌─────┐ ┌─────┐ ┌────┐│
        │  │Agent│ │State│ │Obs ││
        │  │Pool │ │Mgr  │     ││
        │  └─────┘ └─────┘ └────┘│
        └───────────┬───────────┘
        ┌───────────┴───────────┐
        ▼                       ▼
   ┌─────────┐             ┌─────────┐
   │ Claude  │             │  Kimi   │
   │  Code   │             │  Code   │
   └─────────┘             └─────────┘
```

---

## API Highlights

- **Tasks** — `POST /api/v1/tasks`, `GET /api/v1/tasks/{id}`, `POST /api/v1/tasks/{id}/start`, `POST /api/v1/tasks/{id}/cancel`
- **Streaming** — `GET /api/v1/tasks/{id}/stream` (Server-Sent Events for real-time progress)
- **Agents** — `GET /api/v1/agents`, `GET /api/v1/agents/{id}`
- **Sessions** — `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/messages`
- **Stats & Health** — `GET /api/v1/stats`, `GET /health`

---

## Acknowledgments

Knight System stands on the shoulders of giants. We are deeply grateful to the open-source community and the pioneering projects that have shaped our architecture, engineering patterns, and understanding of agentic systems.

### Agent Orchestration & Collaboration
- **[Anthropic Claude Code](https://www.anthropic.com/)** — For demonstrating what a production-grade coding agent can achieve, and for the recovered source in `reference/cc-recovered-main` that informed our Tool abstraction, permission systems, and non-interactive CLI invocation patterns.
- **[OpenClaw](https://openclaw.ai)** — For the elegant unified-gateway design philosophy. Knight's gateway-first architecture, multi-endpoint management, and local-first control plane are heavily inspired by OpenClaw's approach to personal AI assistants.
- **[LangChain / LangGraph](https://www.langchain.com/)** — For advancing the state of agent orchestration frameworks and establishing patterns for chaining reasoning steps and tool use.
- **[CrewAI](https://www.crewai.com/)** — For pioneering multi-agent role-based collaboration, which influenced our thinking about agent specialization and delegation.
- **[AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)** — For the early exploration of autonomous agent loops and self-directed task execution.

### Memory & State Management
- **[MemGPT / Letta](https://letta.com/)** — For groundbreaking work on memory management in LLM systems, particularly hierarchical memory (core vs. archival) and self-editing memory retrieval, which informed our state compression and context surfacing strategies.
- **[Temporal](https://temporal.io/)** — For the durable execution paradigm. Our workflow engine, checkpointing, and saga-style compensation patterns draw directly from Temporal's workflow state machine and activity abstractions (`reference/temporal-sdk-python`).

### Engineering & Infrastructure References
- **[Celery](https://docs.celeryq.dev/)** — For battle-tested task queue patterns, DAG constructs (`group`, `chain`, `chord`), and result aggregation callbacks that shaped our task distribution layer.
- **[Ray](https://www.ray.io/)** — For distributed Actor patterns and cluster scheduling concepts referenced in our agent pool design.
- **[CopilotKit](https://www.copilotkit.ai/)** — For the AG-UI Protocol and generative UI patterns that influenced our frontend-agent interaction model.
- **[shadcn/ui](https://ui.shadcn.com/)** — For the beautiful, composable React components that power our minimal web interface.

### Model Providers
- **[Anthropic](https://www.anthropic.com/)** — Claude models and the Model Context Protocol (MCP).
- **[Moonshot AI](https://www.moonshot.cn/)** — Kimi models.
- **[OpenAI](https://openai.com/)** — Codex and GPT models.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Everyone builds their own agent army.</strong><br/>
  <img src="assets/lodo-main1.png" alt="Knight System" width="40"/>
</p>
