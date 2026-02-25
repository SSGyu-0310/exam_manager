"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { NavContext, SIDEBAR_NAV, TOP_NAV } from "@/config/navigation";
import { useAuth } from "@/context/AuthContext";
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher";
import { useLanguage } from "@/context/LanguageContext";

export function TopNav() {
    const pathname = usePathname();
    const { user, logout, isAuthenticated, isLoading } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [openTopNavDropdown, setOpenTopNavDropdown] = useState<NavContext | null>(null);
    const { t } = useLanguage();

    useEffect(() => {
        setOpenTopNavDropdown(null);
    }, [pathname]);

    return (
        <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-border/60 bg-card/80 px-4 backdrop-blur lg:px-8">
            <div className="flex items-center gap-8">
                {/* Logo Area */}
                <Link href="/" className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-xs font-bold tracking-wide text-primary-foreground">
                        EM
                    </div>
                    <span className="hidden font-semibold lg:inline-block">Exam Manager</span>
                </Link>

                {/* Desktop Navigation */}
                <nav className="hidden items-center gap-6 md:flex">
                    {TOP_NAV.map((item) => {
                        const navValue = item.value as NavContext;
                        const isActive = pathname.startsWith(item.href);
                        const label = item.key ? t(item.key) : item.label;
                        const subItems = SIDEBAR_NAV[navValue] || [];
                        const isDropdownOpen = openTopNavDropdown === navValue;
                        return (
                            <div
                                key={item.value}
                                className="relative"
                                onMouseEnter={() => setOpenTopNavDropdown(navValue)}
                                onMouseLeave={() =>
                                    setOpenTopNavDropdown((prev) =>
                                        prev === navValue ? null : prev
                                    )
                                }
                                onFocusCapture={() => setOpenTopNavDropdown(navValue)}
                                onBlurCapture={(event) => {
                                    const nextFocus = event.relatedTarget as Node | null;
                                    if (!event.currentTarget.contains(nextFocus)) {
                                        setOpenTopNavDropdown((prev) =>
                                            prev === navValue ? null : prev
                                        );
                                    }
                                }}
                            >
                                <Link
                                    href={item.href}
                                    onClick={() => setOpenTopNavDropdown(null)}
                                    className={cn(
                                        "inline-flex items-center rounded-md px-1 py-1 text-sm font-medium transition-colors hover:text-primary",
                                        isActive ? "text-primary font-bold" : "text-muted-foreground"
                                    )}
                                >
                                    {label}
                                </Link>

                                {subItems.length > 0 && (
                                    <div
                                        className={cn(
                                            "absolute left-1/2 top-full z-30 w-56 -translate-x-1/2 rounded-xl border border-border bg-card p-1 shadow-xl ring-1 ring-black/5 transition-all duration-150",
                                            "before:absolute before:-top-2 before:left-0 before:right-0 before:h-2 before:content-['']",
                                            isDropdownOpen
                                                ? "pointer-events-auto translate-y-0 opacity-100"
                                                : "pointer-events-none translate-y-1 opacity-0",
                                            "lg:hidden"
                                        )}
                                    >
                                        <div className="mb-1 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70">
                                            {label}
                                        </div>
                                        <div className="space-y-0.5">
                                            {subItems.map((subItem) => {
                                                const subLabel = subItem.key ? t(subItem.key) : subItem.label;
                                                const isSubActive = pathname === subItem.href;
                                                const Icon = subItem.icon;
                                                return (
                                                    <Link
                                                        key={subItem.href}
                                                        href={subItem.href}
                                                        onClick={() => setOpenTopNavDropdown(null)}
                                                        className={cn(
                                                            "flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors",
                                                            isSubActive
                                                                ? "bg-primary/10 text-primary"
                                                                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                                                        )}
                                                    >
                                                        <Icon className="h-4 w-4" />
                                                        <span>{subLabel}</span>
                                                    </Link>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </nav>
            </div>



            {/* Right Side Actions */}
            <div className="flex items-center gap-4">
                <LanguageSwitcher />
                <div className="relative hidden w-64 md:block">
                    {/* Placeholder for Global Search */}
                    <div className="flex h-9 w-full items-center rounded-md border border-input bg-muted/50 px-3 py-1 text-sm text-muted-foreground">
                        <span className="opacity-50">Search... (Ctrl+K)</span>
                    </div>
                </div>

                {isLoading ? (
                    <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
                ) : isAuthenticated && user ? (
                    <div className="relative">
                        <button
                            onClick={() => setIsMenuOpen(!isMenuOpen)}
                            className="flex items-center gap-2 rounded-full border border-border bg-background px-2 py-1 hover:bg-muted/50"
                        >
                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                                {user.email[0].toUpperCase()}
                            </div>
                            <span className="mr-1 text-xs font-medium text-muted-foreground max-w-[100px] truncate hidden md:block">
                                {user.email.split('@')[0]}
                            </span>
                        </button>

                        {isMenuOpen && (
                            <div className="absolute right-0 top-full mt-2 w-48 rounded-md border border-border bg-popover p-1 shadow-md animate-in fade-in zoom-in-95">
                                <div className="px-2 py-1.5 text-xs text-muted-foreground border-b border-border mb-1">
                                    {user.email}
                                </div>
                                <Link
                                    href="/manage/settings"
                                    className="block rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
                                    onClick={() => setIsMenuOpen(false)}
                                >
                                    Settings
                                </Link>
                                <button
                                    onClick={() => {
                                        setIsMenuOpen(false);
                                        logout();
                                    }}
                                    className="block w-full text-left rounded-sm px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                                >
                                    Sign out
                                </button>
                            </div>
                        )}

                        {/* Overlay to close menu */}
                        {isMenuOpen && (
                            <div
                                className="fixed inset-0 z-[-1]"
                                onClick={() => setIsMenuOpen(false)}
                            />
                        )}
                    </div>
                ) : (
                    <div className="flex items-center gap-2">
                        <Link
                            href="/login"
                            className="text-sm font-medium text-muted-foreground hover:text-primary"
                        >
                            Log in
                        </Link>
                        <Link
                            href="/register"
                            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                        >
                            Sign up
                        </Link>
                    </div>
                )}
            </div>
        </header>
    );
}
