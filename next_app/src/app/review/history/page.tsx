"use client";

import { useEffect, useState } from "react";
import { History, Clock, FileCheck, ExternalLink } from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { useLanguage } from "@/context/LanguageContext";

import { apiFetch } from "@/lib/http";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SessionHistory {
    id: number;
    lectureTitle: string;
    createdAt: string;
    finishedAt: string | null;
    correctCount: number;
    totalCount: number;
    mode: string;
}

export default function ReviewHistoryPage() {
    const { t } = useLanguage();
    const [sessions, setSessions] = useState<SessionHistory[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await apiFetch<any>("/api/review/history");
                if (res.ok) {
                    setSessions(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch history", error);
            } finally {
                setLoading(false);
            }
        };
        fetchHistory();
    }, []);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("review.history")}</h1>
                <p className="text-muted-foreground">{t("review.historyDesc")}</p>
            </div>

            <div className="grid gap-4">
                {loading ? (
                    [1, 2, 3, 4, 5].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-xl" />)
                ) : sessions.length === 0 ? (
                    <Card className="border-border bg-card">
                        <CardContent className="flex flex-col items-center justify-center py-12">
                            <History className="h-12 w-12 text-muted-foreground/30 mb-4" />
                            <p className="text-lg font-medium text-foreground">{t("review.noHistory")}</p>
                            <Link href="/learn/practice">
                                <Button variant="link" className="text-primary mt-2">{t("review.startFirstPractice")}</Button>
                            </Link>
                        </CardContent>
                    </Card>
                ) : (
                    sessions.map((session) => {
                        const accuracy = session.totalCount > 0
                            ? Math.round((session.correctCount / session.totalCount) * 100)
                            : 0;

                        return (
                            <Card key={session.id} className="border-border bg-card hover:border-primary/30 transition-colors">
                                <CardContent className="flex items-center p-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/50 text-muted-foreground">
                                        <FileCheck className="h-5 w-5" />
                                    </div>
                                    <div className="ml-4 flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-foreground">{session.lectureTitle}</span>
                                            <Badge variant="neutral" className="text-[9px] uppercase">{session.mode}</Badge>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                                            <span className="flex items-center gap-1">
                                                <Clock className="h-3 w-3" />
                                                {formatDistanceToNow(new Date(session.createdAt), { addSuffix: true })}
                                            </span>
                                            <span>• {t("review.score")}: {session.correctCount}/{session.totalCount} ({accuracy}%)</span>
                                        </div>
                                    </div>
                                    <Link href={`/practice/session/${session.id}/result`}>
                                        <Button variant="ghost" size="sm" className="text-xs gap-1 hover:text-primary">
                                            {t("review.details")} <ExternalLink className="h-3 w-3" />
                                        </Button>
                                    </Link>
                                </CardContent>
                            </Card>
                        );
                    })
                )}
            </div>
        </div>
    );
}

