# Claude Code Architecture: Engineering Patterns Reference for Knight System

**Date:** 2026-04-04  
**Author:** Claude Opus 4.6  
**Purpose:** Extracted engineering patterns from Claude Code (cc-recovered-main) for other agents working on Knight System  
**Source:** `reference/cc-recovered-main/` (1884 TypeScript source files)

---

## 0. Why This Document Matters

Claude Code is a production-grade single-agent system that solves many of the same problems Knight System needs to solve at the multi-agent cluster level: task decomposition, agent orchestration, permission management, context preservation, error recovery, and human interaction. Its engineering is battle-tested across millions of sessions. This document extracts the key patterns Knight can directly adopt or adapt.

---

## 1. Architecture Overview

### 1.1 Layered Structure

```
User Input (CLI / SDK / IDE)
    ↓
┌────────────────────────────────────┐
│  Query Engine (query.ts)           │  ← The "brain loop"
│  - Sends messages to Claude API    │
│  - Receives assistant response     │
│  - Routes tool_use blocks          │
│  - Handles streaming               │
│  - Auto-compact when context full  │
└──────────────┬─────────────────────┘
               ↓
┌────────────────────────────────────┐
│  Tool Orchestration                │
│  (StreamingToolExecutor)           │
│  - Parallel tool execution         │
│  - Concurrency safety checks       │
│  - Permission gating               │
│  - Progress reporting              │
└──────────────┬─────────────────────┘
               ↓
┌────────────────────────────────────┐
│  Tool Layer (60+ tools)            │
│  - BashTool, FileReadTool, etc.    │
│  - AgentTool (sub-agent spawning)  │
│  - TaskCreate/Update/List/Stop     │
│  - AskUserQuestion (human-in-loop) │
│  - EnterPlanMode / ExitPlanMode    │
└──────────────┬─────────────────────┘
               ↓
┌────────────────────────────────────┐
│  Services Layer                    │
│  - AgentSummary (progress reports) │
│  - Compact (context compression)   │
│  - SessionMemory / extractMemories │
│  - MCP (external tool protocol)    │
│  - Analytics / Telemetry           │
└────────────────────────────────────┘
```

### 1.2 Core Insight: LLM IS the Brain

Claude Code does NOT have a separate "orchestrator brain" module. The LLM itself (Claude API) IS the brain. The system prompt instructs the LLM how to behave as an orchestrator. The engineering system provides:
1. **Tools** the LLM can call
2. **Permission gates** that control what tools can do
3. **Context management** that keeps the LLM informed
4. **Execution infrastructure** that runs tool calls reliably

**Key takeaway for Knight:** Don't build a rule-based orchestrator. Let the LLM think. Build the infrastructure around it.

---

## 2. Tool Abstraction System

### 2.1 The Tool Interface

**File:** `src/Tool.ts` (793 lines)

This is the most important abstraction in the codebase. Every capability is a Tool with a uniform interface:

```typescript
type Tool = {
  name: string
  inputSchema: ZodSchema           // Validated input
  
  // Core execution
  call(args, context, canUseTool, parentMessage, onProgress): Promise<ToolResult>
  
  // Permission system
  validateInput(input, context): Promise<ValidationResult>
  checkPermissions(input, context): Promise<PermissionResult>
  
  // Safety classification
  isReadOnly(input): boolean
  isDestructive(input): boolean
  isConcurrencySafe(input): boolean
  
  // Context for the LLM
  prompt(options): Promise<string>              // LLM-facing description
  description(input, options): Promise<string>  // Dynamic description
  
  // Rendering (for UI display)
  renderToolUseMessage(input, options): ReactNode
  renderToolResultMessage(content, progress, options): ReactNode
  
  // Result size management
  maxResultSizeChars: number
}
```

**What Knight should learn:**

Every agent adapter in Knight should implement a uniform interface like this. The current `ClaudeAdapter` and `KimiAdapter` are too thin — they lack:
- Input validation
- Permission checks
- Read-only / destructive classification
- Result size limits
- Progress reporting

### 2.2 Tool Builder Pattern with Safe Defaults

**File:** `src/Tool.ts:757-792`

