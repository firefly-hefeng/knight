"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { submitFeedback } from "@/lib/api";
import type { FeedbackRequest } from "@/types";

interface FeedbackDialogProps {
  taskId: string;
  feedbackRequest: FeedbackRequest;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitted?: () => void;
}

const ACTION_CONFIG: Record<string, { label: string; desc: string; color: string; hoverColor: string }> = {
  approve: {
    label: "Approve",
    desc: "Continue with the current plan",
    color: "bg-emerald-600 text-white",
    hoverColor: "hover:bg-emerald-700",
  },
  reject: {
    label: "Reject",
    desc: "Skip this step and continue",
    color: "bg-red-600 text-white",
    hoverColor: "hover:bg-red-700",
  },
  modify: {
    label: "Modify",
    desc: "Provide new instructions",
    color: "bg-[#D4853B] text-[#FDF6E3]",
    hoverColor: "hover:bg-[#B0682A]",
  },
  abort: {
    label: "Abort",
    desc: "Cancel the entire task",
    color: "bg-gray-700 text-white",
    hoverColor: "hover:bg-gray-800",
  },
};

const CHECKPOINT_LABELS: Record<string, { label: string; icon: string }> = {
  plan_review:    { label: "Plan Review", icon: "📋" },
  result_review:  { label: "Result Review", icon: "🔍" },
  approval_gate:  { label: "Approval Required", icon: "🛡️" },
  escalation:     { label: "Escalation", icon: "⚠️" },
};

export function FeedbackDialog({ taskId, feedbackRequest, open, onOpenChange, onSubmitted }: FeedbackDialogProps) {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const cpConfig = CHECKPOINT_LABELS[feedbackRequest.checkpointType] || {
    label: feedbackRequest.checkpointType,
    icon: "❓",
  };

  const handleSubmit = async () => {
    if (!selectedAction) return;
    setSubmitting(true);
    try {
      await submitFeedback(taskId, selectedAction, message || undefined);
      setSelectedAction(null);
      setMessage("");
      onOpenChange(false);
      onSubmitted?.();
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-[#2C1810] uppercase tracking-wide flex items-center gap-2">
            <span>{cpConfig.icon}</span>
            {cpConfig.label}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Question */}
          <div className="border border-[#5D4037]/30 rounded-xl p-4 bg-[#F5E6D3]/30">
            <p className="text-sm text-[#2C1810] leading-relaxed">{feedbackRequest.question}</p>
          </div>

          {/* Context */}
          {feedbackRequest.context && (
            <div className="border border-[#5D4037]/20 rounded-xl p-3 bg-[#FFFBF0]">
              <div className="text-[10px] text-[#8D6E63] uppercase tracking-wider mb-1">Context</div>
              <p className="text-xs text-[#5D4037] font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                {feedbackRequest.context}
              </p>
            </div>
          )}

          {/* Action buttons */}
          <div className="space-y-2">
            <div className="text-[10px] text-[#8D6E63] uppercase tracking-wider">Choose Action</div>
            <div className="grid grid-cols-2 gap-2">
              {feedbackRequest.options.map((option) => {
                const config = ACTION_CONFIG[option] || {
                  label: option,
                  desc: "",
                  color: "bg-gray-500 text-white",
                  hoverColor: "hover:bg-gray-600",
                };
                const isSelected = selectedAction === option;
                return (
                  <button
                    key={option}
                    onClick={() => setSelectedAction(option)}
                    className={`p-3 rounded-xl border-2 text-left transition-all ${
                      isSelected
                        ? "border-[#D4853B] bg-[#D4853B]/10 ring-2 ring-[#D4853B]/30"
                        : "border-[#5D4037]/20 hover:border-[#5D4037]/40"
                    }`}
                  >
                    <div className="font-serif text-sm text-[#2C1810] font-semibold">{config.label}</div>
                    <div className="text-[10px] text-[#8D6E63] mt-0.5">{config.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Message input (for modify or any action) */}
          {selectedAction && (
            <div>
              <div className="text-[10px] text-[#8D6E63] uppercase tracking-wider mb-1">
                {selectedAction === "modify" ? "New Instructions" : "Message (optional)"}
              </div>
              <Textarea
                placeholder={
                  selectedAction === "modify"
                    ? "Provide new instructions for this step..."
                    : "Add a comment..."
                }
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="bg-white border-[#5D4037]/30 min-h-20 text-sm"
              />
            </div>
          )}

          {/* Submit */}
          <Button
            onClick={handleSubmit}
            disabled={!selectedAction || submitting || (selectedAction === "modify" && !message.trim())}
            className="w-full bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3] disabled:opacity-50"
          >
            {submitting ? "Submitting..." : selectedAction ? `${ACTION_CONFIG[selectedAction]?.label || selectedAction}` : "Select an action"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ──────────────── Inline feedback banner ──────────────── */

interface FeedbackBannerProps {
  taskId: string;
  feedbackRequest: FeedbackRequest;
  onSubmitted?: () => void;
}

export function FeedbackBanner({ taskId, feedbackRequest, onSubmitted }: FeedbackBannerProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const cpConfig = CHECKPOINT_LABELS[feedbackRequest.checkpointType] || {
    label: feedbackRequest.checkpointType,
    icon: "❓",
  };

  return (
    <>
      <div className="border-2 border-amber-400 rounded-xl p-4 bg-amber-50 animate-pulse-slow">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{cpConfig.icon}</span>
            <div>
              <div className="text-xs text-amber-800 font-semibold uppercase tracking-wider">{cpConfig.label}</div>
              <div className="text-sm text-amber-900 mt-0.5">{feedbackRequest.question}</div>
            </div>
          </div>
          <Button
            onClick={() => setDialogOpen(true)}
            className="bg-amber-600 hover:bg-amber-700 text-white text-sm"
          >
            Respond
          </Button>
        </div>
      </div>

      <FeedbackDialog
        taskId={taskId}
        feedbackRequest={feedbackRequest}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmitted={onSubmitted}
      />
    </>
  );
}
