<p align="center">
  <img src="assets/lodo-main1.png" alt="Knight System" width="140"/>
</p>

<h1 align="center">构建属于你的智能体军团</h1>

<p align="center">
  <strong>Knight System — 本地 AI Agent 集群编排器</strong>
</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/English-2ea44f?style=for-the-badge&logo=googletranslate&logoColor=white" alt="English"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/SSE-流式传输-FF6F61?style=flat-square&logo=serverfault&logoColor=white" alt="SSE Streaming"/>
  <img src="https://img.shields.io/badge/Agent-集群-8A2BE2?style=flat-square&logo=robotframework&logoColor=white" alt="Agent Cluster"/>
  <img src="https://img.shields.io/badge/本地优先-00C853?style=flat-square&logo=homeassistant&logoColor=white" alt="Local First"/>
  <img src="https://img.shields.io/badge/移动端就绪-FF9500?style=flat-square&logo=apple&logoColor=white" alt="Mobile Ready"/>
  <img src="https://img.shields.io/badge/终端+%20网页-007ACC?style=flat-square&logo=windowsterminal&logoColor=white" alt="Terminal + Web"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"/>
</p>

---

![Knight System 架构](docs/pictures/0.png)

## Knight System 是什么？

**Knight System** 是一款面向本地的、工程学深度优化的任务编排器，旨在识别、驱动并管理部署在你本机上的生产级 AI Agent。它将散落在终端中的各个独立 Agent 统一为一个协作集群，让一个人就能指挥一整支 Agent 军团，解决任何单一工具无法胜任的复杂问题。

你可以把它理解为：在你与终端中那些强大 Agent（如 Claude Code、Kimi Code、Codex 等）之间，缺失的那一层「指挥系统」。Knight 不重新定义 Agent 本身，它重新定义的是 Agent 的协作方式。

---

## 设计哲学

Knight System 的核心使命是 **最大化本地 AI Agent 集群解决复杂问题的能力**，以及 **最大化单人操作 Agent 集群的效率**。

我们针对当前生态中的两个关键痛点：
1. 现有多 Agent 框架**工程学优化程度不足**。
2. 单一商用 Agent（如 Claude Code）在面对大型模糊任务时存在**明显的复杂度上限**。

**我们不定义僵化的场景，不重复造 Agent。**  
我们只专注于让 Agent 能够规模化协作的工程学层：

1. **AI 自启动与自驱动能力** — 系统自主拆解目标、调度子任务、分发给合适的 Agent，无需人类持续看护。
2. **状态与记忆架构** — robust 的记忆与状态系统，在长时间、多步骤的工作流中保持上下文连贯。
3. **试错与工程管线能力** — 内置重试循环、故障恢复、迭代评估管线，让 Agent 集群可以探索、失败、学习并最终收敛到高质量输出。
4. **主动学习能力** — 系统会从执行历史中持续改进自身的规划与委派策略。
5. **Agent 集群效率最大化** — 智能负载均衡、任务并行、Agent 优选，确保集群中的每一个 Agent 都被最优利用。

> **一句话总结：** Knight 将市面上已经打磨到极致的生产级 Agent 二次武装，赋予它们更卓越的协调、记忆与试错基础设施，让你可以把繁重的任务管理工作外包给系统本身。

---

## 核心能力

### 1. 直接驱动你已有的 Agent
Knight 直接调用并驱动本机上已安装的强力 Agent。我们不再从头造一个新的 Agent，而是把 Claude Code、Kimi Code、Codex 等视为专业工人。Knight 模拟人类专家打开终端窗口、布置子任务、收集结果、评估质量、再布置下一步的完整流程——只不过它是自主的、并行的、以机器速度运行的。

### 2. 智能任务拆解与规划
面对一个高层目标，Knight 自动将其拆解为工程管线，分配给最合适的 Agent，并迭代评估进展。只在最有价值的决策节点才请求人类反馈。

### 3. 记忆与状态管理
专为长程项目设计的记忆层，能够在正确的时间压缩并呈现正确的上下文。之前的尝试、中间结果、学习到的模式都会被保存并复用，确保项目不会「失忆」。

### 4. 默认遵循工程最佳实践
Knight 通过引入健壮的软件工程模式持续演进：结构化任务图、依赖管理、健康检查、回滚机制、可观测性——让 Agent 之间的协作是可靠的，而不是脆弱的。

### 5. 统一网关 — 终端、网页与移动端
Knight 通过**统一网关**服务所有客户端：
- **终端 / CLI** — 通过 `curl` 或自定义脚本，在命令行中完全控制一切。
- **网页仪表盘** — 极致简洁的双页面界面，用于任务与 Agent 管理。
- **移动端访问** — 网关默认绑定 `0.0.0.0`，因此同一局域网内的任何设备（包括手机、平板）都可以随时监控和管理你的 Agent 军团。

---

## 工作流

![最小化人类输入](docs/pictures/2.png)