```typescript
const TOOL_DEFAULTS = {
  isEnabled: () => true,
  isConcurrencySafe: () => false,      // Assume NOT safe (fail-closed)
  isReadOnly: () => false,             // Assume writes (fail-closed)
  isDestructive: () => false,
  checkPermissions: (input) =>
    Promise.resolve({ behavior: 'allow', updatedInput: input }),
  toAutoClassifierInput: () => '',
  userFacingName: () => '',
}

function buildTool(def) {
  return { ...TOOL_DEFAULTS, userFacingName: () => def.name, ...def }
}
```

**Principle: Fail-closed defaults.** A new tool that forgets to define `isConcurrencySafe` is treated as NOT safe. A tool that forgets `isReadOnly` is treated as writing. Safety is the default; capability must be explicitly declared.

### 2.3 Tool Pool Assembly with Feature Gating

**File:** `src/tools.ts`

Tools are conditionally loaded based on feature flags:

```typescript
const SleepTool = feature('PROACTIVE') ? require('./tools/SleepTool') : null
const cronTools = feature('AGENT_TRIGGERS') ? [CronCreateTool, CronDeleteTool, CronListTool] : []

function getAllBaseTools(): Tools {
  return [
    AgentTool,        // Always available
    BashTool,         // Always available
    FileReadTool,     // Always available
    ...(SleepTool ? [SleepTool] : []),       // Conditional
    ...(cronTools),                           // Conditional
  ]
}
```

Then filtered by deny rules:

```typescript
function getTools(permissionContext): Tools {
  const tools = getAllBaseTools()
  let allowed = filterToolsByDenyRules(tools, permissionContext)
  const isEnabled = allowed.map(t => t.isEnabled())
  return allowed.filter((_, i) => isEnabled[i])
}
```

**What Knight should learn:** Agent capabilities should be modular and conditionally loaded. Don't hardcode which agents exist — use a registry pattern with feature flags.

---

## 3. Sub-Agent (AgentTool) Architecture

### 3.1 Agent as a Tool

**File:** `src/tools/AgentTool/AgentTool.tsx`

The most critical pattern: **spawning a sub-agent is just another tool call**. The parent LLM calls `Agent(prompt, subagent_type)` like it would call `Bash(command)`. This means:
- The LLM decides WHEN to spawn agents (not hardcoded logic)
- The LLM writes the agent's prompt (context transfer is LLM-driven)
- The LLM synthesizes agent results (not a fixed aggregation function)

### 3.2 Agent Type System (Built-in Agents)

**Files:** `src/tools/AgentTool/built-in/*.ts`

Claude Code defines specialized agent types, each with:
- A `systemPrompt` (what the agent is and how it behaves)
- A `whenToUse` description (so the parent LLM knows when to pick it)
- `tools` allowlist or `disallowedTools` denylist
- An optional `model` override

Current built-in types:

| Agent Type | Purpose | Tool Access | Model |
|-----------|---------|-------------|-------|
| `general-purpose` | Multi-step tasks, research, code execution | All tools (`*`) | Default |
| `Explore` | Fast codebase search/navigation | Read-only tools only | Haiku (fast) |
| `Plan` | Architecture design, implementation planning | Read-only tools only | Inherit parent |
| `claude-code-guide` | Answer questions about Claude Code | Read-only + WebFetch | Inherit |
| `statusline-setup` | Configure status line settings | Read + Edit only | Inherit |

**Key design insight: Agent types are NOT about different AI models. They're about different TOOL ACCESS and SYSTEM PROMPTS.** A "Plan" agent uses the same model but can't write files. An "Explore" agent uses a cheaper model but is restricted to read-only operations.

**What Knight should learn:** Knight's agent types (Claude, Kimi) are currently defined by which CLI to call. But the real axis of differentiation should be: what tools does the agent have access to, what is its system prompt, and what model does it use? A single Claude Code install can behave as 5+ different "agent types" just by varying these parameters.

### 3.3 Agent Tool Resolution

**File:** `src/tools/AgentTool/agentToolUtils.ts:70-100`

When spawning a sub-agent, tools are filtered:

