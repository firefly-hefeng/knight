# Architecture Evolution Plan — Towards "Human Expert" Orchestrator

- **Date**: 2026-04-04
- **Author**: Claude Opus 4.6
- **Baseline**: commit `25fa0b2` (master)
- **Related**: [Review Log #1](REVIEW_LOG_001.md)

---

## 1. Vision vs Current State

### Target Vision

The orchestrator should behave like a human expert:

1. **Think & plan** — decompose ambiguous goals into structured task DAGs
2. **Deploy agent cluster** — assign subtasks to the best agents, in parallel
3. **Evaluate output** — judge whether agent results meet quality standards
4. **Retry & improve** — analyze failures, adjust strategy, retry
5. **Run reliably** — handle timeouts, crashes, restarts gracefully
6. **Accept human feedback** — pause at key decision points, incorporate input, continue

### What the system actually does today

```
User input → hand entire request to one Agent → return raw output
```

No planning. No evaluation. No retry logic. No human-in-the-loop. No real parallelism.

---

## 2. The Three Missing Core Loops

The gap is not a list of features — it is **three fundamental loops** that don't exist yet:

```
┌─────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                          │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Loop 1: Plan → Execute → Evaluate               │   │
│  │                                                    │   │
│  │   [Planner]──→[Agent Cluster]──→[Evaluator]       │   │
│  │       ↑                              │             │   │
│  │       └──── not good enough ─────────┘             │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Loop 2: Fail → Analyze → Adjust → Retry         │   │
│  │                                                    │   │
│  │   [Error]──→[Diagnosis]──→[Strategy Change]       │   │
│  │       ↑          │             │                   │   │
│  │       └── still failing ──────┘                   │   │
│  │                  └── switch agent / modify prompt  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Loop 3: Present → Wait → Receive → Continue      │   │
│  │                                                    │   │
│  │   [Checkpoint]──→[Human Review]──→[Feedback]      │   │
│  │                                        │           │   │
│  │                       ┌────────────────┘           │   │
│  │                       ↓                            │   │
│  │                  [Revise Plan]                     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Capability Gap Analysis (7 Dimensions)

### 3.1 Task Decomposition & Planning

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| LLM-driven goal decomposition into DAG | `TaskPlanner` passes entire request as single task | **Critical** |
| Dynamic parallel/serial/map-reduce decisions | `WorkflowPattern` implemented but never called | Wiring |
| Agent-capability-aware planning | `AgentSelector` implemented but never called | Wiring |
| Re-planning when subtasks fail | None | **Critical** |

### 3.2 Agent Cluster Management

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Multiple same-type agents running in parallel | `asyncio.Lock()` enforces strict serialization | **Critical** |
| Dynamic agent discovery and registration | Hardcoded Claude + Kimi | Medium |
| Agent health checks | None | Medium |
| Load balancing | None | Medium |

### 3.3 Task State Management

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Real task DAG with parent-child relationships | `TaskResponse` has fields but never populated | **Critical** |
| Cross-process/restart state consistency | Two independent StateManagers exist | **Critical** |
| Real-time progress from actual execution | Hardcoded 3-step fake progress | Medium |

### 3.4 Output Evaluation

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Quality assessment of agent outputs | Only checks `process.returncode == 0` | **Critical** |
| Multi-agent output comparison | None | Large |
| Result synthesis and summarization | `ResultAggregator` just concatenates strings | Medium |

### 3.5 Retry & Rollback

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Automatic retry on failure | `ErrorHandler` implemented but not wired | Wiring |
| Failure-aware strategy adjustment | None — retry just re-runs same thing | **Critical** |
| Rollback to last known good state | None | Large |
| Learning from errors | None | Large |

### 3.6 Reliability & Resilience

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Global workflow timeout | Only per-adapter timeout (300s) | Medium |
| Graceful degradation | One subtask failure stops entire workflow | Medium |
| Crash recovery (resume after restart) | SQLite has data but no recovery logic | Medium |
| Stuck task detection | None | Medium |

### 3.7 Human-in-the-Loop

| What's needed | Current state | Gap |
|---------------|---------------|-----|
| Pause workflow for human approval | None — fully automatic | **Critical** |
| Accept feedback and revise plan | None | **Critical** |
| Interactive decision points | None | **Critical** |

---

## 4. Evolution Strategy: Three-Phase Convergence

**Principle**: Not a rewrite. Each phase produces a working system that is strictly better than the previous one. Each phase can be stabilized independently.

---

### Phase 1: Unify the Foundation

**Goal**: Eliminate architectural contradictions. Create a single, consistent backbone.

**Scope**:

```
Before:                              After:
                                     
  CLI ──→ WorkflowEngine             CLI ──→ KnightCore
  Web ──→ api/main.py (:8000)        Web ──→ HTTPGateway (:8080) ──→ KnightCore
  curl ──→ HTTPGateway (:8080)       curl ──→ HTTPGateway (:8080) ──→ KnightCore
  Feishu ──→ KnightCore              Feishu ──→ KnightCore
                                     
  (4 entry points, 2 state stores)   (4 entry points, 1 state store)
```

**Changes**:

| # | Change | Resolves |
|---|--------|----------|
| 1 | Delete `api/main.py`, update `web/lib/api.ts` to point to `:8080` Gateway | A-1, D-1 |
| 2 | Absorb `WorkflowEngine` logic into `KnightCore` (planner + aggregator) | A-4 |
| 3 | Single `TaskStatus` definition in `core/schemas.py`, remove duplicate in `state_manager.py` | A-3 |
| 4 | `AgentPool`: replace `Lock` with `Semaphore(n)` | B-1 |
| 5 | `persistence.py`: maintain single connection, enable WAL | B-5 |
| 6 | `gateway/http_gateway.py`: use `hmac.compare_digest()` for API key | C-3 |
| 7 | Fix `stream_task` race condition (check-and-set atomically) | B-6 |

**Risk**: Low. This is plumbing work — no new business logic.

**Outcome**: One entry point, one state store, one truth. Clean foundation for Phase 2.

---

### Phase 2: Wire the Core Loops

**Goal**: Build the Plan-Execute-Evaluate loop using modules that already exist but are disconnected.

**New component — `Orchestrator`** (the "human expert brain"):

```
class Orchestrator:
    """
    The central intelligence loop.
    
    Replaces the current "pass request directly to one agent" flow with:
    1. Use SmartTaskPlanner to decompose goal into subtask DAG
    2. Use AgentSelector to assign best agent per subtask
    3. Use TaskCoordinator to execute DAG (now with parallelism)
    4. Use Evaluator to judge each subtask output
    5. Use ErrorHandler to retry/adjust on failure
    6. Use ResultAggregator to synthesize final output
    """
    
    async def run(self, goal: str, work_dir: str) -> OrchestratorResult:
        # Phase: Plan
        plan = await self.planner.plan(goal, work_dir)       # SmartTaskPlanner
        plan = self.assign_agents(plan)                       # AgentSelector
        
        # Phase: Execute + Evaluate (loop)
        for round in range(max_rounds):
            results = await self.coordinator.run_workflow(plan)
            evaluation = await self.evaluator.evaluate(goal, results)
            
            if evaluation.satisfactory:
                break
            
            # Phase: Adjust
            plan = await self.planner.revise(plan, evaluation.feedback)
        
        # Phase: Synthesize
        return self.aggregator.synthesize(results)
```

**Changes**:

| # | Change | New/Existing |
|---|--------|-------------|
| 1 | Create `core/orchestrator.py` — the main loop | **New** |
| 2 | Create `core/evaluator.py` — uses Agent to judge Agent output | **New** |
| 3 | Wire `SmartTaskPlanner` into Orchestrator | Existing, unwired |
| 4 | Wire `AgentSelector` into Orchestrator | Existing, unwired |
| 5 | Wire `ErrorHandler` into TaskCoordinator | Existing, unwired |
| 6 | Wire `WorkflowPattern` into SmartTaskPlanner output | Existing, unwired |
| 7 | Implement real parent-child task relationships in StateManager | Extend existing |
| 8 | Replace hardcoded 3-step progress with real DAG steps | Fix existing |

**Risk**: Medium. Core logic change, but built on tested components.

**Outcome**: System can decompose → parallel execute → evaluate → retry. The first two loops work.

---

### Phase 3: Human-in-the-Loop & Resilience

**Goal**: Close the third loop (human feedback) and harden reliability.

**Changes**:

| # | Change | Description |
|---|--------|-------------|
| 1 | Task state: add `WAITING_FOR_FEEDBACK` status | Orchestrator pauses, presents plan/result to human |
| 2 | Feedback API: `POST /api/v1/tasks/{id}/feedback` | Human approves, rejects, or modifies |
| 3 | Plan revision from feedback | Orchestrator revises plan based on human input |
| 4 | Checkpoint & recovery | Save orchestrator state to SQLite at each phase boundary |
| 5 | Crash recovery | On startup, detect `RUNNING`/`WAITING` tasks and resume or clean up |
| 6 | Global workflow timeout | Configurable per-task and per-workflow timeouts |
| 7 | Graceful degradation | If subtask fails after max retries, mark it failed but continue others |
| 8 | Agent health probe | Periodic `agent --version` check, mark offline if unreachable |
| 9 | Dynamic agent registration | Config file or API to add/remove agent types |

**Risk**: Medium-High. Requires careful state machine design.

**Outcome**: Full "human expert" behavior — plan, execute, evaluate, retry, consult human, resume.

---

## 5. Target Architecture (Post Phase 3)

```
                    ┌─────────────────────────────┐
                    │        User Interfaces       │
                    │  CLI / Web / Gateway / Feishu│
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │        KnightCore            │
                    │      (Unified Manager)       │
                    │  Sessions · Stats · Events   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       Orchestrator            │
                    │    (Human Expert Brain)       │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Plan-Execute-Evaluate    │  │
                    │  │        Loop              │  │
                    │  │                          │  │
                    │  │  SmartPlanner            │  │
                    │  │       ↓                  │  │
                    │  │  AgentSelector           │  │
                    │  │       ↓                  │  │
                    │  │  TaskCoordinator ←──┐    │  │
                    │  │       ↓             │    │  │
                    │  │  Evaluator          │    │  │
                    │  │       ↓             │    │  │
                    │  │  [satisfactory?]    │    │  │
                    │  │    no → ErrorHandler┘    │  │
                    │  │    yes → Aggregator      │  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ Human Feedback Loop      │  │
                    │  │  Checkpoint → Wait →     │  │
                    │  │  Receive → Revise Plan   │  │
                    │  └─────────────────────────┘  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │        Agent Pool            │
                    │   (Semaphore · Health Check)  │
                    │                               │
                    │  ┌───────┐  ┌───────┐  ┌──┐  │
                    │  │Claude │  │Claude │  │  │  │
                    │  │  #1   │  │  #2   │  │..│  │
                    │  └───────┘  └───────┘  └──┘  │
                    │  ┌───────┐  ┌───────┐        │
                    │  │ Kimi  │  │ Kimi  │        │
                    │  │  #1   │  │  #2   │        │
                    │  └───────┘  └───────┘        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     State & Persistence      │
                    │  StateManager (single)        │
                    │  SQLite (WAL · connection pool)│
                    │  Task DAG · Checkpoints       │
                    └─────────────────────────────┘
```

---

## 6. Phase Comparison Summary

| Capability | Now | After Phase 1 | After Phase 2 | After Phase 3 |
|------------|-----|---------------|---------------|---------------|
| Unified backend | No (2 backends) | Yes | Yes | Yes |
| Parallel agent execution | No (Lock) | Yes (Semaphore) | Yes | Yes |
| Consistent state | No (2 stores) | Yes (1 store) | Yes | Yes |
| Intelligent task planning | No | No | Yes (SmartPlanner) | Yes |
| Output evaluation | No | No | Yes (Evaluator) | Yes |
| Auto retry with adjustment | No | No | Yes (ErrorHandler) | Yes |
| Real task DAG | No | No | Yes | Yes |
| Human-in-the-loop | No | No | No | Yes |
| Crash recovery | No | No | No | Yes |
| Dynamic agent management | No | No | No | Yes |

---

## 7. Decision Rationale: Why Architecture First

The 17 bugs from Review Log #1 fall into three categories:

**Category A — Bugs that vanish after Phase 1** (8 bugs):
A-1, A-3, A-4, B-1, B-2 (partially), B-5, D-1, D-3

**Category B — Bugs that vanish after Phase 2** (4 bugs):
B-2 (fully), B-3, B-4, B-6

**Category C — Independent bugs worth fixing anytime** (5 bugs):
C-1, C-2, C-3, D-2, E-1

Fixing Category A/B bugs before their corresponding phase is wasted work — the code they live in will be restructured or deleted. Category C bugs can be fixed opportunistically during any phase.

---

*End of Architecture Evolution Plan*