1. **接收任务输入**  
   你只需用自然语言描述目标，并可选择性地补充约束条件。仅此而已。

2. **自动拆分与规划**  
   Knight 分析目标，构建执行计划，将其拆分为适合 Agent 执行的子任务。只在歧义可能实质性影响结果时，才会向你征求反馈。

3. **部署 Agent 集群**  
   Knight 启动并直接调用本机上已安装的 Agent，为每个 Agent 精准投喂它所需的上下文。

![自动拆分任务](docs/pictures/3.png)

4. **迭代、评估、更新**  
   收集结果，对照质量标准进行评估，并更新计划。失败的步骤会自动重试或改派。循环持续，直到输出达到既定标准。

5. **交付高质量结果**  
   最终结果会被综合、格式化并呈现给你——同时完整展示每一步的执行过程。

---

## 适用场景

Knight 在以下场景中表现卓越：任何单一 Agent 的能力边界被复杂任务突破的时刻。

- **调研与情报分析** — 多源数据收集、综合整理、报告生成。
- **软件开发** — 大规模重构、跨模块功能实现、架构设计。
- **复杂设计** — 需要迭代探索、对比多种方案、输出详细文档的系统级设计。

---

## 前端预览

![前端管理 Agent 集群](docs/pictures/1.png)

Web 界面的设计理念是「究极简洁」：

- **任务页面** — 发布任务、监控实时执行、检查日志、审阅输出。
- **Agent 队列页面** — 查看所有本地检测到的 Agent、它们的能力以及当前可用性。

没有冗余的仪表盘，没有多余的菜单。只有你真正需要的两个功能。

![自动识别本地 Agent](docs/pictures/4.png)

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+（前端依赖）
- 本机已安装一个或多个本地 AI Agent（如 Claude Code、Kimi Code）

### 安装

```bash
# 克隆仓库
git clone https://github.com/firefly-hefeng/knight.git
cd knight

# 安装 Python 依赖
pip install -r api/requirements.txt

# 安装前端依赖
cd web && npm install && cd ..
```

### 启动

Knight 提供三种启动模式，适配不同使用场景：

#### 1. 网关 + 网页（桌面端推荐）
同时启动统一网关和网页仪表盘：

```bash
python3 launch.py both
```
- 网关 API: `http://localhost:8080`
- 网页仪表盘: `http://localhost:3000`

#### 2. 仅网关（无头模式 / 终端 / 手机远程）
将 Knight 作为后台编排器运行，完全通过终端或任意 HTTP 客户端控制：

```bash
python3 launch.py gateway --gateway-port 8080 --api-key your_secret_key
```

然后通过 `curl` 交互：

```bash
# 创建任务
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_secret_key" \
  -d '{"name":"重构鉴权模块","description":"将鉴权逻辑拆分为独立服务"}'

# 查看 Agent 列表
curl http://localhost:8080/api/v1/agents \
  -H "Authorization: Bearer your_secret_key"

# 流式查看任务进度（SSE）
curl http://localhost:8080/api/v1/tasks/{task_id}/stream \
  -H "Authorization: Bearer your_secret_key"
```

由于网关绑定在 `0.0.0.0`，你也可以在同一局域网下用手机或平板访问 `http://<你的电脑IP>:8080` 进行管理。

#### 3. 仅网页
如果你已在其他地方运行了网关：

```bash
python3 launch.py web --web-port 3000
```

---

## 架构一览

```
         终端 (curl / CLI 脚本)
                    │
      手机 / 平板 (同一局域网)
                    │
    网页仪表盘 (Next.js · 任务页 · Agent 队列页)
                    │
                    ▼
        ┌───────────────────────┐
        │      统一网关          │
        │  (FastAPI · 0.0.0.0)  │
        │  认证 · 路由 · SSE 流  │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │      Knight 核心引擎   │
        │  ┌─────┐ ┌─────┐ ┌────┐│
        │  │规划器│ │记忆系统│ │工程管线││
        │  └─────┘ └─────┘ └────┘│
        │  ┌─────┐ ┌─────┐ ┌────┐│
        │  │Agent│ │状态管理│ │可观测性││
        │  │ 池  │ │     │ │     ││
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

## API 亮点

- **任务管理** — `POST /api/v1/tasks`、`GET /api/v1/tasks/{id}`、`POST /api/v1/tasks/{id}/start`、`POST /api/v1/tasks/{id}/cancel`
- **流式进度** — `GET /api/v1/tasks/{id}/stream`（Server-Sent Events 实时推送）
- **Agent 管理** — `GET /api/v1/agents`、`GET /api/v1/agents/{id}`
- **会话管理** — `POST /api/v1/sessions`、`POST /api/v1/sessions/{id}/messages`
- **统计与健康** — `GET /api/v1/stats`、`GET /health`

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。

---

<p align="center">
  <strong>每个人都构建属于自己的 Agent 军团。</strong><br/>
  <img src="assets/lodo-main1.png" alt="Knight System" width="40"/>
</p>
