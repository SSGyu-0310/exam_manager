"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/http";
import { useLanguage } from "@/context/LanguageContext";

interface ProgressData {
    thisWeekTotal: number;
    changePercent: number;
}

export function WeeklyProgress() {
    const { t } = useLanguage();
    const [data, setData] = useState<ProgressData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchProgress = async () => {
            try {
                const res = await apiFetch<any>("/api/dashboard/progress");
                if (res.ok) {
                    setData(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch progress", error);
            } finally {
                setLoading(false);
            }
        };
        fetchProgress();
    }, []);

    if (loading) {
        return <Card className="shadow-sm border-border animate-pulse h-32" />;
    }

    const isUp = (data?.changePercent || 0) >= 0;

    return (
        <Card className="shadow-sm border-border">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{t("dashboard.weeklyProgressTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex items-end gap-2">
                    <span className="text-3xl font-bold text-primary">{data?.thisWeekTotal || 0}</span>
                    <span className="mb-1 text-sm text-muted-foreground">{t("dashboard.weeklyProgressQuestions")}</span>
                </div>
                <div className={`mt-2 text-xs font-medium ${isUp ? 'text-success' : 'text-danger'} flex items-center gap-1`}>
                    <span>{isUp ? '↑' : '↓'} {Math.round(Math.abs(data?.changePercent || 0))}%</span>
                    <span className="text-muted-foreground font-normal">{t("dashboard.weeklyProgressFromLastWeek")}</span>
                </div>
            </CardContent>
        </Card>
    );
}
