# Claude Code Architecture — Engineering Patterns for Knight System

- **Date**: 2026-04-04
- **Purpose**: Extract actionable engineering patterns from Claude Code (cc-recovered-main) for Knight System's architecture evolution
- **Audience**: All agents working on Knight System development
- **Source**: `reference/cc-recovered-main/src/` (1884 TypeScript files)

---

## 1. Architecture Overview

Claude Code is a production-grade single-agent system that has evolved into a **multi-agent orchestrator**. Its architecture solves many of the same problems Knight System faces, but at massive scale (~34M+ agent spawns/week).

### Directory Structure (Key Modules)

```
src/
├── tools/AgentTool/          # Agent spawning, lifecycle, memory
│   ├── AgentTool.tsx         # Main tool definition (schema, call, render)
│   ├── runAgent.ts           # Core agent execution loop (~900 lines)
│   ├── forkSubagent.ts       # Fork-based context sharing
│   ├── resumeAgent.ts        # Agent resume after crash/restart
│   ├── agentMemory.ts        # Persistent agent memory (user/project/local)
│   ├── agentToolUtils.ts     # Lifecycle utilities (notify, progress, finalize)
│   └── built-in/
│       ├── generalPurposeAgent.ts
│       ├── exploreAgent.ts       # Read-only codebase exploration
│       ├── planAgent.ts          # Read-only architecture planning
│       └── verificationAgent.ts  # Independent verification specialist
│
├── tasks/                    # Task state management
│   ├── types.ts              # Union of all task state types
│   ├── stopTask.ts           # Safe task termination
│   ├── LocalMainSessionTask.ts    # Background session management
│   ├── LocalAgentTask/       # Local agent task lifecycle
│   ├── LocalShellTask/       # Shell command task management
│   ├── RemoteAgentTask/      # Remote agent task management
│   └── InProcessTeammateTask/    # In-process teammate lifecycle
│
├── coordinator/              # Coordinator mode (orchestration)
│   └── coordinatorMode.ts    # Multi-worker delegation system
│
├── services/
│   ├── compact/              # Context window management
│   │   ├── compact.ts        # Conversation compaction engine
│   │   ├── autoCompact.ts    # Automatic compaction triggers
│   │   └── sessionMemoryCompact.ts
│   └── SessionMemory/        # Session-scoped memory
│       ├── sessionMemory.ts  # Auto-maintained session notes
│       └── prompts.ts        # Memory extraction prompts
│
├── utils/swarm/              # Multi-agent cluster management
│   ├── backends/types.ts     # Backend abstraction (tmux/iTerm2/in-process)
│   ├── spawnUtils.ts         # Teammate spawning utilities
│   ├── permissionSync.ts     # Cross-agent permission synchronization
│   ├── reconnection.ts       # Reconnection logic
│   └── teammateLayoutManager.ts   # Visual layout for agent panes
│
└── state/                    # Application state management
```

---

## 2. Core Pattern: Agent as Tool

**CC Design**: An agent is defined as a Tool (`AgentTool`), not a separate service. The LLM itself decides when to spawn agents by calling the `Agent` tool.

**How it works**:
```
User Input → LLM (main loop) → decides to call Agent tool
  → Agent tool spawns a child agent (new LLM call with scoped context)
  → Child runs with its own tools, system prompt, permissions
  → Child result returns to parent as tool_result
```

**Key code** (`AgentTool.tsx`):
- Input schema includes: `prompt`, `description`, `subagent_type`, `model`, `run_in_background`, `isolation`
- Output schema is a discriminated union: `completed | async_launched | teammate_spawned | remote_launched`

**What Knight should learn**:
- The Orchestrator itself should be LLM-powered, not hardcoded logic
- Agent spawning should be a tool the LLM can call, not a fixed pipeline
- Multiple agent types with different capabilities (explore, plan, verify, general-purpose)

---

## 3. Core Pattern: Typed Task State Machine

**CC Design**: Every background operation is a typed task with explicit state transitions.

