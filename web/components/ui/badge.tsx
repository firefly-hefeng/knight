import * as React from "react";
import { cn } from "@/lib/utils";
import type { TaskStatus, AgentStatus } from "@/types";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "primary" | "success" | "warning" | "danger" | "info";
}

const statusVariants: Record<string, { variant: BadgeProps["variant"]; label: string }> = {
  pending: { variant: "warning", label: "PENDING" },
  running: { variant: "info", label: "RUNNING" },
  completed: { variant: "success", label: "COMPLETED" },
  failed: { variant: "danger", label: "FAILED" },
  cancelled: { variant: "default", label: "CANCELLED" },
  waiting_for_feedback: { variant: "warning", label: "AWAITING FEEDBACK" },
  evaluating: { variant: "info", label: "EVALUATING" },
  idle: { variant: "default", label: "IDLE" },
  busy: { variant: "primary", label: "BUSY" },
  offline: { variant: "default", label: "OFFLINE" },
};

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "default", children, ...props }, ref) => {
    const variants = {
      default: "bg-[#F5E6D3] text-[#5D4037] border-[#5D4037]/40",
      primary: "bg-[#D4853B]/15 text-[#B0682A] border-[#D4853B]/50",
      success: "bg-emerald-50 text-emerald-800 border-emerald-400",
      warning: "bg-amber-50 text-amber-800 border-amber-400",
      danger: "bg-red-50 text-red-800 border-red-400",
      info: "bg-orange-50 text-orange-800 border-orange-400",
    };

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border rounded-sm",
          variants[variant],
          className
        )}
        {...props}
      >
        {children}
      </span>
    );
  }
);

Badge.displayName = "Badge";

interface StatusBadgeProps extends Omit<BadgeProps, "variant"> {
  status: TaskStatus | AgentStatus;
}

const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ status, ...props }, ref) => {
    const config = statusVariants[status] || { variant: "default", label: status };
    return (
      <Badge ref={ref} variant={config.variant} {...props}>
        {config.label}
      </Badge>
    );
  }
);

StatusBadge.displayName = "StatusBadge";

export { Badge, StatusBadge };
