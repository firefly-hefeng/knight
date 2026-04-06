"use client";

import { useMemo, useCallback } from "react";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  Position,
  MarkerType,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "reactflow";
import "reactflow/dist/style.css";
import type { TaskDAG, SubTaskInfo, TaskStatus } from "@/types";

interface DAGVisualizerProps {
  dag: TaskDAG;
  className?: string;
}

/* ──────────────── Status → visual mapping ──────────────── */

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  pending:   { bg: "#F5E6D3", border: "#8D6E63", text: "#5D4037", glow: "" },
  running:   { bg: "#FFF3E0", border: "#E65100", text: "#BF360C", glow: "0 0 12px rgba(230,81,0,0.4)" },
  completed: { bg: "#E8F5E9", border: "#2E7D32", text: "#1B5E20", glow: "" },
  failed:    { bg: "#FFEBEE", border: "#C62828", text: "#B71C1C", glow: "" },
  skipped:   { bg: "#ECEFF1", border: "#78909C", text: "#546E7F", glow: "" },
  waiting_for_feedback: { bg: "#FFF8E1", border: "#F9A825", text: "#F57F17", glow: "0 0 12px rgba(249,168,37,0.5)" },
  evaluating:{ bg: "#E3F2FD", border: "#1565C0", text: "#0D47A1", glow: "0 0 12px rgba(21,101,192,0.3)" },
};

const STATUS_ICONS: Record<string, string> = {
  pending: "○",
  running: "◉",
  completed: "✓",
  failed: "✗",
  skipped: "⊘",
  waiting_for_feedback: "⏸",
  evaluating: "⏳",
};

/* ──────────────── DAG layout algorithm ──────────────── */