**Task types** (`tasks/types.ts`):
```typescript
type TaskState =
  | LocalShellTaskState    // Shell commands (bash)
  | LocalAgentTaskState    // Local sub-agents
  | RemoteAgentTaskState   // Remote CCR agents
  | InProcessTeammateTaskState  // In-process teammates
  | LocalWorkflowTaskState      // Workflows
  | MonitorMcpTaskState         // MCP monitoring
  | DreamTaskState              // Background dreaming
```

**Task lifecycle** (`stopTask.ts`):
```typescript
// 1. Look up task by ID
// 2. Validate status is 'running'
// 3. Get typed implementation via getTaskByType()
// 4. Call taskImpl.kill() — type-specific cleanup
// 5. Update state atomically (check-and-set to prevent duplicates)
// 6. Emit SDK event for external consumers
```

**Atomic state updates** — always check-and-set to prevent race conditions:
```typescript
// Anti-pattern (Knight does this):
if (task.status == 'pending'):
    start_task()  # Race condition!

// CC pattern — atomic check-and-set:
setAppState(prev => {
  const task = prev.tasks[taskId]
  if (!task || task.notified) return prev  // Already handled
  return { ...prev, tasks: { ...prev.tasks, [taskId]: { ...task, notified: true } } }
})
```

**What Knight should learn**:
- Use discriminated union types for task states (not a generic `TaskState` for everything)
- State updates must be atomic (check-then-act is a race condition)
- Every task type has its own `kill()` implementation for proper cleanup
- Task completion should emit structured notifications, not just status changes

---

## 4. Core Pattern: Specialized Built-in Agents

CC defines specialized agent roles with carefully scoped capabilities:

### 4.1 Explore Agent
- **Purpose**: Read-only codebase exploration
- **Tools**: Glob, Grep, Read, Bash (read-only)
- **Disallowed**: Agent (no nesting), Edit, Write
- **Optimization**: Omits CLAUDE.md and gitStatus from context to save tokens

### 4.2 Plan Agent
- **Purpose**: Architecture design and implementation planning
- **Tools**: Same as Explore (read-only)
- **System prompt**: Explicit `=== CRITICAL: READ-ONLY MODE ===`
- **Output format**: Structured plan with "Critical Files for Implementation" section

### 4.3 Verification Agent
- **Purpose**: Independent quality verification (tries to BREAK the implementation)
- **System prompt**: 153 lines of adversarial verification instructions
- **Key philosophy**: "Your job is not to confirm the implementation works — it's to try to break it"
- **Output format**: Structured `VERDICT: PASS | FAIL | PARTIAL` with evidence
- **Anti-rationalization prompts**: Explicitly lists common excuses the agent might use to skip checks
- **Disallowed**: Edit, Write (cannot modify project files — only verify)

### 4.4 Fork Agent
- **Purpose**: Context-sharing agent that inherits parent's full conversation
- **Design**: Produces byte-identical API request prefixes for prompt cache sharing
- **Output format**: Structured report (Scope, Result, Key files, Files changed, Issues)
- **Anti-recursion**: Guards against fork children spawning more forks

