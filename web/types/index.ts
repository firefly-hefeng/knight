export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'waiting_for_feedback' | 'evaluating';
export type AgentStatus = 'idle' | 'busy' | 'offline';

export interface EvaluationResult {
  passed: boolean;
  score: number;
  criteriaResults: Record<string, boolean>;
  failureReasons: string[];
  recommendedAction: string;
}

export interface SubTaskInfo {
  id: string;
  description: string;
  agentType: string;
  status: TaskStatus;
  acceptanceCriteria: string[];
  isCheckpoint: boolean;
  attempts: number;
  result?: string;
  evaluation?: EvaluationResult;
}

export interface TaskDAG {
  id: string;
  goal?: string;
  subtasks: SubTaskInfo[];
  edges: [string, string][];
  checkpoints: string[];
  version: number;
  progress: number;
}

export interface FeedbackRequest {
  taskId: string;
  checkpointType: string;
  question: string;
  context: string;
  options: string[];
}

export interface Task {
  id: string;
  name: string;
  description?: string;
  status: TaskStatus;
  agentId?: string;
  agentName?: string;
  createdAt: string;
  updatedAt?: string;
  progress?: number;
  result?: string;
  error?: string;
  logs?: string[];
  steps?: WorkflowStep[];
  dag?: TaskDAG;
  feedbackRequest?: FeedbackRequest;
  orchestrationStats?: {
    totalAgentCalls: number;
    totalCostUsd: number;
    totalDurationMs: number;
  };
}

export interface Agent {
  id: string;
  name: string;
  status: AgentStatus;
  currentTask?: string;
  capabilities: string[];
  description?: string;
  completedTasks?: number;
}

export interface WorkflowStep {
  id: string;
  name: string;
  status: TaskStatus;
  agent?: string;
}
