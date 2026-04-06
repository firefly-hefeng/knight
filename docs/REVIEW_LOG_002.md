# Early Review Log #2 — Post-Improvement System Audit

- **Date**: 2026-04-05
- **Reviewer**: Claude Opus 4.6
- **Scope**: Full system re-audit after Phase 1-3 improvements
- **Baseline**: Review Log #1 (2026-04-04, commit `25fa0b2`)
- **Related**: [Review Log #1](REVIEW_LOG_001.md), [Architecture Evolution Plan](ARCHITECTURE_EVOLUTION_PLAN.md), [CC Architecture Reference](REFERENCE_CC_ARCHITECTURE.md)

---

## 1. Review Log #1 Fix Status

| # | Issue | Priority | Status | Notes |
|---|-------|----------|--------|-------|
| A-1 | Two parallel API backends | P0 | **Fixed** | `api/main.py` now delegates to `KnightCore` singleton, shares state with Gateway |
| A-2 | Singleton ineffective cross-process | P0 | **Mitigated** | Both backends use same KnightCore instance + same SQLite database |
| A-3 | TaskStatus type conflict | P0 | **Fixed** | `state_manager.py` uses `VALID_STATUSES` string tuple, `schemas.py` uses Enum, `update_status` accepts both |
| A-4 | Two independent entry points | P1 | **Fixed** | `KnightCore._execute_task` routes through `OrchestratorLoop` with `USE_ORCHESTRATOR` feature flag for fallback |
| B-1 | AgentPool Lock serialization | P1 | **Fixed** | Changed to `Semaphore(2/3)`, added `execute_batch` and `check_health` |
| B-2 | Hardcoded 3-step progress | P1 | **Partial** | DAG has real steps, but `_to_task_response` still generates hardcoded 3 steps for frontend compat |
| B-3 | SmartTaskPlanner not integrated | P1 | **Superseded** | Orchestrator uses LLM directly to generate TaskDAG, SmartTaskPlanner no longer needed |
| B-4 | Multiple unused modules | P1 | **Fixed** | `ObservabilityManager`, `ContextManager`, `Evaluator`, `Signal` all wired into KnightCore |
| B-5 | SQLite connection per operation | P2 | **Fixed** | `persistence.py` uses persistent connection + WAL mode |
| B-6 | stream_task race condition | P3 | **Not fixed** | `stream_task` still has non-atomic check-then-start |
| C-1 | Gateway CORS allows all | P2 | **Not fixed** | Gateway still `allow_origins=["*"]`; `api/main.py` also changed to `"*"` |
| C-2 | Default work_dir /tmp | P2 | **Not fixed** | Still defaults to `/tmp` |
| C-3 | API Key plain text comparison | P2 | **Not fixed** | Gateway still uses `token != self.api_key` |
| D-1 | Frontend API address inconsistency | P2 | **Fixed** | Frontend `api.ts` calls `:8000` api/main.py which routes through KnightCore |
| D-2 | Hardcoded fake homepage stats | P3 | **Fixed** | Homepage no longer shows fake 10K+/500+ data |
| D-3 | Polling instead of push | P2 | **Not fixed** | Still 2s/3s polling intervals |
| E-1 | Uneven test coverage | P3 | **Not fixed** | New modules (orchestrator, evaluator, task_dag, feedback) have no unit tests |

**Summary**: 10/17 fixed, 2 partially fixed/mitigated, 5 remain (mostly P2/P3 security and frontend).

---

## 2. New Modules Quality Assessment

### 2.1 OrchestratorLoop (`orchestrator.py`, 583 lines) — Rating: Excellent

The crown jewel of this improvement. Implements the full Plan-Execute-Evaluate loop from the Architecture Evolution Plan.

**Strengths**:
- Complete Plan → Execute → Evaluate → Iterate cycle
- 6 decision paths from ReviewVerdict: `proceed | partial_rework | rework | decompose | escalate | abort`
- Dynamic replanning via `_maybe_replan` after each subtask completion
- Checkpoint pausing for human-in-the-loop via `_checkpoint`
- Graceful degradation via `_fallback_single` when planning fails
- Global timeout prevents infinite orchestration
- Deadlock detection (no ready tasks but DAG incomplete)
- DAG persisted to SQLite after every round

**Key design decision**: Evaluation uses LLM-driven `ReviewVerdict` (understanding + forward_context + rework_instructions) instead of mechanical scoring. The coordinator synthesizes understanding rather than delegating it — exactly the CC Coordinator pattern.

**Files**: `core/orchestrator.py`

---

### 2.2 QualityEvaluator (`evaluator.py`, 205 lines) — Rating: Good

- Dual mode: `review()` (new, returns ReviewVerdict) and `evaluate()` (legacy, returns EvaluationResult)
- Three-level degradation for review parsing: JSON parse → text inference → exit code fallback
- Output preservation — no hard truncation, only head+tail at extreme lengths (8K)

**Files**: `core/evaluator.py`

---

### 2.3 TaskDAG (`task_dag.py`, 354 lines) — Rating: Excellent

- Complete DAG operations: add/remove/reset/mark_running/mark_complete/mark_failed
- Version snapshots via `snapshot()` with plan history
- Full serialization/deserialization: `to_json()`/`from_json()`
- Rich data model: `SubTask`, `AttemptRecord`, `EvaluationResult`, `ReviewVerdict`, `FailureAnalysis`, `RetryStrategy` — all with `to_dict()`/`from_dict()`

**Files**: `core/task_dag.py`

---

### 2.4 ContextManager (`context_manager.py`, ~450 lines) — Rating: Excellent

- Scene-aware compression: CODE/ERROR/DATA/LOG/GENERAL with per-scene compression ratios and min/max token limits
- Three-layer pipeline: disk persistence → micro-compact (rule-based dedup) → LLM scene-aware compression
- Artifact registry: references instead of content passing
- Knowledge base: records failed approaches and known information for future tasks
- Context budget awareness: tighter compression when many dependencies compete for budget

**Files**: `core/context_manager.py`

---

### 2.5 Orchestrator Prompts (`orchestrator_prompts.py`, 326 lines) — Rating: Excellent

- 7 carefully engineered prompts: PLANNING, EVALUATION, COORDINATOR_REVIEW, FAILURE_ANALYSIS, SYNTHESIS, REPLAN, CONTEXT_SUMMARY
- 5 scene-specific compression prompts: CODE, ERROR, DATA, LOG, GENERAL
- "Policy as prompt" philosophy: changing a prompt changes orchestration behavior without code changes
- Every prompt specifies exact JSON response format with field descriptions

**Files**: `core/orchestrator_prompts.py`

---

### 2.6 FeedbackManager (`feedback.py`, 159 lines) — Rating: Good

- Async event-driven: `asyncio.Event` blocks orchestrator, human submission wakes it
- Persistence: feedback requests and responses stored in SQLite
- Timeout handling: auto-approve after configurable timeout with logging

**Files**: `core/feedback.py`

---

### 2.7 IterationEngine (`iteration_engine.py`, 237 lines) — Rating: Fair (has issues)

- LLM-driven failure analysis: classifies root cause into 5 categories
- Strategy generation from analysis results
- DAG mutation for retry strategies

**Issues**: See N-2 and N-3 below.

**Files**: `core/iteration_engine.py`

---

### 2.8 Persistence Upgrade — Rating: Good

- Persistent connection + WAL mode
- New tables: `feedback_requests`, `attempt_history`
- Forward-compatible: `ALTER TABLE ADD COLUMN` migration for old databases
- Safe row access: `safe(idx, default)` handles missing columns in old data

**Files**: `core/persistence.py`

---

### 2.9 API Layer Improvements — Rating: Good

- `api/main.py` fully delegates to KnightCore (no more independent state)
- New endpoints: `/api/tasks/{id}/dag`, `/api/tasks/{id}/attempts`, `/api/tasks/{id}/feedback`, `/api/tasks/{id}/feedback-request`
- Frontend `api.ts` has retry with exponential backoff and 10s timeout
- Frontend types updated with `TaskDAG`, `SubTaskInfo`, `EvaluationResult`, `FeedbackRequest`

**Files**: `api/main.py`, `web/lib/api.ts`, `web/types/index.ts`

---

## 3. New Issues Found

### N-1. `stream_task` race condition persists (Carried from B-6)

```python
# knight_core.py:200-201
if task.status == TaskStatus.PENDING.value:
    await self.start_task(task_id)
```

Two concurrent `stream_task` calls can both trigger `start_task` → duplicate `_execute_task`.

**Recommendation**: Add atomic compare-and-swap to StateManager:
```python
def try_transition(self, task_id: str, from_status: str, to_status: str) -> bool:
    """Atomic status transition. Returns True if transition succeeded."""
```

**File**: `core/knight_core.py:200-201`

---

### N-2. IterationEngine `decompose` uses `run_until_complete` anti-pattern [Critical]

```python
# iteration_engine.py:180-182
result = asyncio.get_event_loop().run_until_complete(
    self.pool.execute(...)
) if not asyncio.get_event_loop().is_running() else None
```

In a running async event loop (which is always the case during orchestration), `is_running()` returns `True`, so `result` is always `None`. **The LLM-driven decompose call never executes** — it always falls through to the hardcoded "simple bisect" fallback.

**Recommendation**: Make `_apply_strategy` an `async def`, or move the LLM call to `handle_failure` (which is already async).

**File**: `core/iteration_engine.py:180-182`

---

### N-3. IterationEngine is wired but never called

`KnightCore.__init__` creates `self.iteration_engine` and injects it into `self.orchestrator.iteration_engine`, but `OrchestratorLoop.run()` never calls `self.iteration_engine`. All failure handling (rework, decompose, escalate) is done directly in the orchestrator's main loop via `ReviewVerdict` decisions.

This means 237 lines of `iteration_engine.py` are dead code in the current flow.

**Recommendation**: Either:
- (a) Integrate: call `self.iteration_engine.handle_failure()` from the `rework` branch in orchestrator, or
- (b) Remove: delete `iteration_engine.py` if ReviewVerdict fully supersedes it

**Files**: `core/iteration_engine.py`, `core/orchestrator.py`, `core/knight_core.py:97-105`

---

### N-4. Gateway API Key still not timing-safe (Carried from C-3)

```python
# http_gateway.py:98
if token != self.api_key:
```

**Recommendation**: `import hmac; if not hmac.compare_digest(token, self.api_key):`

**File**: `gateway/http_gateway.py:98`

---

### N-5. No unit tests for new modules

7 new core modules (orchestrator, evaluator, task_dag, feedback, iteration_engine, context_manager, orchestrator_prompts) have zero test files.

Priority targets for testing:
- `TaskDAG` — serialization, get_ready_subtasks, dependency resolution, snapshot
- `ReviewVerdict` — to_evaluation_result, from_dict
- `FeedbackManager` — request/submit/wait cycle, timeout behavior
- `ContextManager` — classify_output, microcompact, compute_target_tokens

---

### N-6. `_to_task_response` still generates hardcoded steps

```python
# knight_core.py — _to_task_response
steps = [
    TaskStep(id="1", name="Initialize", ...),
    TaskStep(id="2", name="Execute", ...),
    TaskStep(id="3", name="Complete", ...),
]
```

Although DAG has real subtask steps, the API response still shows fake 3-step progress. The frontend cannot see actual DAG progress.

**Recommendation**: When `task.dag_json` exists, generate steps from DAG subtasks instead:
```python
if task.dag_json:
    dag = TaskDAG.from_json(task.dag_json)
    steps = [TaskStep(id=st.id, name=st.description[:50], status=st.status, agent=st.agent_type)
             for st in dag.subtasks.values()]
```

**File**: `core/knight_core.py:_to_task_response`

---

### N-7. `api/main.py` CORS widened to `"*"`

Previously `api/main.py` restricted CORS to `localhost:3000/3001`. Now changed to `allow_origins=["*"]`, matching Gateway's permissiveness.

**File**: `api/main.py:29`

---

## 4. Architecture Maturity Assessment

| Capability | Log #1 | Current | Change |
|------------|--------|---------|--------|
| Unified backend | No (2 independent) | **Yes** (shared KnightCore) | Critical breakthrough |
| Task DAG | No (fake 3-step) | **Yes** (TaskDAG + serialization + persistence) | Critical breakthrough |
| LLM-driven planning | No | **Yes** (PLANNING_PROMPT → JSON DAG) | Critical breakthrough |
| Output evaluation | Exit code only | **Yes** (ReviewVerdict: 6 decisions) | Critical breakthrough |
| Parallel execution | Serial Lock | **Yes** (Semaphore + execute_batch) | Fixed |
| Retry with improvement | Blind retry (unwired) | **Yes** (LLM root cause analysis → strategy → DAG mutation) | Critical breakthrough |
| Context management | None | **Yes** (scene compression + disk persistence + artifact registry) | Critical breakthrough |
| Human-in-the-loop | None | **Yes** (checkpoint pause + feedback API + timeout) | Critical breakthrough |
| Agent health check | None | **Yes** (`check_health` method) | New |
| Dynamic replanning | None | **Yes** (post-subtask LLM re-evaluation of remaining plan) | Critical breakthrough |
| Crash recovery | None | **Partial** (DAG persisted to SQLite, but no restart recovery logic) | Foundation laid |

---

## 5. Architecture Evolution Plan Progress

| Phase | Item | Status |
|-------|------|--------|
| **Phase 1** | Unify API backends to KnightCore | **Done** |
| | Merge WorkflowEngine into KnightCore | **Done** (Orchestrator replaces it) |
| | Unify TaskStatus | **Done** |
| | AgentPool → Semaphore | **Done** |
| | SQLite WAL + persistent connection | **Done** |
| | API Key timing-safe comparison | Not done |
| **Phase 2** | Create Orchestrator main loop | **Done** |
| | Create Evaluator | **Done** |
| | Wire SmartTaskPlanner → TaskDAG | **Done** (direct LLM DAG generation) |
| | Wire ErrorHandler → IterationEngine | **Superseded** (ReviewVerdict handles inline) |
| | Implement real parent-child task DAG | **Done** |
| | Replace hardcoded 3-step with real DAG steps | Partial (backend has DAG, frontend still shows fake steps) |
| **Phase 3** | WAITING_FOR_FEEDBACK status | **Done** |
| | Feedback API endpoints | **Done** |
| | Plan revision from feedback | **Done** |
| | Checkpoint & recovery | **Done** (checkpoints) / Partial (recovery) |
| | Global workflow timeout | **Done** |
| | Graceful degradation | **Done** (fallback single) |
| | Agent health probe | **Done** |
| | Dynamic agent registration | Not done |

**Phase 1: ~90%** | **Phase 2: ~95%** | **Phase 3: ~70%**

---

## 6. Recommended Next Actions

| Priority | Item | Issue # | Effort |
|----------|------|---------|--------|
| P0 | Fix IterationEngine `run_until_complete` anti-pattern | N-2 | Low — make method async |
| P1 | Fix `stream_task` race condition | N-1 | Low — add atomic transition |
| P1 | Resolve IterationEngine dead code | N-3 | Low — integrate or remove |
| P1 | Frontend: show real DAG steps | N-6 | Medium — modify `_to_task_response` + frontend |
| P2 | API Key: `hmac.compare_digest` | N-4 | Trivial |
| P2 | Unit tests for new modules | N-5 | Medium |
| P3 | Crash recovery logic | — | Medium — detect stale running/waiting tasks on startup |
| P3 | Frontend SSE to replace polling | — | Medium — Gateway already has SSE |

---

## 7. Overall Assessment

This is a **transformational improvement**. The system has evolved from a pass-through single-agent wrapper into a genuine multi-agent orchestration engine with planning, evaluation, retry, context management, and human feedback capabilities.

**Most notable design decisions**:
1. **ReviewVerdict over mechanical scoring** — 6 decision paths give the orchestrator real judgment, not binary pass/fail
2. **Scene-aware context compression** — different output types get different compression strategies, far superior to naive truncation
3. **Policy-as-prompt** — all orchestration logic lives in prompts, modifiable without code changes
4. **Multi-level degradation** — LLM call failure → text inference → exit code → single-task fallthrough

**Immediate attention needed**: N-2 (IterationEngine decompose never executes in async context) and N-3 (IterationEngine is wired but never called from Orchestrator).

---

*End of Review Log #2*
