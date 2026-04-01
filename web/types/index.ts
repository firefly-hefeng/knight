export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';
export type AgentStatus = 'idle' | 'busy' | 'offline';

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
  logs?: string[];
  steps?: WorkflowStep[];
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
