# Architecture Gap Analysis & Upgrade Roadmap

**Date:** 2026-04-04  
**Author:** Claude Opus 4.6  
**Status:** Proposal — Pending Review  
**Prerequisite:** [Early Issue Review Log #2](EARLY_REVIEW_LOG_2.md)

---

## 1. Vision vs Current State

### Target Vision

The master orchestrator should behave like a human expert:

1. **Think & Plan** — Analyze goals, decompose into structured subtasks with dependencies
2. **Arm the Cluster** — Select and configure the right agents for each subtask
3. **Manage State** — Track all task states, contexts, and intermediate artifacts
4. **Evaluate Outputs** — Judge output quality against acceptance criteria
5. **Rollback & Iterate** — Analyze failures, adjust strategy, retry with improvements
6. **Run Robustly** — Handle failures gracefully, ensure forward progress
7. **Accept Human Feedback** — Pause at checkpoints, incorporate direction changes, continue

### Ideal Orchestration Loop

```
  Human Goal ──→ [Think/Plan] ──→ [Assign Agents] ──→ [Monitor Execution]
                     ↑                                       │
                     │                                       ▼
                [Human Feedback] ←── [Deliver/Report] ←── [Evaluate Quality]
                                                             │
                                                             ▼ (not acceptable)
                                                       [Rollback/Retry/Adapt]
```

### What Actually Exists Today

```
  Request → Wrap as single task → Send to Agent → Wait → Return raw output
```

The "brain" — thinking, evaluating, deciding, iterating — is entirely absent.

---

## 2. Missing Core Capabilities

### Capability 1: Orchestrator Brain (completely missing)

**Priority: CRITICAL — Foundation for everything else**

The system has no "thinking" step. `TaskPlanner.plan()` passes the request through unchanged. `SmartTaskPlanner` exists but only asks an Agent for a numbered list — no structured dependency analysis, no acceptance criteria, no checkpoint design.

**What's needed:**

```
OrchestratorBrain:
  ├── analyze_goal(request) → GoalAnalysis
  │     - Intent classification
  │     - Complexity assessment
  │     - Constraint extraction
  │
  ├── decompose(goal) → TaskDAG
  │     - Subtask generation with clear boundaries
  │     - Dependency graph (not just linear chains)
  │     - Per-subtask acceptance criteria
  │     - Agent assignment per subtask
  │     - Checkpoint placement (where to pause for human)
  │
  ├── decide_next(current_state) → Action
  │     - Given completed/failed/pending tasks, what to do next
  │     - May add new tasks, retry, escalate, or declare done
  │
  └── synthesize(results) → FinalOutput
        - Merge and format outputs from all subtasks
        - Quality self-check before delivery
```

**Key design choice:** The brain should be LLM-powered (calling an Agent to reason about the plan), not rule-based. This means the orchestrator itself uses an Agent (e.g., Claude) as its "thinking engine", separate from the worker Agents that execute tasks.

### Capability 2: Output Quality Evaluation (completely missing)

**Priority: HIGH**

Current behavior: `result.success` only means the CLI process exited with code 0. It says nothing about whether the output actually solves the problem.

**What's needed:**

```
QualityEvaluator:
  ├── define_criteria(subtask) → AcceptanceCriteria
  │     - Functional checks (does it compile, pass tests)
  │     - Semantic checks (does output match intent)
  │     - Quality checks (code style, completeness)
  │
  ├── evaluate(output, criteria) → EvaluationResult
  │     - Score / pass-fail per criterion
  │     - Specific failure reasons
  │     - Confidence level
  │
  └── recommend_action(eval_result) → Action
        - ACCEPT → proceed to next subtask
        - RETRY_SAME → same agent, refined prompt
        - RETRY_DIFFERENT → different agent or approach
        - ESCALATE → ask human for guidance
```

### Capability 3: Trial-and-Error Loop (skeleton exists, not wired)

**Priority: HIGH**

`ErrorHandler` does blind retries (same prompt, same agent). `ContinuousTester` has a test-fix loop but isn't integrated. Neither analyzes *why* something failed.

**What's needed:**

```
IterationEngine:
  ├── analyze_failure(task, result) → FailureAnalysis
  │     - Root cause classification
  │     - Was it a prompt issue, agent limitation, or external failure?
  │
  ├── generate_fix_strategy(analysis) → Strategy
  │     - Refine prompt with error context
  │     - Switch to a more capable agent
  │     - Break subtask into smaller pieces
  │     - Provide additional context from knowledge base
  │
  ├── rollback(task_id) → RollbackResult
  │     - Undo file changes made by failed step
  │     - Restore state to last known-good checkpoint
  │
  └── Config:
        - max_retries_per_task: int (default 3)
        - max_total_iterations: int (default 10)
        - escalation_threshold: int (after N failures, ask human)
```

### Capability 4: Human-in-the-Loop (completely missing)

**Priority: HIGH**

Current system is fire-and-forget. No way to pause, inject feedback, or gate execution.

**What's needed:**

```
HumanInteraction:
  ├── Checkpoint System
  │     - Tasks can be marked as requiring human approval before proceeding
  │     - Configurable: "always ask", "ask on uncertainty", "never ask"
  │
  ├── Feedback Injection
  │     - POST /api/v1/tasks/{id}/feedback — inject mid-flight guidance
  │     - Feedback gets incorporated into the orchestrator's next think() cycle
  │
  ├── Interactive Revision
  │     - Human reviews final output, provides modification instructions
  │     - Orchestrator translates feedback into new subtasks
  │     - Continues agent execution with revision context
  │
  └── Approval Gates
        - High-risk operations (delete files, deploy, etc.) require explicit approval
        - Configurable risk assessment per operation type
```

### Capability 5: Dynamic Replanning (completely missing)

**Priority: MEDIUM**

Current plan is static once generated. The workflow runs linearly regardless of intermediate results.

**What's needed:**

```
DynamicPlanner:
  ├── on_task_complete(task, result)
  │     - Re-evaluate remaining plan given new information
  │     - May add, remove, or reorder pending tasks
  │
  ├── on_task_fail(task, error)
  │     - Decide: retry, skip, add recovery tasks, or abort
  │     - Update downstream task dependencies
  │
  ├── on_new_discovery(info)
  │     - Agent discovers something unexpected mid-execution
  │     - Orchestrator adjusts plan to accommodate
  │
  └── Plan Versioning
        - Keep history of plan changes
        - Ability to diff "original plan" vs "current plan"
        - Rollback to previous plan version if needed
```

### Capability 6: Cross-Task Context Management (skeleton exists, too primitive)

**Priority: MEDIUM**

Current: `dep.result[:150]` — brutal truncation that destroys most context.

**What's needed:**

```
ContextManager (upgraded):
  ├── Intelligent Summarization
  │     - LLM-powered compression of task outputs
  │     - Extract key decisions, artifacts, and constraints
  │     - Maintain a "running summary" that grows with the project
  │
  ├── Knowledge Base
  │     - Accumulated facts discovered during execution
  │     - File modification history (what changed, by whom, why)
  │     - Failed approaches (avoid repeating)
  │
  ├── Context Window Budget
  │     - Track how much context each agent can handle
  │     - Prioritize most relevant context per subtask
  │     - Progressive disclosure: give summary first, full detail if needed
  │
  └── Artifact Registry
        - Track files created/modified by each subtask
        - Provide diffs to downstream tasks
        - Support rollback to previous file states
```

---

## 3. Capability Dependency Graph

```
                 Orchestrator Brain (1)
                ╱        |        ╲
               ╱         |         ╲
  Dynamic Replan (5)  Evaluation (2)  Human Feedback (4)
         ╲              |              ╱
          ╲             |             ╱
         Iteration / Trial-Error (3)
                        |
              Cross-Task Context (6)
```

**The Orchestrator Brain is the foundation.** Without it, the other capabilities have nowhere to attach.

---

## 4. Proposed Core Architecture

### 4.1 The Orchestrator Loop

The heart of the system — a continuous observe-think-act-evaluate cycle:

```python
class OrchestratorLoop:
    """
    The main orchestration loop.

    This is the 'brain' of Knight System.
    It uses an LLM (via an Agent) as its reasoning engine
    to make decisions about planning, execution, and evaluation.
    """

    async def run(self, goal: str, config: OrchestrationConfig) -> OrchestrationResult:
        # Phase 1: Understand & Plan
        plan = await self.think(goal)
        await self.checkpoint("plan_review", plan)  # optional human review

        # Phase 2: Execute & Iterate
        while not plan.is_complete():
            # Observe
            state = self.observe(plan)

            # Decide next action
            action = await self.decide(state)

            if action.type == "execute_task":
                result = await self.execute(action.task)
                evaluation = await self.evaluate(result, action.task.criteria)

                if evaluation.passed:
                    plan.mark_complete(action.task)
                    plan = await self.maybe_replan(plan, result)
                else:
                    plan = await self.handle_failure(plan, action.task, evaluation)

            elif action.type == "ask_human":
                feedback = await self.request_human_input(action.question)
                plan = await self.incorporate_feedback(plan, feedback)

            elif action.type == "done":
                break

        # Phase 3: Synthesize & Deliver
        output = await self.synthesize(plan)
        return output
```

### 4.2 Key Data Structures

```python
@dataclass
class TaskDAG:
    """Directed Acyclic Graph of subtasks"""
    tasks: Dict[str, SubTask]
    edges: List[Tuple[str, str]]  # (dependency, dependent)
    checkpoints: List[str]        # task_ids that require human approval
    version: int                  # plan version for tracking changes

@dataclass
class SubTask:
    id: str
    description: str
    agent_type: str
    acceptance_criteria: List[str]
    context_requirements: List[str]  # what context this task needs
    risk_level: str                  # low / medium / high
    max_retries: int
    status: TaskStatus
    result: Optional[TaskResult]
    evaluation: Optional[EvaluationResult]
    attempt_history: List[AttemptRecord]

@dataclass
class EvaluationResult:
    passed: bool
    score: float                    # 0.0 to 1.0
    criteria_results: Dict[str, bool]
    failure_reasons: List[str]
    recommended_action: str         # accept / retry / escalate / abort

@dataclass
class AttemptRecord:
    attempt_number: int
    agent_type: str
    prompt_used: str
    result: TaskResult
    evaluation: EvaluationResult
    duration_ms: int
    timestamp: datetime
```

### 4.3 Component Relationship

```
┌─────────────────────────────────────────────────────────┐
│                   OrchestratorLoop                       │
│                                                         │
│   ┌──────────┐  ┌───────────┐  ┌───────────────────┐   │
│   │ Planner  │  │ Evaluator │  │ IterationEngine   │   │
│   │ (LLM)    │  │ (LLM)     │  │                   │   │
│   └────┬─────┘  └─────┬─────┘  └────────┬──────────┘   │
│        │              │                  │              │
│   ┌────▼──────────────▼──────────────────▼──────────┐   │
│   │              ContextManager                      │   │
│   │  (knowledge base, summaries, artifact registry)  │   │
│   └──────────────────┬───────────────────────────────┘   │
│                      │                                   │
│   ┌──────────────────▼───────────────────────────────┐   │
│   │              StateManager                         │   │
│   │  (task DAG, status, persistence, plan versions)   │   │
│   └──────────────────┬───────────────────────────────┘   │
└──────────────────────┼───────────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │       AgentPool         │
          │  (dynamic registration) │
          └────┬──────────┬─────────┘
               │          │
          ┌────▼──┐  ┌────▼──┐
          │Claude │  │ Kimi  │  ...extensible
          └───────┘  └───────┘
```

---

## 5. Phased Implementation Roadmap

### Phase 0: Stabilize (30 min)

Fix P0 bugs from [Review Log #2](EARLY_REVIEW_LOG_2.md) to ensure a working baseline:
- P0-1: Fix `FeishuAdapter` import
- P0-2: Unify `TaskStatus` type
- P0-3: Fix frontend API port
- P0-4: Fix singleton test isolation

### Phase 1: Orchestrator Brain (Core)

**Goal:** Replace the "pass-through" planner with an LLM-driven orchestration loop.

Key deliverables:
- `OrchestratorLoop` — the main observe-think-act-evaluate cycle
- `Planner` — LLM-powered task decomposition producing a `TaskDAG`
- `SubTask` with acceptance criteria and agent assignment
- Integration with existing `AgentPool` and `StateManager`

**What changes:**
- `WorkflowEngine` replaced by `OrchestratorLoop`
- `TaskPlanner` / `SmartTaskPlanner` replaced by `Planner`
- `TaskCoordinator` becomes internal to the loop
- `StateManager` extended for DAG structure

**What stays:**
- `AgentPool`, `ClaudeAdapter`, `KimiAdapter` — unchanged
- `HTTPGateway` — API surface stays the same
- `schemas.py` — extended but backward-compatible
- Frontend — unchanged (consumes same API)

### Phase 2: Quality Evaluation + Iteration

**Goal:** The system can judge output quality and retry intelligently.

Key deliverables:
- `QualityEvaluator` — LLM-based output assessment
- `IterationEngine` — failure analysis, strategy adjustment, rollback
- `AttemptRecord` — history of all attempts per subtask
- Integration: failed evaluations trigger retry loop before marking failure

### Phase 3: Human Feedback Loop

**Goal:** Humans can steer execution at key moments.

Key deliverables:
- Checkpoint system — pause execution at designated points
- `POST /api/v1/tasks/{id}/feedback` endpoint
- Feedback incorporation into the orchestrator's next decision cycle
- Approval gates for high-risk operations
- Frontend: feedback UI in task detail view

### Phase 4: Dynamic Replanning + Context

**Goal:** Plans adapt to reality; context flows intelligently.

Key deliverables:
- Plan versioning and diffing
- Dynamic task insertion/removal/reordering
- LLM-powered context summarization
- Knowledge base and artifact registry
- Context budget management per agent

---

## 6. Bug Fix Strategy

**Principle:** Fix P0 bugs immediately (30 min). Let P1/P2 bugs resolve naturally through architecture upgrades.

| Bug Category | Action |
|-------------|--------|
| P0 (4 bugs) | Fix now — they block basic functionality and won't be superseded |
| P1-1 (two APIs) | Resolve in Phase 1 — remove `api/main.py` when `OrchestratorLoop` ships |
| P1-2 (persistence) | Resolve in Phase 1 — new `StateManager` will have complete persistence |
| P1-3 (pydantic) | Fix now — 1 line, universal |
| P1-4 (sessions) | Resolve in Phase 3 — session model redesigned with human feedback |
| P1-5 (double-start) | Resolve in Phase 1 — `OrchestratorLoop` manages all task lifecycle |
| P1-6 (feishu async) | Fix now — adapter layer won't change |
| P2-1~P2-4 (dead code) | Resolve in Phase 1~2 — integrate or remove as architecture crystallizes |
| P2-5~P2-7 | Low priority — fix opportunistically |

---

## 7. Design Principles

1. **LLM as reasoning engine, not hardcoded rules.** The orchestrator's planning, evaluation, and adaptation should all be LLM-powered. Rules are only for safety constraints and resource limits.

2. **Separation of thinking and doing.** The orchestrator "thinks" (via a dedicated Agent call). Worker Agents "do". Never conflate the two.

3. **Every subtask has acceptance criteria.** No task is "done" just because the process exited successfully.

4. **Fail loudly, recover gracefully.** Log everything. Retry with improved context. Escalate to human when stuck. Never silently swallow failures.

5. **Human feedback is a first-class input.** Not an afterthought. The orchestrator should be designed to pause, receive, and incorporate feedback at any point.

6. **Context is precious, manage it actively.** Compress, summarize, and prioritize. Never blindly truncate. Never flood an Agent with irrelevant context.

7. **Plan is a living document.** Initial plan is a hypothesis. Execution reveals truth. The system must adapt.
