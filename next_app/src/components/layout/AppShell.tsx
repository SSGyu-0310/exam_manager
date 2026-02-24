"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const isPracticeSession = pathname?.startsWith("/practice/session/");

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <TopNav />
      <div className="flex flex-1">
        {!isPracticeSession && <Sidebar />}
        <main
          className={`flex-1 overflow-x-hidden ${isPracticeSession ? "" : "p-6 lg:p-8"
            }`}
        >
          <div className={isPracticeSession ? "" : "mx-auto max-w-7xl"}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