```typescript
function filterToolsForAgent({ tools, isBuiltIn, isAsync, permissionMode }) {
  return tools.filter(tool => {
    if (tool.name.startsWith('mcp__')) return true        // MCP tools always allowed
    if (ALL_AGENT_DISALLOWED_TOOLS.has(tool.name)) return false  // Hard deny list
    if (!isBuiltIn && CUSTOM_AGENT_DISALLOWED_TOOLS.has(tool.name)) return false
    if (isAsync && !ASYNC_AGENT_ALLOWED_TOOLS.has(tool.name)) return false
    return true
  })
}
```

Three layers of filtering:
1. **Global denylist** — some tools are NEVER available to sub-agents
2. **Custom agent denylist** — additional restrictions for user-defined agents
3. **Async agent allowlist** — background agents get fewer tools (no interactive UI)

### 3.4 Fork Subagent (Cache-Sharing Pattern)

**File:** `src/utils/forkedAgent.ts`

A "fork" creates a sub-agent that SHARES the parent's prompt cache. This is a performance optimization: the forked agent inherits the parent's entire conversation context without re-sending it to the API.

```typescript
type CacheSafeParams = {
  systemPrompt: SystemPrompt     // Must match parent
  userContext: object             // Must match parent
  systemContext: object           // Must match parent
  toolUseContext: ToolUseContext  // Contains tools, model, etc.
  forkContextMessages: Message[]  // Parent's conversation history
}
```

**What Knight should learn:** When Knight re-uses the same Agent for follow-up tasks, context should be preserved and shared, not rebuilt from scratch. The "fork" pattern — inheriting parent context while adding new instructions — is far more efficient than starting fresh every time.

---

## 4. Coordinator Mode (Multi-Agent Orchestration)

### 4.1 The Coordinator Pattern

**File:** `src/coordinator/coordinatorMode.ts`

This is the most directly relevant pattern for Knight. Claude Code's coordinator mode transforms a single Claude instance into a multi-agent coordinator:

**Coordinator's role (from system prompt):**
1. Help the user achieve their goal
2. Direct workers to research, implement, and verify
3. Synthesize results and communicate with the user
4. Answer questions directly when possible — don't delegate what you can handle

**Coordinator's tools:**
- `Agent` — Spawn a new worker
- `SendMessage` — Continue an existing worker (send follow-up instructions)
- `TaskStop` — Stop a running worker

### 4.2 Task Workflow Phases

The coordinator system prompt defines a four-phase workflow:

| Phase | Who | Purpose |
|-------|-----|---------|
| **Research** | Workers (parallel) | Investigate codebase, find files, understand problem |
| **Synthesis** | **Coordinator** | Read findings, understand problem, craft specs |
| **Implementation** | Workers | Make targeted changes per spec |
| **Verification** | Workers | Test changes work |

**Critical rule: "Never delegate understanding."**

```
// BAD — lazy delegation
Agent({ prompt: "Based on your findings, fix the auth bug" })

// GOOD — synthesized spec
Agent({ prompt: "Fix the null pointer in src/auth/validate.ts:42. 
  The user field is undefined when sessions expire. Add a null check 
  before user.id access. Return 401 with 'Session expired'." })
```