**What Knight should learn**:
- Each agent type needs a detailed, carefully engineered system prompt
- Restrict tools per agent role (don't give write tools to verification agents)
- The verification agent pattern is exactly Knight's missing "Evaluator"
- Fork agents enable parallel exploration of the same context
- Anti-recursion guards prevent agent spawning spirals

---

## 5. Core Pattern: Context Window Management (Compact)

CC's most sophisticated subsystem. Context management is treated as a first-class engineering problem.

### 5.1 Auto-Compaction (`autoCompact.ts`)
- Monitors token usage against configurable thresholds
- Triggers compaction when tokens exceed `contextWindow - 13K buffer`
- **Circuit breaker**: Stops retrying after 3 consecutive failures
- **Recursion guard**: Compact agents and session memory agents are excluded from auto-compaction
- Different strategies: session memory compaction (lighter) vs full conversation compaction (heavier)

### 5.2 Session Memory (`sessionMemory.ts`)
- Runs periodically in the background using a forked subagent
- Extracts key information from the conversation without interrupting the main flow
- Maintains a markdown file with structured notes about the current session
- Has initialization threshold (minimum activity before first extraction)
- Has update threshold (minimum activity between updates)
- Uses sequential execution to prevent concurrent memory updates

### 5.3 Agent Memory (`agentMemory.ts`)
- Persistent memory across sessions, scoped to agent type
- Three scopes: `user` (global), `project` (git-tracked), `local` (machine-specific)
- Stored as `MEMORY.md` files in dedicated directories
- Loaded into system prompt at agent spawn time
- Fire-and-forget directory creation (mkdir runs async, doesn't block agent startup)

**What Knight should learn**:
- Context management needs multiple strategies at different granularities
- Circuit breakers prevent infinite retry loops
- Session memory should run as a background process, not in the critical path
- Agent memory should persist across sessions and be scoped appropriately
- Token counting must be explicit and monitored against known thresholds

---

## 6. Core Pattern: Coordinator Mode (Multi-Agent Orchestration)

This is the most directly relevant pattern for Knight's Orchestrator.

### 6.1 Architecture (`coordinatorMode.ts`)

The coordinator is a special mode where the LLM becomes an orchestrator:
- **Tools available to coordinator**: Agent (spawn workers), SendMessage (continue workers), TaskStop (stop workers)
- **Tools available to workers**: Bash, Read, Edit, Write, etc.
- **Communication**: Workers report back via structured `<task-notification>` XML

### 6.2 Coordinator System Prompt (500+ lines)

The coordinator prompt defines a complete orchestration framework:

**Role definition**:
> "You are a coordinator. Your job is to: Help the user achieve their goal, Direct workers to research/implement/verify, Synthesize results, Answer questions directly when possible"

**Task workflow phases**:
| Phase | Who | Purpose |
|-------|-----|---------|
| Research | Workers (parallel) | Investigate codebase, find files |
| Synthesis | **Coordinator** | Read findings, craft implementation specs |
| Implementation | Workers | Make targeted changes per spec, commit |
| Verification | Workers | Test changes work |

**Concurrency rules**:
- Read-only tasks → run in parallel freely
- Write-heavy tasks → one at a time per file set
- Verification → can sometimes run alongside implementation on different files

**Worker prompt engineering** (critical insight):
> "Never write 'based on your findings' or 'based on the research.' These phrases delegate understanding to the worker instead of doing it yourself."

The coordinator must **synthesize** research results into specific, self-contained implementation specs with:
- File paths and line numbers
- Exact changes needed
- Definition of "done"
- Purpose statement (why this task exists)

**Continue vs. Spawn decision matrix**:
| Situation | Action | Reason |
|-----------|--------|--------|
| Research explored exact files to edit | Continue | Worker has context |
| Research was broad, implementation narrow | Spawn fresh | Avoid context noise |
| Correcting a failure | Continue | Worker has error context |
| Verifying another worker's code | Spawn fresh | Fresh eyes, no assumptions |
| Wrong approach entirely | Spawn fresh | Avoid anchoring on failed path |

**Failure handling**:
- Continue the same worker via SendMessage (it has error context)
- If correction fails, try different approach
- Workers can be stopped mid-flight and redirected

**What Knight should learn**:
- The Orchestrator prompt is the single most important design artifact
- Synthesis (understanding and re-expressing worker findings) is the coordinator's core job
- Worker prompts must be self-contained (workers can't see the coordinator's conversation)
- The continue-vs-spawn decision should be context-overlap-aware
- Explicit rules about concurrency prevent file conflicts

---

## 7. Core Pattern: Swarm Backend Abstraction

CC abstracts the execution environment for multi-agent spawning:

### Backend Types (`backends/types.ts`)
```typescript
type BackendType = 'tmux' | 'iterm2' | 'in-process'
```

### PaneBackend Interface (Terminal-based)
- `isAvailable()` — Check if backend exists on system
- `isRunningInside()` — Check if we're in this backend's environment
- `createTeammatePaneInSwarmView()` — Create visual pane for a teammate
- `sendCommandToPane()` — Send command to specific pane
- `killPane()` / `hidePane()` / `showPane()` — Lifecycle management
- `rebalancePanes()` — Layout management

### TeammateExecutor Interface (Lifecycle)
- `spawn(config)` — Spawn a new teammate
- `sendMessage(agentId, message)` — Send message to teammate
- `terminate(agentId)` — Graceful shutdown
- `kill(agentId)` — Force kill
- `isActive(agentId)` — Health check

### TeammateSpawnConfig
```typescript
type TeammateSpawnConfig = {
  name: string
  teamName: string
  prompt: string
  cwd: string
  model?: string
  systemPrompt?: string
  systemPromptMode?: 'default' | 'replace' | 'append'
  worktreePath?: string
  parentSessionId: string
  permissions?: string[]
  allowPermissionPrompts?: boolean
}
```

**What Knight should learn**:
- Abstract the execution backend (CLI subprocess, in-process, remote)
- Each teammate needs explicit permissions and working directory
- Health checking (`isActive()`) is a first-class concern
- The backend detects its own availability (no hardcoding)
- Environment variables must be explicitly forwarded to spawned agents

---

## 8. Core Pattern: Agent Lifecycle Management

### 8.1 Spawning (`runAgent.ts` — 900+ lines)

Agent startup is a multi-phase process:
1. Resolve agent model (considering parent, agent definition, override)
2. Create isolated file state cache (clone or fresh)
3. Resolve user context and system context (with smart omissions)
4. Determine permission mode (inheritance with overrides)
5. Execute SubagentStart hooks
6. Initialize agent-specific MCP servers
7. Record initial transcript (fire-and-forget)
8. Enter query loop (streaming messages)
9. Cleanup on exit (MCP servers, hooks, cache, todos, shell tasks, perfetto)

### 8.2 Cleanup (Critical)

The `finally` block in `runAgent.ts` performs 10+ cleanup operations:
```typescript
finally {
  await mcpCleanup()                    // Clean up agent-specific MCP servers
  clearSessionHooks(agentId)            // Clean up agent's session hooks
  cleanupAgentTracking(agentId)         // Clean up prompt cache tracking
  agentToolUseContext.readFileState.clear()  // Release file state cache memory
  initialMessages.length = 0            // Release fork context messages
  unregisterPerfettoAgent(agentId)      // Release perfetto registry entry
  clearAgentTranscriptSubdir(agentId)   // Release transcript subdir mapping
  // Release this agent's todos entry (prevents memory leak in long sessions)
  rootSetAppState(prev => {
    if (!(agentId in prev.todos)) return prev
    const { [agentId]: _removed, ...todos } = prev.todos
    return { ...prev, todos }
  })
  killShellTasksForAgent(agentId)       // Kill background bash tasks this agent spawned
}
```

### 8.3 Resume (`resumeAgent.ts`)

Agents can be resumed after crash or session restart:
1. Read agent transcript from disk
2. Read agent metadata (agentType, worktreePath, description)
3. Filter orphaned thinking-only messages
4. Filter unresolved tool uses
5. Reconstruct content replacement state
6. Re-register as async agent
7. Resume the query loop

**What Knight should learn**:
- Agent startup is a complex multi-phase process — each phase can fail and needs cleanup
- The `finally` block is as important as the main logic — every resource must be released
- Resume capability requires persistent transcripts and metadata
- Cleanup prevents memory leaks in long-running sessions (todo entries, file caches, shell tasks)
- Fire-and-forget patterns (transcript writes) prevent I/O from blocking the agent loop

---

## 9. Core Pattern: Notification & Progress System

### Task Notification Format
```xml
<task-notification>
  <task-id>{agentId}</task-id>
  <tool-use-id>{toolUseId}</tool-use-id>
  <output-file>{outputPath}</output-file>
  <status>completed|failed|killed</status>
  <summary>{human-readable status summary}</summary>
</task-notification>
```

### Progress Tracking
- `tokenCount` — cumulative tokens consumed
- `toolUseCount` — number of tool calls made
- `recentActivities` — last 5 tool activities (tool name + input)
- Updated atomically via `setAppState` on every message
- Deduplication: skip update if counts unchanged

### Foreground/Background Model
- Tasks can be backgrounded (`isBackgrounded: true`)
- Background tasks send XML notifications on completion
- Foreground tasks show output directly in the UI
- Tasks can be foregrounded mid-flight (`foregroundMainSessionTask`)
- Duplicate notification prevention via atomic `notified` flag

**What Knight should learn**:
- Use structured XML/JSON notifications (not just status field changes)
- Track progress with concrete metrics (tokens, tool calls) not percentages
- Background/foreground is a runtime toggle, not a fixed property
- Prevent duplicate notifications with atomic check-and-set

---

## 10. Direct Mapping to Knight System

| CC Pattern | Knight Equivalent (Phase 1-3) | Priority |
|------------|-------------------------------|----------|
| AgentTool as LLM-callable tool | Orchestrator uses LLM to decide spawning | Phase 2 |
| Typed task state union | Extend TaskState with discriminated types | Phase 1 |
| Atomic state updates | Replace race-prone status checks | Phase 1 |
| Explore/Plan/Verify agents | Create specialized agent definitions | Phase 2 |
| Verification agent | Evaluator component | Phase 2 |
| Coordinator mode | Orchestrator loop | Phase 2 |
| Coordinator prompt | Orchestrator system prompt | Phase 2 |
| Auto-compact | Context management for long workflows | Phase 3 |
| Session memory | Workflow memory persistence | Phase 3 |
| Agent memory | Cross-session agent learning | Phase 3 |
| Swarm backend abstraction | AgentPool backend interface | Phase 1 |
| TeammateExecutor interface | Adapter interface standardization | Phase 1 |
| Agent cleanup (finally block) | Resource cleanup on task completion | Phase 1 |
| Resume from transcript | Crash recovery from SQLite | Phase 3 |
| Notification system | Task completion events | Phase 2 |
| Fork for context sharing | Parallel agent context inheritance | Phase 3 |
| Circuit breaker on failures | ErrorHandler retry limits | Phase 2 |
| Continue vs Spawn decision | Smart agent reuse strategy | Phase 3 |

---

## 11. Key Engineering Principles

### 11.1 "The Coordinator Synthesizes, Workers Execute"
The coordinator's most important job is **understanding** worker results and crafting precise follow-up instructions. It never delegates understanding.

### 11.2 "Verification Tries to Break, Not Confirm"
The verification agent has detailed anti-rationalization prompts that fight the natural tendency to rubber-stamp work.

### 11.3 "Every Resource Gets Cleaned Up"
The `finally` block in `runAgent.ts` has 10+ cleanup operations. Every spawned resource (MCP servers, hooks, caches, shell tasks, todos) is tracked and released.

### 11.4 "State Updates Are Atomic"
Every state mutation uses check-and-set patterns. No read-modify-write without the set being conditional on the read.

### 11.5 "Fire and Forget for Non-Critical I/O"
Transcript writes, metadata saves, and directory creation use `void promise.catch()` to prevent I/O from blocking the agent loop.

### 11.6 "Circuit Breakers Prevent Infinite Loops"
Auto-compaction stops after 3 consecutive failures. This prevents sessions where context is irrecoverably large from wasting API calls.

### 11.7 "Prompt Engineering IS Architecture"
The coordinator system prompt (500+ lines) is the most carefully engineered artifact. It defines task phases, concurrency rules, prompt writing guidelines, continue-vs-spawn decisions, failure handling, and output formats.

---

*End of Reference Architecture Analysis*