function computeLayout(dag: TaskDAG): { positions: Record<string, { x: number; y: number }>; width: number; height: number } {
  const subtasks = dag.subtasks;
  if (!subtasks.length) return { positions: {}, width: 400, height: 200 };

  // Build adjacency from edges
  const children = new Map<string, string[]>();
  const parents = new Map<string, string[]>();
  const ids = new Set(subtasks.map((s) => s.id));

  for (const st of subtasks) {
    children.set(st.id, []);
    parents.set(st.id, []);
  }

  // Use edge data AND dependency fields
  const edgeSet = new Set<string>();
  for (const [from, to] of dag.edges) {
    if (ids.has(from) && ids.has(to)) {
      const key = `${from}->${to}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        children.get(from)!.push(to);
        parents.get(to)!.push(from);
      }
    }
  }

  // Topological sort with BFS (Kahn's algorithm) → assign layers
  const inDegree = new Map<string, number>();
  for (const id of ids) inDegree.set(id, parents.get(id)!.length);

  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }

  const layers: string[][] = [];
  const layerOf = new Map<string, number>();

  while (queue.length > 0) {
    const currentLayer = [...queue];
    layers.push(currentLayer);
    const layerIdx = layers.length - 1;
    queue.length = 0;

    for (const id of currentLayer) {
      layerOf.set(id, layerIdx);
      for (const child of children.get(id) || []) {
        inDegree.set(child, inDegree.get(child)! - 1);
        if (inDegree.get(child) === 0) queue.push(child);
      }
    }
  }

  // Catch orphans (cyclic or disconnected)
  for (const id of ids) {
    if (!layerOf.has(id)) {
      const nextLayer = layers.length;
      layers.push([id]);
      layerOf.set(id, nextLayer);
    }
  }

  // Assign positions
  const nodeW = 220;
  const nodeH = 80;
  const gapX = 60;
  const gapY = 100;

  const positions: Record<string, { x: number; y: number }> = {};
  let maxX = 0;

  for (let ly = 0; ly < layers.length; ly++) {
    const layer = layers[ly];
    const totalW = layer.length * nodeW + (layer.length - 1) * gapX;
    const startX = -totalW / 2;
    for (let i = 0; i < layer.length; i++) {
      const x = startX + i * (nodeW + gapX);
      positions[layer[i]] = { x, y: ly * (nodeH + gapY) };
      maxX = Math.max(maxX, Math.abs(x) + nodeW);
    }
  }

  return {
    positions,
    width: maxX * 2 + 100,
    height: layers.length * (nodeH + gapY) + 50,
  };
}

/* ──────────────── Component ──────────────── */

export function DAGVisualizer({ dag, className }: DAGVisualizerProps) {
  const { nodes, edges } = useMemo(() => {
    const { positions } = computeLayout(dag);
    const idSet = new Set(dag.subtasks.map((s) => s.id));

    const rfNodes: Node[] = dag.subtasks.map((st) => {
      const colors = STATUS_COLORS[st.status] || STATUS_COLORS.pending;
      const icon = STATUS_ICONS[st.status] || "○";
      const pos = positions[st.id] || { x: 0, y: 0 };

      return {
        id: st.id,
        type: "default",
        position: pos,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        data: {
          label: (
            <div className="flex items-start gap-2 min-w-0">
              <span className="text-base flex-shrink-0 mt-0.5" style={{ lineHeight: 1 }}>{icon}</span>
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-xs leading-tight truncate" title={st.description}>
                  {st.description.length > 40 ? st.description.slice(0, 37) + "..." : st.description}
                </div>
                <div className="flex items-center gap-2 mt-1 text-[10px] opacity-70">
                  <span className="uppercase">{st.agentType}</span>
                  {st.attempts > 0 && <span>×{st.attempts}</span>}
                </div>
              </div>
            </div>
          ),
        },
        style: {
          background: colors.bg,
          color: colors.text,
          border: `2px solid ${colors.border}`,
          borderRadius: "10px",
          padding: "8px 12px",
          width: 220,
          fontSize: "12px",
          boxShadow: colors.glow || "0 1px 3px rgba(0,0,0,0.1)",
        },
      };
    });

    const rfEdges: Edge[] = dag.edges
      .filter(([from, to]) => idSet.has(from) && idSet.has(to))
      .map(([from, to], idx) => {
        const targetSt = dag.subtasks.find((s) => s.id === to);
        const isActive = targetSt?.status === "running";
        return {
          id: `e-${from}-${to}-${idx}`,
          source: from,
          target: to,
          animated: isActive,
          style: {
            stroke: isActive ? "#E65100" : "#8D6E63",
            strokeWidth: isActive ? 2.5 : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isActive ? "#E65100" : "#8D6E63",
            width: 16,
            height: 16,
          },
        };
      });

    return { nodes: rfNodes, edges: rfEdges };
  }, [dag]);

  const [rfNodes, , onNodesChange] = useNodesState(nodes);
  const [rfEdges, , onEdgesChange] = useEdgesState(edges);

  return (
    <div className={`w-full border border-[#5D4037]/30 rounded-xl overflow-hidden bg-[#FFFBF0] ${className || ""}`}
         style={{ height: Math.max(280, Math.min(500, dag.subtasks.length * 100 + 80)) }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        minZoom={0.3}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#D7CCC8" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

/* ──────────────── DAG summary bar ──────────────── */

export function DAGSummary({ dag }: { dag: TaskDAG }) {
  const counts = useMemo(() => {
    const c = { total: dag.subtasks.length, completed: 0, running: 0, failed: 0, pending: 0 };
    for (const st of dag.subtasks) {
      if (st.status === "completed") c.completed++;
      else if (st.status === "running") c.running++;
      else if (st.status === "failed") c.failed++;
      else c.pending++;
    }
    return c;
  }, [dag]);

  return (
    <div className="flex items-center gap-3 text-xs font-mono text-[#5D4037]">
      <span className="text-[#8D6E63] uppercase tracking-wider text-[10px]">DAG v{dag.version}</span>
      <span className="text-emerald-700">{counts.completed}✓</span>
      {counts.running > 0 && <span className="text-orange-700">{counts.running}◉</span>}
      {counts.failed > 0 && <span className="text-red-700">{counts.failed}✗</span>}
      {counts.pending > 0 && <span className="text-gray-500">{counts.pending}○</span>}
      <span className="ml-auto font-semibold">{dag.progress}%</span>
    </div>
  );
}
