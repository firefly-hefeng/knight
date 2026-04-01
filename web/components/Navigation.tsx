"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const navLinks = [
  {
    label: "Home",
    href: "/",
    desc: "Overview of the Knight System platform"
  },
  {
    label: "Task Board",
    href: "/tasks",
    desc: "Create, manage and monitor task execution pipelines"
  },
  {
    label: "Agent Army",
    href: "/agents",
    desc: "View and manage your AI agent fleet with capabilities"
  },
];

export function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(href);
  };

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          isScrolled
            ? "bg-[#FDF6E3]/95 backdrop-blur-xl shadow-sm border-b border-[#D4C4A8]"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 lg:h-20">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-lg overflow-hidden transition-transform duration-300 group-hover:scale-105">
                <Image src="/logo.png" alt="Knight System" width={40} height={40} className="w-full h-full object-contain" />
              </div>
              <span className="font-logo text-2xl text-[#2C1810]">Knight System</span>
            </Link>

            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <div key={link.href} className="group relative">
                  <Link
                    href={link.href}
                    className={`relative px-4 py-2 text-base font-medium transition-colors duration-200 rounded-lg ${
                      isActive(link.href)
                        ? "text-[#D4853B]"
                        : "text-[#5D4037] hover:text-[#2C1810] hover:bg-[#D4853B]/10"
                    }`}
                  >
                    {link.label}
                    {isActive(link.href) && (
                      <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-[#D4853B]" />
                    )}
                  </Link>
                  <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-56 p-3 bg-white border border-[#5D4037]/30 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pointer-events-none">
                    <p className="text-xs text-[#5D4037] text-center">{link.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="hidden md:block group relative">
              <Button size="sm" className="bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3] cursor-help">
                Features
              </Button>
              <div className="absolute right-0 top-full mt-2 w-64 p-4 bg-white border border-[#5D4037]/30 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
                <p className="text-sm text-[#5D4037] leading-relaxed">
                  <strong className="text-[#2C1810]">Knight System</strong> - Multi-agent task orchestration platform. Create tasks, assign agents, and monitor execution flows in real-time.
                </p>
              </div>
            </div>

            <button
              className="md:hidden p-2 rounded-lg hover:bg-[#D4853B]/10 transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? (
                <X className="w-6 h-6 text-[#5D4037]" />
              ) : (
                <Menu className="w-6 h-6 text-[#5D4037]" />
              )}
            </button>
          </div>
        </div>
      </nav>

      <div
        className={`fixed inset-0 z-40 md:hidden transition-all duration-300 ${
          isMobileMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      >
        <div className="absolute inset-0 bg-[#2C1810]/20 backdrop-blur-sm" onClick={() => setIsMobileMenuOpen(false)} />
        <div
          className={`absolute top-16 left-4 right-4 bg-[#FDF6E3] rounded-2xl shadow-xl border border-[#D4C4A8] p-4 transition-all duration-300 ${
            isMobileMenuOpen ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0"
          }`}
        >
          <div className="flex flex-col gap-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                  isActive(link.href)
                    ? "bg-[#D4853B]/15 text-[#B0682A]"
                    : "text-[#5D4037] hover:bg-[#D4853B]/10"
                }`}
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-2 mt-2 border-t border-[#D4C4A8]">
              <Button className="w-full bg-[#D4853B] hover:bg-[#E8A55C] text-[#FDF6E3]">Get Started</Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
