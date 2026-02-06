"use client";

import { Sparkles, Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";

export default function RecommendedPage() {
    const { t } = useLanguage();

    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6">
            <div className="p-4 rounded-full bg-ai/10 text-ai">
                <Sparkles className="h-12 w-12" />
            </div>
            <div className="text-center space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("learn.aiRecommendations")}</h1>
                <p className="text-muted-foreground max-w-md">
                    {t("learn.aiRecommendationsDesc")}
                </p>
            </div>
            <Card className="border-border bg-card/50 max-w-sm">
                <CardContent className="pt-6 flex items-center gap-3">
                    <Construction className="h-5 w-5 text-warning" />
                    <p className="text-sm font-medium">{t("learn.underConstruction")}</p>
                </CardContent>
            </Card>
            <Link href="/learn/practice">
                <Button variant="outline">{t("learn.backToPractice")}</Button>
            </Link>
        </div>
    );
}

