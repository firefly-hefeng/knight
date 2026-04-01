"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

interface Step {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  agent?: string;
}

interface TaskPipelineProps {
  steps: Step[];
  progress?: number;
  logs?: string[];
}

const statusConfig = {
  pending: { color: "bg-gray-500/20 text-gray-400", icon: "○" },
  running: { color: "bg-blue-500/20 text-blue-400", icon: "◐" },
  completed: { color: "bg-green-500/20 text-green-400", icon: "●" },
  failed: { color: "bg-red-500/20 text-red-400", icon: "✕" },
};

export function TaskPipeline({ steps, progress = 0, logs = [] }: TaskPipelineProps) {
  return (
    <Card className="p-6">
      <div className="space-y-4">
        {progress > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        <div className="space-y-3">
          {steps.map((step, idx) => {
            const config = statusConfig[step.status];
            const isLast = idx === steps.length - 1;

            return (
              <div key={step.id} className="flex items-start gap-4">
                <div className="flex flex-col items-center">
                  <span className={`text-xl ${config.color.split(' ')[1]}`}>
                    {config.icon}
                  </span>
                  {!isLast && (
                    <div className="w-px h-8 bg-border" />
                  )}
                </div>
                <div className="flex-1 pb-2">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-base">{step.name}</span>
                    <Badge className={config.color}>{step.status}</Badge>
                  </div>
                  {step.agent && (
                    <span className="text-sm text-muted-foreground">Agent: {step.agent}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {logs.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="text-sm font-medium mb-2">Recent Logs</div>
            <div className="space-y-1 text-sm text-muted-foreground font-mono">
              {logs.map((log, i) => (
                <div key={i} className="truncate">{log}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
