"use client";

import { useEffect, useState } from "react";
import { BookOpen, RotateCcw } from "lucide-react";
import Link from "next/link";

import { apiFetch } from "@/lib/http";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { useLanguage } from "@/context/LanguageContext";

interface SummaryData {
    counts: {
        blocks: number;
        lectures: number;
        exams: number;
        questions: number;
        unclassified: number;
    };
    recentExams: any[];
}

export function OverviewCards() {
    const { t } = useLanguage();
    const [summary, setSummary] = useState<SummaryData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const data = await apiFetch<any>("/api/manage/summary");
                if (data.ok) {
                    setSummary(data.data);
                }
            } catch (error) {
                console.error("Failed to fetch summary", error);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();
    }, []);

    if (loading) {
        return <div className="grid gap-6 md:grid-cols-2 lg:gap-8 animate-pulse">
            <div className="h-64 rounded-xl bg-muted" />
            <div className="h-64 rounded-xl bg-muted" />
        </div>;
    }

    return (
        <div className="grid gap-6 md:grid-cols-2 lg:gap-8">
            <Card className="relative overflow-hidden border border-border bg-card shadow-sm transition-all hover:shadow-md">
                <CardHeader className="pb-4">
                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <BookOpen className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-xl text-foreground">{t("dashboard.overviewResumeTitle")}</CardTitle>
                    <CardDescription className="text-muted-foreground">
                        {t("dashboard.overviewResumeDesc")}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="rounded-lg border border-border bg-muted/30 p-3">
                            <p className="text-sm font-medium text-muted-foreground">{t("dashboard.overviewTotalQuestions")}</p>
                            <p className="text-2xl font-bold text-foreground">{summary?.counts.questions || 0}</p>
                        </div>
                        <div className="rounded-lg border border-border bg-muted/30 p-3">
                            <p className="text-sm font-medium text-muted-foreground">{t("dashboard.overviewLectures")}</p>
                            <p className="text-2xl font-bold text-foreground">{summary?.counts.lectures || 0}</p>
                        </div>
                    </div>
                </CardContent>
                <CardFooter>
                    <Link href="/learn/practice" className="w-full">
                        <Button className="w-full group bg-primary text-primary-foreground hover:bg-primary/90">
                            {t("dashboard.overviewStartPractice")}
                        </Button>
                    </Link>
                </CardFooter>
            </Card>

            <Card className="relative overflow-hidden border border-border bg-card shadow-sm transition-all hover:shadow-md">
                <CardHeader className="pb-4">
                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10 text-warning">
                        <RotateCcw className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-xl text-foreground">{t("dashboard.overviewUnclassifiedTitle")}</CardTitle>
                    <CardDescription className="text-muted-foreground">
                        {t("dashboard.overviewUnclassifiedDesc")}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-6 py-4">
                        <div className="text-center">
                            <p className="text-3xl font-bold text-warning">{summary?.counts.unclassified || 0}</p>
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("dashboard.overviewToClassify")}</p>
                        </div>
                        {summary?.counts.unclassified && summary.counts.unclassified > 0 ? (
                            <div className="ml-auto">
                                <Badge variant="danger" className="animate-pulse">{t("dashboard.overviewActionRequired")}</Badge>
                            </div>
                        ) : null}
                    </div>
                </CardContent>
                <CardFooter className="mt-auto">
                    <Link href="/manage/unclassified" className="w-full">
                        <Button variant="outline" className="w-full border-border hover:bg-muted text-foreground">
                            {t("dashboard.overviewGoToClassification")}
                        </Button>
                    </Link>
                </CardFooter>
            </Card>
        </div>
    );
}
