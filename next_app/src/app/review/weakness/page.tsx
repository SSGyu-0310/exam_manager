"use client";

import { useEffect, useState } from "react";
import { TrendingDown, Target, AlertTriangle, ShieldCheck } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import { apiFetch } from "@/lib/http";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface WeaknessData {
    blockId: number;
    blockName: string;
    accuracy: number;
    totalAnswered: number;
}

export default function ReviewWeaknessPage() {
    const { t } = useLanguage();
    const [data, setData] = useState<WeaknessData[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await apiFetch<any>("/api/review/weakness");
                if (res.ok) {
                    setData(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch weakness data", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const getStatusIcon = (accuracy: number) => {
        if (accuracy < 60) return <AlertTriangle className="h-5 w-5 text-danger" />;
        if (accuracy < 80) return <TrendingDown className="h-5 w-5 text-warning" />;
        return <ShieldCheck className="h-5 w-5 text-success" />;
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("review.weakness")}</h1>
                <p className="text-muted-foreground">{t("review.weaknessDesc")}</p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {loading ? (
                    [1, 2, 3, 4].map(i => <Card key={i} className="h-40 animate-pulse bg-muted" />)
                ) : data.length === 0 ? (
                    <div className="col-span-full py-20 text-center">
                        <Target className="h-12 w-12 text-muted-foreground/30 mx-auto mb-4" />
                        <p className="text-lg font-medium">{t("review.notEnoughData")}</p>
                        <p className="text-sm text-muted-foreground">{t("review.notEnoughDataDesc")}</p>
                    </div>
                ) : (
                    data.map((item) => (
                        <Card key={item.blockId} className="border-border bg-card shadow-sm hover:shadow-md transition-shadow">
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-lg font-semibold">{item.blockName}</CardTitle>
                                    {getStatusIcon(item.accuracy)}
                                </div>
                                <CardDescription>{item.totalAnswered} {t("review.questionsAnswered")}</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-muted-foreground font-medium">{t("review.accuracy")}</span>
                                        <span className={`font-bold ${item.accuracy < 60 ? 'text-danger' : item.accuracy < 80 ? 'text-warning' : 'text-success'}`}>
                                            {item.accuracy}%
                                        </span>
                                    </div>
                                    <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                        <div
                                            className={`h-full transition-all duration-1000 ${item.accuracy < 60 ? 'bg-danger' : item.accuracy < 80 ? 'bg-warning' : 'bg-success'
                                                }`}
                                            style={{ width: `${item.accuracy}%` }}
                                        />
                                    </div>
                                    <p className="text-[11px] text-muted-foreground italic">
                                        {item.accuracy < 60 ? t("review.intensiveReview") : item.accuracy < 80 ? t("review.steadyProgress") : t("review.strongUnderstanding")}
                                    </p>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>
        </div>
    );
}

