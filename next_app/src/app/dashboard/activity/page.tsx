"use client";

import { useEffect, useState } from "react";
import { Clock, History as HistoryIcon, ArrowRight, ExternalLink, Calendar } from "lucide-react";
import Link from "next/link";
import { format, formatDistanceToNow } from "date-fns";

import { apiFetch } from "@/lib/http";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/LanguageContext";

interface ActivitySession {
    id: number;
    lectureTitle: string;
    createdAt: string;
    finishedAt: string | null;
    correctCount: number;
    totalCount: number;
    mode: string;
}

export default function RecentActivityPage() {
    const { t } = useLanguage();
    const [sessions, setSessions] = useState<ActivitySession[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchActivity = async () => {
            try {
                const res = await apiFetch<any>("/api/review/history");
                if (res.ok) {
                    setSessions(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch recent activity", error);
            } finally {
                setLoading(false);
            }
        };
        fetchActivity();
    }, []);

    // Grouping by date
    const groupedSessions = sessions.reduce((acc, session) => {
        const dateKey = format(new Date(session.createdAt), "yyyy-MM-dd");
        if (!acc[dateKey]) acc[dateKey] = [];
        acc[dateKey].push(session);
        return acc;
    }, {} as Record<string, ActivitySession[]>);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("dashboard.activityPageTitle")}</h1>
                    <p className="text-muted-foreground">{t("dashboard.activityPageDesc")}</p>
                </div>
                <div className="hidden sm:block p-3 rounded-full bg-secondary/50">
                    <HistoryIcon className="h-6 w-6 text-muted-foreground" />
                </div>
            </div>

            {loading ? (
                <div className="space-y-8">
                    {[1, 2].map(i => (
                        <div key={i} className="space-y-4">
                            <div className="h-6 w-32 bg-muted animate-pulse rounded" />
                            <div className="space-y-3">
                                {[1, 2, 3].map(j => <div key={j} className="h-24 bg-muted animate-pulse rounded-xl" />)}
                            </div>
                        </div>
                    ))}
                </div>
            ) : Object.keys(groupedSessions).length === 0 ? (
                <Card className="border-border bg-card">
                    <CardContent className="flex flex-col items-center justify-center py-20">
                        <Clock className="h-12 w-12 text-muted-foreground/20 mb-4" />
                        <p className="text-lg font-medium text-foreground">{t("dashboard.activityPageNoActivityTitle")}</p>
                        <p className="text-sm text-muted-foreground mb-6">{t("dashboard.activityPageNoActivityDesc")}</p>
                        <Link href="/learn/practice">
                            <Button className="gap-2">
                                {t("dashboard.activityPageGoToPractice")} <ArrowRight className="h-4 w-4" />
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-8">
                    {Object.entries(groupedSessions).map(([date, daySessions]) => (
                        <div key={date} className="space-y-4">
                            <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                                <Calendar className="h-4 w-4" />
                                <span>{format(new Date(date), "MMMM d, yyyy")}</span>
                            </div>
                            <div className="grid gap-3">
                                {daySessions.map((session) => {
                                    const accuracy = session.totalCount > 0
                                        ? Math.round((session.correctCount / session.totalCount) * 100)
                                        : 0;

                                    return (
                                        <Card key={session.id} className="border-border bg-card hover:bg-muted/30 transition-colors">
                                            <CardContent className="flex items-center p-5">
                                                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                                    <Clock className="h-6 w-6" />
                                                </div>
                                                <div className="ml-4 flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="font-bold text-foreground text-lg truncate">
                                                            {session.lectureTitle}
                                                        </span>
                                                        <Badge variant="neutral" className="text-[10px] uppercase tracking-wider">
                                                            {session.mode}
                                                        </Badge>
                                                    </div>
                                                    <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                                                        <span>{format(new Date(session.createdAt), "h:mm a")}</span>
                                                        <span>•</span>
                                                        <span className="flex items-center gap-1.5">
                                                            <span className="font-medium text-foreground">{session.correctCount}</span> / {session.totalCount} {t("dashboard.activityPageCorrect")}
                                                            <span className={`ml-1 text-xs font-bold ${accuracy >= 80 ? 'text-success' : accuracy >= 60 ? 'text-warning' : 'text-danger'}`}>
                                                                ({accuracy}%)
                                                            </span>
                                                        </span>
                                                    </div>
                                                </div>
                                                <Link href={`/practice/session/${session.id}/result`}>
                                                    <Button variant="outline" size="sm" className="ml-4 gap-2 whitespace-nowrap">
                                                        {t("dashboard.activityPageViewResult")} <ExternalLink className="h-3.5 w-3.5" />
                                                    </Button>
                                                </Link>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
