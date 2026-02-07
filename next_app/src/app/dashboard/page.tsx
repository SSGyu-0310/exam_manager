"use client";

import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { WeeklyProgress } from "@/components/dashboard/WeeklyProgress";
import { Bookmarks } from "@/components/dashboard/Bookmarks";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";

export default function DashboardPage() {
    const { t } = useLanguage();
    const { user, isLoading } = useAuth();

    // Safely extract username or default to empty
    const username = user?.email?.split('@')[0] || '';

    // Show loading state while checking authentication
    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="animate-pulse text-lg text-muted-foreground">{t("common.loading")}</div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">
                    {t("dashboard.welcome")}{user ? `, ${username}` : ''}{t("dashboard.welcomeSuffix")}
                </h2>
                <p className="text-muted-foreground">
                    {t("dashboard.subtitle")}
                </p>
            </div>

            <OverviewCards />

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <RecentActivity />

                <div className="space-y-6">
                    <WeeklyProgress />
                    <Bookmarks />
                </div>
            </div>
        </div>
    );
}
