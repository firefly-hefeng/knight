"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Play, CheckCircle, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Navigation } from "@/components/Navigation";

const stats = [
  { value: "10K+", label: "Tasks" },
  { value: "500+", label: "Agents" },
  { value: "99.9%", label: "Uptime" },
];

export default function Home() {
  const heroRef = useRef<HTMLDivElement>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (heroRef.current) {
        const rect = heroRef.current.getBoundingClientRect();
        const x = (e.clientX - rect.left - rect.width / 2) / rect.width;
        const y = (e.clientY - rect.top - rect.height / 2) / rect.height;
        setMousePosition({ x: x * 8, y: y * -8 });
      }
    };

    const hero = heroRef.current;
    if (hero) {
      hero.addEventListener("mousemove", handleMouseMove);
      return () => hero.removeEventListener("mousemove", handleMouseMove);
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#FDF6E3] parchment-texture">
      <Navigation />
      <section ref={heroRef} className="relative min-h-screen flex items-center overflow-hidden gradient-hero">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 -left-32 w-64 h-64 bg-[#D4853B]/8 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-[#5D4037]/5 rounded-full blur-3xl" />
        </div>

        <div className="relative w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8 animate-slide-up">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-[#5D4037]/30 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-[#D4853B] animate-pulse" />
                <span className="text-sm font-medium text-[#5D4037] uppercase tracking-wider">
                  AI Agent Task Orchestration System
                </span>
              </div>

              <div className="space-y-1">
                <h1 className="font-display text-6xl sm:text-7xl lg:text-8xl text-[#2C1810] leading-[1.1]">
                  BUILD YOUR
                </h1>
                <h1 className="font-display text-6xl sm:text-7xl lg:text-8xl leading-[1.1]">
                  <span className="text-[#D4853B]">AGENTS ARMY</span>
                </h1>
              </div>

              <p className="text-xl text-[#5D4037] max-w-lg leading-relaxed">
                Knight System is a powerful multi-agent task orchestration platform.
                Create tasks, assign agents, monitor execution flows — let your AI army work without ever stopping.
              </p>

              <div className="flex flex-wrap gap-4">
                <Link href="/tasks">
                  <Button variant="primary" size="lg" className="gap-2 bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3] border-[#B0682A]">
                    Start Building
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </Link>
                <Button variant="secondary" size="lg" className="gap-2 border-[#5D4037] text-[#5D4037] hover:bg-[#5D4037] hover:text-[#FDF6E3]">
                  <Play className="w-4 h-4" />
                  Documentation
                </Button>
              </div>

              <div className="flex flex-wrap gap-8 pt-4">
                {stats.map((stat) => (
                  <div key={stat.label} className="space-y-1">
                    <div className="font-numbers text-4xl text-[#2C1810]">{stat.value}</div>
                    <div className="text-xs text-[#8D6E63] uppercase tracking-wider">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>

            <div
              className="relative flex items-center justify-center lg:justify-end"
              style={{
                transform: `perspective(1000px) rotateY(${mousePosition.x}deg) rotateX(${mousePosition.y}deg)`,
                transition: "transform 0.15s ease-out",
              }}
            >
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-[#D4853B]/15 to-[#B0682A]/15 rounded-full blur-3xl scale-110" />
                <Image
                  src="/lodo-main1.png"
                  alt="Knight System"
                  width={500}
                  height={500}
                  className="relative animate-float drop-shadow-2xl"
                />
                <div className="absolute -top-4 -right-4 px-3 py-1.5 bg-white rounded-xl border border-[#5D4037]/30 shadow-lg">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs font-medium text-[#5D4037] uppercase tracking-wider">Online</span>
                  </div>
                </div>

                <div
                  className="absolute -bottom-4 -left-4 px-3 py-1.5 bg-white rounded-xl border border-[#5D4037]/30 shadow-lg"
                >
                  <div className="flex items-center gap-2">
                    <Image src="/logo.png" alt="" width={16} height={16} />
                    <span className="text-xs font-medium text-[#5D4037] uppercase tracking-wider">
                      Never Stops
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-[#8D6E63]">
          <span className="text-xs font-medium uppercase tracking-wider">Scroll</span>
          <div className="w-6 h-10 rounded-xl border border-[#5D4037]/30 flex items-start justify-center p-2">
            <div className="w-1 h-1 rounded-full bg-[#D4853B] animate-bounce" />
          </div>
        </div>
      </section>

      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="font-serif text-3xl sm:text-4xl text-[#2C1810] uppercase tracking-wide mb-4">
              Powerful Features
            </h2>
            <p className="text-lg text-[#8D6E63]">Complete support for your AI army</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { icon: "/icons/task.png", title: "Task Orchestration", desc: "Visual task pipelines with real-time execution monitoring" },
              { icon: "/icons/agent.png", title: "Agent Management", desc: "Unified AI agent management with capability tracking" },
              { icon: "/icons/workflow.png", title: "Workflow Design", desc: "Drag-and-drop workflow design without coding" },
              { icon: "/icons/monitor.png", title: "Real-time Monitoring", desc: "Live task execution logs and performance metrics" },
              { icon: "/icons/scale.png", title: "Auto Scaling", desc: "Automatically adjust agent count based on workload" },
              { icon: "/icons/security.png", title: "Secure & Reliable", desc: "Enterprise-grade security with encrypted data transmission" },
            ].map((feature) => (
              <Card key={feature.title} className="group">
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-14 h-14 rounded-xl overflow-hidden flex-shrink-0 border border-[#5D4037]/30 bg-[#F5E6D3]/50">
                      <Image src={feature.icon} alt={feature.title} width={56} height={56} className="w-full h-full object-cover" />
                    </div>
                    <div>
                      <h3 className="font-serif text-lg font-semibold text-[#2C1810] uppercase tracking-wide mb-2 group-hover:text-[#D4853B] transition-colors">
                        {feature.title}
                      </h3>
                      <p className="text-[#8D6E63] text-sm leading-relaxed">{feature.desc}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="py-24 bg-[#FDF6E3]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <h2 className="font-serif text-3xl sm:text-4xl text-[#2C1810] uppercase tracking-wide">Task Board</h2>
              <p className="text-lg text-[#5D4037] leading-relaxed">
                Keep all tasks in view at a glance. Visualize the task execution flow from creation to completion.
              </p>
              <ul className="space-y-4">
                {["Real-time status updates", "Intelligent assignment algorithm", "Execution log tracking", "Automatic error retry"].map((item) => (
                  <li key={item} className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                    <span className="text-[#5D4037]">{item}</span>
                  </li>
                ))}
              </ul>
              <Link href="/tasks">
                <Button variant="primary" className="gap-2 mt-4 bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3]">
                  View Task Board
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </div>

            <div className="space-y-4">
              {[
                { name: "Code Review Task", status: "In Progress", color: "text-orange-700 bg-orange-100 border-orange-300", agent: "Code Knight #1", progress: 65 },
                { name: "Data Analysis Task", status: "Pending", color: "text-amber-700 bg-amber-100 border-amber-300", agent: "Data Mage #3", progress: 0 },
                { name: "Documentation Task", status: "Completed", color: "text-emerald-700 bg-emerald-100 border-emerald-300", agent: "Scribe #2", progress: 100 },
              ].map((task, idx) => (
                <div
                  key={task.name}
                  className="bg-white border border-[#5D4037]/30 rounded-xl p-5 hover:border-[#D4853B] hover:shadow-md transition-all cursor-pointer group"
                  style={{ transform: `translateX(${idx * 16}px)` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-serif font-semibold text-[#2C1810] uppercase tracking-wide group-hover:text-[#D4853B] transition-colors">{task.name}</h4>
                    <span className={`px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border rounded-lg ${task.color}`}>
                      {task.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-[#8D6E63] mb-3 font-mono">
                    <Users className="w-4 h-4" />
                    {task.agent}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-[#F5E6D3] border border-[#5D4037]/20 rounded-lg overflow-hidden">
                      <div className="h-full bg-[#D4853B] transition-all duration-1000" style={{ width: `${task.progress}%` }} />
                    </div>
                    <span className="text-sm font-mono text-[#5D4037]">{task.progress}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
