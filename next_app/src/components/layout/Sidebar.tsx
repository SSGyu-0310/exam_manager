"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { NavContext, SIDEBAR_NAV, TOP_NAV } from "@/config/navigation";
import { useLanguage } from "@/context/LanguageContext";

export function Sidebar() {
    const pathname = usePathname();

    const { t } = useLanguage();

    // Determine current context based on URL
    const currentNav = TOP_NAV.find((nav) => pathname.startsWith(nav.href));
    const currentContext = (currentNav?.value as NavContext) || "home";
    const sidebarItems = SIDEBAR_NAV[currentContext] || [];
    const currentLabel = currentNav?.key
        ? t(currentNav.key)
        : currentNav?.label || t(`nav.${currentContext}`);

    return (
        <aside className="hidden h-[calc(100vh-4rem)] w-64 flex-col border-r border-border/60 bg-card/50 backdrop-blur lg:flex">
            <div className="flex-1 py-6 px-4">
                <div className="mb-4 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                    {currentLabel}
                </div>
                <nav className="space-y-1">
                    {sidebarItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = pathname === item.href;
                        const label = item.key ? t(item.key) : item.label;

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-primary/10 text-primary"
                                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                )}
                            >
                                <Icon className="h-4 w-4" />
                                <span>{label}</span>
                            </Link>
                        );
                    })}
                </nav>
            </div>

            <div className="p-4">
                {/* Placeholder for Footer/User Profile */}
            </div>
        </aside>
    );
}
