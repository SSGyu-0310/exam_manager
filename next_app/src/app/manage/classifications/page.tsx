"use client";

import { UnclassifiedQueue } from "@/components/exam/UnclassifiedQueue";
import { useLanguage } from "@/context/LanguageContext";

export default function ClassificationsPage() {
    const { t } = useLanguage();

    return (
        <div className="space-y-6">
            <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                    {t("classifications.pageLabel")}
                </p>
                <h2 className="text-2xl font-semibold text-foreground">
                    {t("classifications.pageTitle")}
                </h2>
            </div>
            <UnclassifiedQueue />
        </div>
    );
}
