"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { Task } from "@/types";
import { getTasks, getTask, getFeedbackRequest } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ─────────────── SSE hook for real-time task updates ─────────────── */

interface UseTaskSSEOptions {
  /** Task ID to stream updates for. If undefined, falls back to polling all tasks. */
  taskId?: string;
  /** Called when a new chunk arrives */
  onChunk?: (chunk: SSEChunk) => void;
  /** Enable/disable the connection */
  enabled?: boolean;
}

interface SSEChunk {
  type: string;
  content: string;
  task_id?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Hook for SSE-based task streaming.
 *
 * Uses the gateway SSE endpoint when streaming a specific task,
 * falls back to polling for task list updates (SSE not available for list).
 */
export function useTaskStream({ taskId, onChunk, enabled = true }: UseTaskSSEOptions) {
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled || !taskId) return;

    const url = `${API_BASE}/api/v1/tasks/${taskId}/stream`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (event) => {
      if (event.data === "[DONE]") {
        es.close();
        setConnected(false);
        return;
      }
      try {
        const chunk: SSEChunk = JSON.parse(event.data);
        onChunk?.(chunk);
      } catch {
        // Non-JSON data, ignore
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [taskId, enabled]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setConnected(false);
  }, []);

  return { connected, disconnect };
}

/* ─────────────── Polling hook with smart interval ─────────────── */

interface UseTaskPollingOptions {
  /** Polling interval in ms when tasks are active */
  activeInterval?: number;
  /** Polling interval in ms when all tasks are idle */
  idleInterval?: number;
  /** Enable/disable polling */
  enabled?: boolean;
}

/**
 * Smart polling hook — polls faster when tasks are active (running/evaluating),
 * slower when all tasks are idle (completed/failed/pending).
 */
export function useTaskPolling({
  activeInterval = 2000,
  idleInterval = 8000,
  enabled = true,
}: UseTaskPollingOptions = {}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);
  const hasActiveRef = useRef(false);

  const loadTasks = useCallback(async () => {
    try {
      const data = await getTasks();
      setTasks(data);
      setError(null);

      // Check if any tasks are active
      hasActiveRef.current = data.some(
        (t: Task) => t.status === "running" || t.status === "evaluating" || t.status === "waiting_for_feedback"
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    loadTasks();

    // Adaptive interval: fast when active, slow when idle
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      const interval = hasActiveRef.current ? activeInterval : idleInterval;
      timer = setTimeout(async () => {
        await loadTasks();
        tick();
      }, interval);
    };
    tick();

    return () => clearTimeout(timer);
  }, [enabled, activeInterval, idleInterval, loadTasks]);

  return { tasks, error, refresh: loadTasks };
}

/* ─────────────── Single task detail hook ─────────────── */

interface UseTaskDetailOptions {
  taskId: string | null;
  pollInterval?: number;
  enabled?: boolean;
}

/**
 * Hook for polling a single task's detail + feedback request.
 */
export function useTaskDetail({ taskId, pollInterval = 2000, enabled = true }: UseTaskDetailOptions) {
  const [task, setTask] = useState<Task | null>(null);
  const [feedbackPending, setFeedbackPending] = useState<boolean>(false);
  const [feedbackData, setFeedbackData] = useState<unknown>(null);

  const load = useCallback(async () => {
    if (!taskId) return;
    try {
      const data = await getTask(taskId);
      setTask(data);

      // Check for pending feedback
      if (data.status === "waiting_for_feedback") {
        const fbData = await getFeedbackRequest(taskId);
        if (fbData?.pending) {
          setFeedbackPending(true);
          setFeedbackData(fbData);
        } else {
          setFeedbackPending(false);
          setFeedbackData(null);
        }
      } else {
        setFeedbackPending(false);
        setFeedbackData(null);
      }
    } catch {
      // Ignore — task may have been deleted
    }
  }, [taskId]);

  useEffect(() => {
    if (!enabled || !taskId) return;
    load();

    const active = task?.status === "running" || task?.status === "evaluating" || task?.status === "waiting_for_feedback";
    const interval = active ? pollInterval : pollInterval * 4;

    const timer = setInterval(load, interval);
    return () => clearInterval(timer);
  }, [taskId, enabled, pollInterval, load]);

  return { task, feedbackPending, feedbackData, refresh: load };
}
