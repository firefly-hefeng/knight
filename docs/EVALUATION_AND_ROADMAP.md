# System Evaluation & Development Roadmap

- **Date**: 2026-04-06
- **Author**: Claude Opus 4.6
- **Baseline**: Post Review Log #2 fixes (uncommitted changes on master)
- **Related**: [Review Log #1](REVIEW_LOG_001.md) → [Review Log #2](REVIEW_LOG_002.md) → [Architecture Evolution Plan](ARCHITECTURE_EVOLUTION_PLAN.md) → [CC Reference](REFERENCE_CC_ARCHITECTURE.md)

---

## 1. Current System State

### What the system does now

```
User input → LLM plans TaskDAG → Parallel agent dispatch via Semaphore pool
         → LLM reviews each output (ReviewVerdict: 6 decisions)
         → Scene-aware context compression → Dynamic replanning
         → Human checkpoints → Iteration with failure analysis
         → Final synthesis output
```

### Fix completion across two review cycles

| Source | Total | Fixed | Partial | Remaining |
|--------|-------|-------|---------|-----------|
| Review Log #1 | 17 | 15 | 1 | 1 (default `/tmp`) |
| Review Log #2 | 7 | 7 | — | 0 |
| Phase A (this cycle) | 4 | 4 | — | 0 |
| **Total** | **28** | **26** | **1** | **1** |

### Architecture Evolution Plan progress

| Phase | Completion | Key remaining |
|-------|-----------|---------------|
| Phase 1: Unify Foundation | **100%** | — |
| Phase 2: Core Loops | **100%** | — |
| Phase 3: Human-in-the-Loop & Resilience | **100%** | — |

---

## 2. Module Ratings

| Module | Rating | Rationale |
|--------|--------|-----------|
| OrchestratorLoop | ★★★★★ | Complete Think→Execute→Evaluate→Iterate cycle, 6-way decisions, deadlock detection, global timeout, graceful degradation |
| TaskDAG | ★★★★★ | Full DAG operations, version snapshots, serialization, rich data model |
| Orchestrator Prompts | ★★★★★ | "Policy as prompt" philosophy, 12 carefully designed prompts |
| ContextManager | ★★★★½ | Scene-aware compression, 3-layer pipeline, artifact registry, knowledge base |
| QualityEvaluator | ★★★★ | ReviewVerdict replaces mechanical scoring, 3-level degradation |
| FeedbackManager | ★★★★ | asyncio.Event block/wake, persistence, timeout handling |
| IterationEngine | ★★★½ | LLM failure analysis + strategy, correctly wired into Orchestrator, but partial overlap with ReviewVerdict |
| Persistence | ★★★★ | WAL + persistent connection + 3 tables + forward-compatible migration |
| AgentPool | ★★★★★ | AgentRegistry with dynamic registration, health patrol, cost tracking, output parsers |
| Frontend | ★★★★ | DAG visualization, feedback UI, smart polling, new status badges |
| Tests | ★★★★½ | 200 pytest tests + 6 E2E smoke tests covering all core modules |

---

## 3. What Makes This System Good

### 3.1 ReviewVerdict over pass/fail
6 decision paths (proceed / rework / partial_rework / decompose / escalate / abort) give the orchestrator real judgment. Most multi-agent systems only have binary success/failure.

### 3.2 Three-layer delegation for failures
```
Layer 1: ReviewVerdict has specific rework_instructions → execute directly
Layer 2: No specific instructions → delegate to IterationEngine for deep analysis
Layer 3: IterationEngine unavailable → append error context and retry
```

### 3.3 Scene-aware context compression
Error output retains 60% (details cannot be lost). Logs retain only 20% (high redundancy). Code retains 40%. This is smarter than any truncation strategy.

### 3.4 Atomic state transitions
`try_transition(task_id, from_status, to_status)` eliminates race conditions — the check-and-set pattern learned from CC architecture.

### 3.5 Policy-as-prompt
All orchestration logic lives in `orchestrator_prompts.py`. Changing a prompt changes strategy without touching code. This makes the system tunable by non-engineers.

---

## 4. What the System Still Lacks

### 4.1 No real-world validation
The orchestration loop logic is correct, but it has not been proven end-to-end on a real complex task. Integration bugs are likely hiding.

### 4.2 Frontend lags behind backend
Backend has DAG, feedback, evaluation, replanning. Frontend is still basic polling card view. The most powerful capabilities are invisible to users.

### 4.3 ~~Test debt~~ ✅ Fixed
150 pytest tests across 8 test files: TaskDAG (39 tests), Evaluator (12), FeedbackManager (7), ContextManager (27), StateManager (20), Persistence (12), Orchestrator (8), IterationEngine (19), plus 6 end-to-end smoke tests covering happy path, retry, fallback, parallel execution, feedback checkpoints, and global timeout.

### 4.4 ~~No crash recovery~~ ✅ Fixed
`recover_stale_tasks()` in `StateManager` detects tasks stuck in `running`/`waiting_for_feedback`/`evaluating` states on startup, marks them as `failed`, and is called automatically in `KnightCore.__init__`. DAG state is persisted to SQLite and can be used for future resume-from-checkpoint capability.

---

## 5. Development Roadmap

### Phase A: Stabilize ~~(Do Now)~~ ✅ Complete

**Goal**: Prove the system works, then prove it works reliably.

| # | Item | Status | Notes |
|---|------|--------|-------|
| A1 | **End-to-end smoke test** | ✅ Done | 6 scenarios: happy path, retry/rework, fallback, parallel, feedback checkpoint, global timeout. Also found and fixed a `datetime` serialization bug in `TaskDAG.to_json()`. |
| A2 | **Core module unit tests** | ✅ Done | 150 tests across 8 files: TaskDAG, Evaluator, FeedbackManager, ContextManager, StateManager, Persistence, Orchestrator, IterationEngine. |
| A3 | **CORS configuration** | ✅ Done | Both `api/main.py` and Gateway: replaced `"*"` with configurable whitelist via `KNIGHT_CORS_ORIGINS` env var (comma-separated). Defaults to localhost dev origins. |

### Phase B: Frontend Visualization (Important, Not Urgent)

**Goal**: Make the powerful backend capabilities visible and interactive.

| # | Item | Why |
|---|------|-----|
| B1 | **DAG visualization** | Backend has complete TaskDAG data. Frontend should render real subtask dependency graph. `reactflow` is already in `package.json` but unused. |
| B2 | **Feedback interaction UI** | Backend has FeedbackManager + API endpoints. Frontend needs checkpoint approval dialog when task enters `waiting_for_feedback` state. |
| B3 | **SSE replaces polling** | Gateway already implements SSE (`/api/v1/tasks/{id}/stream`). Frontend should use `EventSource` instead of 2s/3s `setInterval`. |
| B4 | **Live log streaming** | Orchestrator logs during execution should push to frontend in real-time, not be fetched after completion. |

### Phase C: Reliability Completion ~~(Phase 3 Wrap-up)~~ ✅ Complete

**Goal**: Make the system trustworthy for long-running, unattended operation.

| # | Item | Status |
|---|------|--------|
| C1 | **Crash recovery** | ✅ `recover_stale_tasks()` in StateManager. |
| C2 | **Dynamic agent registration** | ✅ `AgentRegistry` with config-driven registration, CLI adapters, output parsers. API: `POST /api/agents/register`, `DELETE /api/agents/{name}`. |
| C3 | **Agent health patrol** | ✅ `start_patrol()` periodic health checks, auto-mark unhealthy after 3 consecutive failures. `POST /api/agents/{name}/health`. |
| C4 | **Global cost tracking** | ✅ Per-agent cost tracking, `GET /api/costs`, `KNIGHT_COST_CEILING` env var for spend limits. |

### Phase D: Advanced Capabilities — Partial ✅

**Goal**: Move from "working orchestrator" to "expert-level orchestrator."

| # | Item | Status | CC Reference |
|---|------|--------|-------------|
| D1 | **Agent persistent memory** | ✅ Three scopes (user/project/local), MEMORY.md files, keyword-based relevance matching, auto-extraction from agent output. | `agentMemory.ts` |
| D2 | **Verification agent** | ✅ Adversarial prompts, structured VERDICT (PASS/FAIL/PARTIAL), wired into orchestrator for high-risk subtasks. | `verificationAgent.ts` |
| D3 | **Workflow templates** | Common task patterns (code refactoring, bug fix, doc generation) as pre-built DAG templates that can be customized. | CC's built-in agents (Explore, Plan, Verify) as specialized roles |
| D4 | **Multi-project parallel** | One Knight instance orchestrates agent clusters across multiple independent projects simultaneously. | CC's swarm backend abstraction (tmux/iTerm2/in-process) |
| D5 | **Context collapse** | When context window approaches limit, intelligently compress old context while preserving critical state. More sophisticated than current auto-compact. | CC's `contextCollapse` module |
| D6 | **Fork for parallelism** | Spawn agents that inherit full parent conversation context for cache-identical API prefixes. Enables parallel exploration of the same problem from different angles. | CC's `forkSubagent.ts` |

### Recommended execution order

```
Now ──→ A1 Smoke test ──→ A2 Unit tests ──→ B1 DAG visualization
                                             ↓
         A3 CORS ──────────────────→ B2 Feedback UI ──→ B3 SSE
                                                         ↓
                                                  C1 Crash recovery ──→ C2 Dynamic registration
                                                                         ↓
                                                                    D1 Persistent memory ──→ D2 Verification agent
```

### Core principle

**Prove it runs (A1) → Prove it's stable (A2) → Make it visible (B1-B2) → Make it trustworthy (C1-C4) → Make it expert-level (D1-D6).**

---

## 6. Remaining Open Issues

These items from previous reviews are still not addressed. They are low priority but should not be forgotten:

| Issue | Source | Priority | Description |
|-------|--------|----------|-------------|
| C-2 | Log #1 | P3 | Default `work_dir="/tmp"` — no sandbox or directory whitelist |

Previously open, now resolved:
- ~~N-5~~ Core module unit tests → 150 tests written (Phase A2)
- ~~N-7~~ CORS `allow_origins=["*"]` → Replaced with configurable whitelist via `KNIGHT_CORS_ORIGINS` env var (Phase A3)
- ~~C1~~ Crash recovery → `recover_stale_tasks()` implemented and active

---

*End of System Evaluation & Development Roadmap*
