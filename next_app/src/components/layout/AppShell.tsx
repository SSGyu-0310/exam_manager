"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  FileUp,
  LayoutGrid,
  Layers,
  ListChecks,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const navItems = [
  { label: "Dashboard", href: "/manage", icon: LayoutGrid },
  { label: "Blocks/Lectures", href: "/manage/blocks", icon: Layers },
  { label: "Exams", href: "/manage/exams", icon: ListChecks },
  { label: "Upload PDF", href: "/manage/upload-pdf", icon: FileUp },
  { label: "Unclassified", href: "/exam/unclassified", icon: Sparkles },
  { label: "Practice", href: "/lectures", icon: BookOpen },
];

type AppShellProps = {
  children: React.ReactNode;
};

function isNavActive(pathname: string, href: string) {
  const normalized =
    pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  if (href === "/manage") {
    return normalized === "/manage";
  }
  return normalized === href || normalized.startsWith(`${href}/`);
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const current = navItems.find((item) => isNavActive(pathname, item.href));
  const pageTitle = current?.label ?? "Exam Manager";

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 flex-col border-r border-border/60 bg-card/80 backdrop-blur lg:flex">
        <div className="flex items-center gap-3 px-6 py-6">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-sm font-bold tracking-wide text-primary-foreground">
            EM
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Exam Manager
            </p>
            <p className="text-sm font-semibold">Admin Console</p>
          </div>
        </div>
        <nav className="flex-1 px-4">
          <div className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = isNavActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-soft"
                      : "text-foreground/80 hover:bg-muted"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </nav>
        <div className="px-6 pb-6">
          <div className="rounded-xl border border-border/70 bg-muted/70 p-4 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Local Mode</span>
              <Badge variant="success">On</Badge>
            </div>
            <p className="mt-2">Flask: :5000 | Next: :3000</p>
          </div>
        </div>
      </aside>
      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-border/60 bg-card/80 backdrop-blur">
          <div className="flex items-center justify-between px-4 py-4 lg:px-8">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Exam Manager
              </p>
              <h1 className="text-lg font-semibold text-foreground">{pageTitle}</h1>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <Badge variant="ai">AI Ready</Badge>
            </div>
          </div>
          <div className="flex gap-2 overflow-x-auto px-4 pb-4 lg:hidden">
            {navItems.map((item) => {
              const isActive = isNavActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "whitespace-nowrap rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-wide transition",
                    isActive
                      ? "border-transparent bg-primary text-primary-foreground shadow-soft"
                      : "border-border bg-card text-foreground/80 hover:bg-muted"
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </header>
        <main className="flex-1 px-4 py-8 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
