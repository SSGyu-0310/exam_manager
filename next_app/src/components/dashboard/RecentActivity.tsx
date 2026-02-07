"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

import { apiFetch } from "@/lib/http";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { useLanguage } from "@/context/LanguageContext";

interface Session {
    sessionId: number;
    lectureTitle: string;
    mode: string;
    createdAt: string;
    totalQuestions: number;
    answeredCount: number;
    correctCount: number;
}

export function RecentActivity() {
    const { t } = useLanguage();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSessions = async () => {
            try {
                const data = await apiFetch<any>("/api/practice/sessions?limit=5");
                if (data.sessions) {
                    setSessions(data.sessions);
                }
            } catch (error) {
                console.error("Failed to fetch sessions", error);
            } finally {
                setLoading(false);
            }
        };

        fetchSessions();
    }, []);

    if (loading) {
        return (
            <Card className="lg:col-span-2 shadow-sm border-border animate-pulse">
                <CardHeader className="pb-3 border-b border-border/50">
                    <div className="h-6 w-32 bg-muted rounded" />
                </CardHeader>
                <CardContent className="pt-4 h-48 bg-muted/20" />
            </Card>
        );
    }

    return (
        <Card className="lg:col-span-2 shadow-sm border-border">
            <CardHeader className="pb-3 border-b border-border/50">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold text-foreground">{t("dashboard.recentActivityTitle")}</CardTitle>
                    <Link href="/review/history">
                        <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground hover:text-foreground">{t("dashboard.recentActivityViewAll")}</Button>
                    </Link>
                </div>
            </CardHeader>
            <CardContent className="pt-4">
                <div className="space-y-1">
                    {sessions.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4 text-center">{t("dashboard.recentActivityEmpty")}</p>
                    ) : (
                        sessions.map((session) => {
                            const score = session.answeredCount > 0
                                ? Math.round((session.correctCount / session.answeredCount) * 100)
                                : 0;
                            const isPassed = score >= 60;

                            return (
                                <div key={session.sessionId} className="flex items-center gap-4 rounded-md p-2 transition-colors hover:bg-muted/50">
                                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary/80 text-muted-foreground">
                                        <Clock className="h-4 w-4" />
                                    </div>
                                    <div className="flex-1 space-y-0.5">
                                        <p className="text-sm font-medium text-foreground">
                                            {session.lectureTitle || t("dashboard.recentActivitySessionFallback")}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {formatDistanceToNow(new Date(session.createdAt), { addSuffix: true })} • {t("dashboard.recentActivityScoreLabel")}: {score}%
                                        </p>
                                    </div>
                                    <Badge
                                        variant={isPassed ? "success" : "danger"}
                                        className="h-6"
                                    >
                                        {isPassed ? t("dashboard.recentActivityPassed") : t("dashboard.recentActivityFailed")}
                                    </Badge>
                                </div>
                            );
                        })
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
