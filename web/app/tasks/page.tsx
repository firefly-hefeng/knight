"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus, Search, LayoutGrid, List, GitBranch, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge, Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Navigation } from "@/components/Navigation";
import { DAGVisualizer, DAGSummary } from "@/components/WorkflowVisualizer";
import { FeedbackBanner } from "@/components/FeedbackDialog";
import { createTask, getTasks, getTask, getFeedbackRequest } from "@/lib/api";
import { useTaskPolling, useTaskDetail } from "@/lib/hooks";
import type { Task, TaskStatus, TaskDAG, FeedbackRequest } from "@/types";

/* ─────────── Task Detail Dialog (separate component for type safety) ─────────── */

function TaskDetailDialog({
  task,
  open,
  onOpenChange,
  feedbackPending,
  feedbackData,
  onFeedbackSubmitted,
}: {
  task: Task;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  feedbackPending: boolean;
  feedbackData: FeedbackRequest | null;
  onFeedbackSubmitted: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-[#2C1810] uppercase tracking-wide">Task Details</DialogTitle>
        </DialogHeader>
        <div className="space-y-5">
          <div>
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-serif text-lg font-semibold text-[#2C1810]">{task.name}</h3>
              <StatusBadge status={task.status} />
            </div>
            <p className="text-sm text-[#8D6E63]">{task.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="border border-[#5D4037]/30 rounded-xl p-3 bg-[#F5E6D3]/30">
              <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-1">Assigned Agent</div>
              <div className="font-serif text-[#2C1810]">{task.agentName || "N/A"}</div>
            </div>
            <div className="border border-[#5D4037]/30 rounded-xl p-3 bg-[#F5E6D3]/30">
              <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-1">Created</div>
              <div className="font-mono text-sm text-[#2C1810]">
                {new Date(task.createdAt).toLocaleString("en-US")}
              </div>
            </div>
          </div>

          <div className="border border-[#5D4037]/30 rounded-xl p-4 bg-[#F5E6D3]/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[#5D4037] uppercase tracking-wider">Execution Progress</span>
              <span className="font-mono text-[#2C1810]">{task.progress || 0}%</span>
            </div>
            <div className="h-2 bg-[#FDF6E3] border border-[#5D4037]/20 rounded-lg overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  task.status === "completed" ? "bg-emerald-600" :
                  task.status === "failed" ? "bg-red-600" : "bg-[#D4853B]"
                }`}
                style={{ width: `${task.progress || 0}%` }}
              />
            </div>
          </div>

          {feedbackPending && feedbackData && (
            <FeedbackBanner
              taskId={task.id}
              feedbackRequest={feedbackData}
              onSubmitted={onFeedbackSubmitted}
            />
          )}

          {task.dag && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-[#D4853B]" />
                  <span className="text-xs text-[#8D6E63] uppercase tracking-wider font-semibold">Execution Plan</span>
                </div>
                <DAGSummary dag={task.dag} />
              </div>
              <DAGVisualizer dag={task.dag} />
            </div>
          )}

          {task.result && (
            <div className="border border-[#5D4037]/30 rounded-xl p-4 bg-[#F5E6D3]/30">
              <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-2">Result</div>
              <div className="text-sm text-[#2C1810] font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                {task.result}
              </div>
            </div>
          )}

          {task.error && (
            <div className="border border-red-300 rounded-xl p-4 bg-red-50">
              <div className="text-xs text-red-700 uppercase tracking-wider mb-2">Error</div>
              <div className="text-sm text-red-900 font-mono whitespace-pre-wrap">{task.error}</div>
            </div>
          )}

          {task.logs && task.logs.length > 0 && (
            <div className="border border-[#5D4037]/30 rounded-xl p-4 bg-[#F5E6D3]/30">
              <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-2">
                Execution Logs ({task.logs.length})
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto font-mono text-xs text-[#5D4037]">
                {task.logs.map((log: string, i: number) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-[#8D6E63] flex-shrink-0 select-none">{i + 1}.</span>
                    <span className="whitespace-pre-wrap">{log}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ─────────── Main Page ─────────── */

export default function TasksPage() {
  const { tasks, refresh: refreshTasks } = useTaskPolling({
    activeInterval: 2000,
    idleInterval: 8000,
  });
  const [open, setOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [newTask, setNewTask] = useState({ name: "", description: "" });
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Detail view with smart polling
  const { task: selectedTask, feedbackPending, feedbackData, refresh: refreshDetail } = useTaskDetail({
    taskId: selectedTaskId,
    enabled: isDetailOpen,
  });

  const handleCreate = async () => {
    if (!newTask.name) return;
    setLoading(true);
    try {
      await createTask(newTask.name, newTask.description);
      await refreshTasks();
      setNewTask({ name: "", description: "" });
      setOpen(false);
    } catch (error) {
      console.error("Failed to create task:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || task.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: tasks.length,
    pending: tasks.filter((t) => t.status === "pending").length,
    running: tasks.filter((t) => t.status === "running" || t.status === "evaluating").length,
    completed: tasks.filter((t) => t.status === "completed").length,
    failed: tasks.filter((t) => t.status === "failed").length,
    feedback: tasks.filter((t) => t.status === "waiting_for_feedback").length,
  };

  return (
    <div className="min-h-screen bg-[#FDF6E3] parchment-texture">
      <Navigation />
      <div className="bg-white border-b border-[#5D4037]/20 sticky top-16 z-30 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="font-serif text-2xl text-[#2C1810] uppercase tracking-wide">Task Board</h1>
              <p className="text-sm text-[#8D6E63] mt-1">Manage and monitor your task executions</p>
            </div>
            <Button onClick={() => setOpen(true)} className="gap-2 bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3]">
              <Plus className="w-4 h-4" />
              Create Task
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 mt-6">
            {[
              { label: "All", value: stats.total, status: "all" },
              { label: "Pending", value: stats.pending, status: "pending" },
              { label: "Running", value: stats.running, status: "running" },
              { label: "Completed", value: stats.completed, status: "completed" },
              { label: "Failed", value: stats.failed, status: "failed" },
              { label: "Feedback", value: stats.feedback, status: "waiting_for_feedback" },
            ].map((stat) => (
              <button
                key={stat.label}
                onClick={() => setStatusFilter(stat.status as TaskStatus | "all")}
                className={`flex flex-col items-center p-3 rounded-xl border-2 transition-all ${
                  statusFilter === stat.status
                    ? "border-[#D4853B] bg-[#D4853B]/10"
                    : "border-[#5D4037]/20 bg-[#F5E6D3]/50 hover:border-[#5D4037]/40"
                }`}
              >
                <span className="text-2xl font-serif text-[#2C1810]">{stat.value}</span>
                <span className="text-xs text-[#8D6E63] uppercase tracking-wider">{stat.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#8D6E63]" />
            <Input
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-white border-[#5D4037]/30"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded-lg border transition-colors ${
                viewMode === "grid"
                  ? "border-[#D4853B] bg-[#D4853B]/10 text-[#D4853B]"
                  : "border-[#5D4037]/30 text-[#8D6E63] hover:border-[#5D4037]/50"
              }`}
            >
              <LayoutGrid className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded-lg border transition-colors ${
                viewMode === "list"
                  ? "border-[#D4853B] bg-[#D4853B]/10 text-[#D4853B]"
                  : "border-[#5D4037]/30 text-[#8D6E63] hover:border-[#5D4037]/50"
              }`}
            >
              <List className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        {filteredTasks.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-xl border-2 border-[#5D4037]/30 bg-[#F5E6D3]/50 flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-[#8D6E63]" />
            </div>
            <h3 className="font-serif text-lg text-[#2C1810] mb-1">No tasks found</h3>
            <p className="text-sm text-[#8D6E63]">Try adjusting your search or create a new task</p>
          </div>
        ) : (
          <div className={`grid gap-5 ${viewMode === "grid" ? "sm:grid-cols-2 lg:grid-cols-3" : "grid-cols-1"}`}>
            {filteredTasks.map((task) => (
              <Card
                key={task.id}
                className="group cursor-pointer"
                onClick={() => {
                  setSelectedTaskId(task.id);
                  setIsDetailOpen(true);
                }}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-serif text-lg font-semibold text-[#2C1810] uppercase tracking-wide truncate group-hover:text-[#D4853B] transition-colors">
                        {task.name}
                      </h3>
                      <p className="text-sm text-[#8D6E63] mt-1 line-clamp-1">{task.description}</p>
                    </div>
                    <StatusBadge status={task.status} className="ml-3 flex-shrink-0" />
                  </div>

                  <div className="flex items-center gap-4 text-xs text-[#8D6E63] mb-4 font-mono">
                    <span>ID: {task.id}</span>
                    {task.agentName && <span>Agent: {task.agentName}</span>}
                    {task.dag && (
                      <span className="flex items-center gap-1 text-[#D4853B]">
                        <GitBranch className="w-3 h-3" />
                        DAG
                      </span>
                    )}
                    {task.status === "waiting_for_feedback" && (
                      <span className="flex items-center gap-1 text-amber-600 animate-pulse">
                        <MessageSquare className="w-3 h-3" />
                        Feedback
                      </span>
                    )}
                    <span>{new Date(task.createdAt).toLocaleDateString("en-US")}</span>
                  </div>

                  <div className="border border-[#5D4037]/30 rounded-xl p-4 bg-[#F5E6D3]/30">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-medium text-[#5D4037] uppercase tracking-wider">Progress</span>
                      <span className="text-sm font-mono text-[#2C1810]">{task.progress || 0}%</span>
                    </div>
                    <div className="h-2 bg-[#F5E6D3] border border-[#5D4037]/20 rounded-lg overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${
                          task.status === "completed"
                            ? "bg-emerald-600"
                            : task.status === "failed"
                            ? "bg-red-600"
                            : task.status === "waiting_for_feedback"
                            ? "bg-amber-500"
                            : "bg-[#D4853B]"
                        }`}
                        style={{ width: `${task.progress || 0}%` }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create task dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-serif text-xl text-[#2C1810] uppercase tracking-wide">Create New Task</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Input
              placeholder="Task name"
              value={newTask.name}
              onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
              className="bg-white border-[#5D4037]/30"
            />
            <Textarea
              placeholder="Description"
              value={newTask.description}
              onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
              className="bg-white border-[#5D4037]/30 min-h-32"
            />
            <Button
              onClick={handleCreate}
              className="w-full bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3]"
              disabled={loading}
            >
              {loading ? "Creating..." : "Create"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Task detail dialog — with DAG + feedback */}
      {selectedTask && (
        <TaskDetailDialog
          task={selectedTask}
          open={isDetailOpen}
          onOpenChange={setIsDetailOpen}
          feedbackPending={feedbackPending}
          feedbackData={feedbackData as FeedbackRequest | null}
          onFeedbackSubmitted={() => { refreshDetail(); refreshTasks(); }}
        />
      )}
    </div>
  );
}
