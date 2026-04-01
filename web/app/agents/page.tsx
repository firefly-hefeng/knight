"use client";

import { useState, useEffect } from "react";
import { Plus, Search, Activity, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Navigation } from "@/components/Navigation";
import { getAgents } from "@/lib/api";
import type { Agent, AgentStatus } from "@/types";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<AgentStatus | "all">("all");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  useEffect(() => {
    loadAgents();
    const interval = setInterval(loadAgents, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadAgents = async () => {
    try {
      const data = await getAgents();
      setAgents(data);
    } catch (err) {
      console.error('Failed to load agents:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch = agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.capabilities.some((cap) => cap.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === "all" || agent.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: agents.length,
    idle: agents.filter((a) => a.status === "idle").length,
    busy: agents.filter((a) => a.status === "busy").length,
    offline: agents.filter((a) => a.status === "offline").length,
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FDF6E3] flex items-center justify-center">
        <div className="text-[#8D6E63]">Loading agents...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FDF6E3] parchment-texture">
      <Navigation />
      <div className="bg-white border-b border-[#5D4037]/20 sticky top-16 z-30 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="font-serif text-2xl text-[#2C1810] uppercase tracking-wide">Agent Army</h1>
              <p className="text-sm text-[#8D6E63] mt-1">Manage and configure your AI agents</p>
            </div>
            <Button className="gap-2 bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3]">
              <Plus className="w-4 h-4" />
              Create Agent
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
            {[
              { label: "All", value: stats.total, status: "all" },
              { label: "Idle", value: stats.idle, status: "idle" },
              { label: "Busy", value: stats.busy, status: "busy" },
              { label: "Offline", value: stats.offline, status: "offline" },
            ].map((stat) => (
              <button
                key={stat.label}
                onClick={() => setStatusFilter(stat.status as AgentStatus | "all")}
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
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#8D6E63]" />
          <Input
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-white border-[#5D4037]/30"
          />
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        {filteredAgents.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-xl border-2 border-[#5D4037]/30 bg-[#F5E6D3]/50 flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-[#8D6E63]" />
            </div>
            <h3 className="font-serif text-lg text-[#2C1810] mb-1">No agents found</h3>
            <p className="text-sm text-[#8D6E63]">Try adjusting your search or create a new agent</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredAgents.map((agent) => (
              <Card
                key={agent.id}
                className="group cursor-pointer"
                onClick={() => {
                  setSelectedAgent(agent);
                  setIsDetailOpen(true);
                }}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <Avatar className="w-12 h-12 bg-[#F5E6D3] border border-[#5D4037]/30">
                          <AvatarFallback className="text-[#5D4037]">
                            {agent.name.slice(0, 2).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <span
                          className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#FDF6E3] ${
                            agent.status === "idle" ? "bg-emerald-500" :
                            agent.status === "busy" ? "bg-[#D4853B]" : "bg-gray-400"
                          }`}
                        />
                      </div>
                      <div>
                        <h3 className="font-serif text-lg font-semibold text-[#2C1810] uppercase tracking-wide group-hover:text-[#D4853B] transition-colors">
                          {agent.name}
                        </h3>
                        <span className="text-xs text-[#8D6E63] uppercase tracking-wider">
                          {agent.status}
                        </span>
                      </div>
                    </div>
                    <StatusBadge status={agent.status} />
                  </div>

                  <p className="text-sm text-[#8D6E63] mb-4 line-clamp-2">
                    {agent.description || "AI Agent"}
                  </p>

                  {agent.currentTask && (
                    <div className="border border-[#5D4037]/30 rounded-xl p-3 bg-[#F5E6D3]/30 mb-4">
                      <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-1">Current Task</div>
                      <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-[#D4853B]" />
                        <span className="text-sm text-[#2C1810] font-medium truncate">{agent.currentTask}</span>
                      </div>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {agent.capabilities.slice(0, 4).map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-0.5 bg-[#F5E6D3] border border-[#5D4037]/20 rounded-lg text-xs text-[#5D4037]"
                      >
                        {cap}
                      </span>
                    ))}
                    {agent.capabilities.length > 4 && (
                      <span className="px-2 py-0.5 text-xs text-[#8D6E63]">
                        +{agent.capabilities.length - 4}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-[#5D4037]/20">
                    <div className="flex items-center gap-1.5 text-sm text-[#8D6E63]">
                      <CheckCircle className="w-4 h-4 text-emerald-600" />
                      <span className="font-mono">{agent.completedTasks || 0}</span>
                      <span className="text-xs uppercase tracking-wider">tasks</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {selectedAgent && (
        <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-serif text-xl text-[#2C1810] uppercase tracking-wide">Agent Details</DialogTitle>
            </DialogHeader>
            <div className="space-y-5">
              <div className="flex items-center gap-4">
                <Avatar className="w-16 h-16 bg-[#F5E6D3] border border-[#5D4037]/30">
                  <AvatarFallback className="text-[#5D4037] text-xl">
                    {selectedAgent.name.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <h3 className="font-serif text-lg font-semibold text-[#2C1810] uppercase tracking-wide">
                    {selectedAgent.name}
                  </h3>
                  <StatusBadge status={selectedAgent.status} />
                </div>
              </div>

              <p className="text-[#8D6E63]">{selectedAgent.description || "AI Agent"}</p>

              {selectedAgent.currentTask && (
                <div className="border border-[#5D4037]/30 rounded-xl p-3 bg-[#F5E6D3]/30">
                  <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-1">Current Task</div>
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[#D4853B]" />
                    <span className="font-medium text-[#2C1810]">{selectedAgent.currentTask}</span>
                  </div>
                </div>
              )}

              <div>
                <div className="text-xs text-[#8D6E63] uppercase tracking-wider mb-2">Capabilities</div>
                <div className="flex flex-wrap gap-2">
                  {selectedAgent.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="px-3 py-1 bg-[#D4853B]/10 text-[#B0682A] border border-[#D4853B]/30 rounded-lg text-sm"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="border border-[#5D4037]/30 rounded-xl p-4 text-center bg-[#F5E6D3]/30">
                  <div className="text-2xl font-serif text-[#2C1810]">
                    {selectedAgent.completedTasks || 0}
                  </div>
                  <div className="text-xs text-[#8D6E63] uppercase tracking-wider">Tasks Completed</div>
                </div>
                <div className="border border-[#5D4037]/30 rounded-xl p-4 text-center bg-[#F5E6D3]/30">
                  <div className="text-2xl font-serif text-[#2C1810]">
                    {selectedAgent.capabilities.length}
                  </div>
                  <div className="text-xs text-[#8D6E63] uppercase tracking-wider">Capabilities</div>
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
