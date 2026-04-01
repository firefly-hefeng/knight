"use client";

import { useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface WorkflowVisualizerProps {
  tasks: Array<{
    id: string;
    name: string;
    status: string;
    agentId?: string;
  }>;
}

const statusColors = {
  pending: '#6b7280',
  running: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
};

export function WorkflowVisualizer({ tasks }: WorkflowVisualizerProps) {
  const initialNodes: Node[] = tasks.map((task, idx) => ({
    id: task.id,
    type: 'default',
    position: { x: 250, y: idx * 100 },
    data: {
      label: (
        <div className="text-sm">
          <div className="font-medium">{task.name}</div>
          <div className="text-xs text-gray-500">{task.agentId}</div>
        </div>
      )
    },
    style: {
      background: statusColors[task.status as keyof typeof statusColors] || '#6b7280',
      color: 'white',
      border: '1px solid #222',
      borderRadius: '8px',
      padding: '10px',
    },
  }));

  const initialEdges: Edge[] = tasks.slice(0, -1).map((task, idx) => ({
    id: `e${task.id}-${tasks[idx + 1].id}`,
    source: task.id,
    target: tasks[idx + 1].id,
    animated: tasks[idx + 1].status === 'running',
  }));

  const [nodes] = useNodesState(initialNodes);
  const [edges] = useEdgesState(initialEdges);

  return (
    <div className="h-96 w-full border rounded-lg overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