**What Knight should learn:** This is the exact pattern Knight's OrchestratorLoop needs. The coordinator:
1. Receives the goal
2. Spawns research workers (parallel)
3. SYNTHESIZES findings (the coordinator thinks, doesn't delegate thinking)
4. Writes specific implementation specs
5. Spawns implementation workers
6. Spawns verification workers
7. Reports results to user

### 4.3 Concurrency Management

```
Read-only tasks (research)  → Run in parallel freely
Write-heavy tasks (implementation) → One at a time per set of files  
Verification → Can sometimes run alongside implementation on different files
```

### 4.4 Worker Failure Handling

```
When a worker reports failure:
1. Continue the SAME worker with SendMessage — it has error context
2. If correction attempt fails, try a different approach
3. Or report to the user
```

This is the "trial-and-error" loop Knight needs: don't restart from scratch on failure. Continue the failed worker with corrected instructions, because it already has context about what went wrong.

### 4.5 Task Notifications

Workers report back via structured XML notifications:

```xml
<task-notification>
  <task-id>agent-a1b</task-id>
  <status>completed|failed|killed</status>
  <summary>Human-readable status summary</summary>
  <result>Agent's final text response</result>
  <usage>
    <total_tokens>N</total_tokens>
    <tool_uses>N</tool_uses>
    <duration_ms>N</duration_ms>
  </usage>
</task-notification>
```

**What Knight should learn:** Task results need structured metadata (not just raw output). Token usage, duration, and tool use count are essential for monitoring and cost control.

---

## 5. Permission & Safety System

### 5.1 Multi-Layer Permission Architecture

**File:** `src/utils/permissions/permissions.ts`

Permissions are checked in a cascade:

```
1. Tool-specific validateInput()     → Reject invalid inputs
2. Tool-specific checkPermissions()  → Tool-level permission logic
3. Permission rules (allow/deny/ask) → User-configured rules
4. YOLO Classifier (LLM-based)      → Auto-approve safe operations
5. User prompt (if needed)           → Ask the human
```

### 5.2 YOLO Classifier (Auto-Approve Safe Operations)

**File:** `src/utils/permissions/yoloClassifier.ts`

An LLM-based classifier that automatically approves operations it deems safe:

```typescript
async function classifyYoloAction(
  transcript: string,    // Recent conversation history
  toolName: string,      // Which tool
  toolInput: unknown,    // What the tool wants to do
  permissionContext      // Current permission rules
): Promise<YoloClassifierResult> {
  // Sends a side-query to a fast model (Haiku)
  // to classify the action as safe/unsafe
  // Returns: approve | deny | ask_user
}
```

**What Knight should learn:** For Knight's human-in-the-loop system, not every action needs human approval. An LLM classifier can auto-approve safe operations (read-only, within known directories) and only escalate risky ones (file deletion, network access, etc.).

### 5.3 Denial Tracking (Graceful Degradation)

**File:** `src/utils/permissions/denialTracking.ts`

If the auto-classifier keeps denying actions, the system falls back to prompting the user:

```typescript
const DENIAL_LIMITS = {
  consecutiveDenials: 3,    // After 3 consecutive denials...
  fallbackToPrompting: true  // ...ask the user instead of auto-denying
}
```

**Principle: Never silently block. If automated checks keep failing, escalate to the human.**

---

## 6. Context & Memory Management

### 6.1 File State Cache (LRU + Size-Bounded)

**File:** `src/utils/fileStateCache.ts`

```typescript
class FileStateCache {
  private cache: LRUCache<string, FileState>
  
  constructor(maxEntries: number, maxSizeBytes: number) {
    this.cache = new LRUCache({
      max: maxEntries,           // 100 entries default
      maxSize: maxSizeBytes,     // 25MB default
      sizeCalculation: value => Math.max(1, Buffer.byteLength(value.content)),
    })
  }
}
```

Uses a proper LRU library with size-based eviction. Knight's `FileStateCache` is a manual implementation — consider using an LRU library.

### 6.2 Auto-Compact (Context Window Management)

**File:** `src/services/compact/compact.ts`

When the context window gets too large, the system automatically compresses it:

1. Fork the current conversation to a side-query
2. Ask the fork to summarize what happened so far
3. Replace old messages with the summary
4. Continue with reduced context

This is critical for long-running multi-step tasks. Without it, context overflow kills the session.

**What Knight should learn:** Knight's `ContextManager` truncates at 150 characters. It should instead use LLM-powered summarization to compress context intelligently.

### 6.3 Agent Summary (Periodic Progress Reports)

**File:** `src/services/AgentSummary/agentSummary.ts`

For background agents, a periodic summarizer runs every 30 seconds:

```typescript
const SUMMARY_INTERVAL_MS = 30_000

function buildSummaryPrompt(previousSummary) {
  return `Describe your most recent action in 3-5 words using present tense.
  Good: "Reading runAgent.ts"
  Good: "Fixing null check in validate.ts"
  Bad (too vague): "Investigating the issue"`
}
```

The summarizer forks the agent's conversation and asks it to describe what it's doing — this provides real-time progress visibility without interrupting the agent's work.

### 6.4 Tool Result Budget (Content Replacement)

**File:** `src/utils/toolResultStorage.ts`

When tool results exceed `maxResultSizeChars`, they're persisted to disk and replaced with a preview + file path:

```
Original: [5000 lines of grep output]
Replaced: "Found 247 matches. Full results saved to /tmp/knight/tool-results/abc123.txt.
           First 50 lines shown below: ..."
```

**What Knight should learn:** Agent outputs can be enormous. Storing full outputs in memory kills performance. Persist large results to disk, keep summaries in context.

---

## 7. Task Management System

### 7.1 Task Framework

**File:** `src/utils/task/framework.ts`

Tasks have a lifecycle managed through AppState:

```typescript
function registerTask(task: TaskState, setAppState): void
function updateTaskState(taskId, setAppState, updater): void

// Task status types
type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'killed'
```

### 7.2 Progress Tracking

**File:** `src/tasks/LocalAgentTask/LocalAgentTask.tsx`

Each agent task tracks granular progress:

```typescript
type AgentProgress = {
  toolUseCount: number           // How many tools it has used
  tokenCount: number             // How many tokens consumed
  lastActivity?: ToolActivity    // What it's currently doing
  recentActivities?: ToolActivity[] // Last 5 actions
  summary?: string               // LLM-generated summary
}

type ToolActivity = {
  toolName: string
  input: Record<string, unknown>
  activityDescription?: string   // e.g., "Reading src/foo.ts"
  isSearch?: boolean
  isRead?: boolean
}
```

**What Knight should learn:** Task progress should be rich and structured, not just a percentage. Knight's `progress: int` (0-100) is too crude. Track what the agent is actually doing.

### 7.3 Task Output on Disk

**File:** `src/utils/task/diskOutput.ts`

Agent output is written to disk files, not held in memory. The coordinator reads the output file when the notification arrives. This allows:
- Background agents to run without holding memory
- Output to survive process restarts
- Users to inspect output directly via file system

---

## 8. Human Interaction Patterns

### 8.1 AskUserQuestion Tool

Claude Code has a dedicated tool for asking the user questions mid-execution:

```typescript
AskUserQuestionTool({
  question: "Which database should we use for the user table?",
  options: [
    { label: "PostgreSQL", description: "Relational, ACID compliant" },
    { label: "MongoDB", description: "Document store, flexible schema" }
  ]
})
```

The LLM decides WHEN to ask. The tool pauses execution and waits for the user's answer.

### 8.2 Plan Mode

**Files:** `src/tools/EnterPlanModeTool/`, `src/tools/ExitPlanModeTool/`

The LLM can enter "plan mode" where it explores and designs without executing. This is a permission-level switch:
- In plan mode: read-only tools only (no writes, no execution)
- User reviews the plan
- On approval: exit plan mode, proceed with implementation

**What Knight should learn:** Knight needs a similar gating mechanism. Before executing, the orchestrator should present the plan and wait for approval. This is the "checkpoint" concept from our architecture design.

### 8.3 SendMessage (Continue a Running Agent)

The coordinator can send follow-up instructions to a running or completed agent:

```typescript
SendMessage({ to: "agent-a1b", message: "Fix the assertion on line 58" })
```

The agent resumes with its full context preserved. This is how the coordinator:
- Corrects mistakes without restarting
- Chains multiple steps through the same agent
- Handles human feedback (user says "also fix X" → SendMessage to the worker)

---

## 9. Patterns Directly Applicable to Knight

### Pattern 1: LLM-as-Coordinator (Most Important)

Replace Knight's hardcoded `TaskPlanner` with an LLM call. The "plan" should be generated by asking Claude/Kimi to analyze the task and produce a structured decomposition. The system prompt tells the LLM how to be a good coordinator.

### Pattern 2: Tool-Based Agent Spawning

In Knight, spawning an agent should be a "tool" that the coordinator LLM calls, not a hardcoded step in the pipeline. This lets the LLM decide how many agents to spawn, what type each should be, and what prompt each gets.

### Pattern 3: Structured Task Notifications

When a worker completes, don't just return raw output. Return structured metadata:
```python
@dataclass
class TaskNotification:
    task_id: str
    status: str          # completed | failed | killed
    summary: str         # human-readable status
    result: str          # agent's output
    token_count: int
    tool_use_count: int
    duration_ms: int
```

### Pattern 4: Continue-on-Failure (SendMessage Pattern)

When a worker fails, don't restart from scratch. Send a follow-up message to the same worker with the error context. The worker already knows what it tried — give it corrective instructions.

### Pattern 5: Permission-Gated Tool Access

Different agent types get different tool sets. A "research" agent can read files but not write them. An "implementation" agent can write but not deploy. A "verification" agent runs tests but doesn't modify code.

### Pattern 6: Periodic Progress Summarization

For long-running agents, fork the conversation every 30 seconds and ask "what are you doing now?" in 3-5 words. This provides real-time visibility without interrupting the agent.

### Pattern 7: LRU-Bounded Caches with Size Limits

Every cache (file state, tool results, context) should have both entry-count AND byte-size limits. Unbounded caches kill memory. Use proper LRU libraries, not manual implementations.

### Pattern 8: Auto-Compact for Context Management

When context grows too large, use an LLM to summarize it rather than truncating. Truncation loses information randomly; summarization preserves the important parts.

### Pattern 9: Task Output on Disk

Write agent output to files, not memory. This scales better, survives restarts, and allows output inspection via the file system.

### Pattern 10: Coordinator System Prompt as the Orchestration Logic

The coordinator's behavior (when to parallelize, how to handle failures, when to verify) is defined in the system prompt, not in code. This means the orchestration strategy can be updated by changing a prompt, not by rewriting logic.

---

## 10. Key Files Quick Reference

For agents working on Knight, these are the most valuable reference files to study:

| File | Lines | What to Learn |
|------|-------|---------------|
| `src/Tool.ts` | 793 | Tool interface design, buildTool pattern |
| `src/tools.ts` | 390 | Tool pool assembly, feature gating, deny rules |
| `src/coordinator/coordinatorMode.ts` | 370 | **Full coordinator system prompt** — the orchestration logic |
| `src/tools/AgentTool/AgentTool.tsx` | ~1000 | How sub-agents are spawned, managed, and reported |
| `src/tools/AgentTool/prompt.ts` | 288 | Agent prompt engineering, when-to-use guidelines |
| `src/tools/AgentTool/runAgent.ts` | ~600 | Agent execution lifecycle, MCP integration |
| `src/tools/AgentTool/agentToolUtils.ts` | ~400 | Tool filtering, progress tracking, classifier |
| `src/tools/AgentTool/built-in/*.ts` | ~300 | Agent type definitions (general, explore, plan) |
| `src/utils/forkedAgent.ts` | ~300 | Cache-sharing fork pattern |
| `src/services/AgentSummary/agentSummary.ts` | ~120 | Periodic progress summarization |
| `src/services/compact/compact.ts` | ~400 | Auto-compact context management |
| `src/utils/permissions/permissions.ts` | ~400 | Multi-layer permission cascade |
| `src/utils/permissions/yoloClassifier.ts` | ~300 | LLM-based auto-approval classifier |
| `src/utils/fileStateCache.ts` | ~120 | Proper LRU cache with size bounds |
| `src/utils/task/framework.ts` | ~200 | Task lifecycle management |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | ~400 | Agent progress tracking |

---

## 11. Critical Design Principles Extracted

1. **The LLM is the orchestrator.** Code provides tools, guardrails, and infrastructure. The LLM makes decisions.

2. **Every capability is a Tool.** Spawning agents, asking users, entering plan mode — all Tools with uniform interfaces.

3. **Fail-closed safety.** Unknown tools default to "not concurrent safe", "not read-only", "requires permission". Safety is opt-out, not opt-in.

4. **Context is king.** Continue workers (don't restart). Compress context (don't truncate). Cache aggressively (don't re-read).

5. **Never delegate understanding.** The coordinator synthesizes findings before giving specs. It doesn't say "based on your findings, fix it."

6. **Structured over unstructured.** Task notifications use XML with typed fields. Progress is measured in tool uses and tokens, not percentages. Agent types are defined by schemas, not strings.

7. **Disk over memory for large data.** Tool results, agent transcripts, and output go to files. Memory holds summaries and pointers.

8. **Feature flags for everything.** New capabilities are gated behind flags. Dead code elimination removes disabled features at build time.

9. **Prompt engineering IS architecture.** The coordinator system prompt defines workflow phases, concurrency rules, failure handling, and prompt-writing guidelines. Changing the prompt changes the architecture.

10. **Parallelism is the coordinator's superpower.** Research tasks fan out. Independent implementation tasks run concurrently. Verification can overlap with implementation on different file sets.
