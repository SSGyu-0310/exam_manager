"use client";

import { FileText } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

type ExamEditHeaderProps = {
  examTitle?: string;
  questionCount?: number;
};

export function ExamEditHeader({ examTitle, questionCount }: ExamEditHeaderProps) {
  const { t } = useLanguage();

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          {t("manage.exams")}
        </p>
        <h2 className="text-2xl font-semibold text-foreground">{t("manage.editExam")}</h2>
      </div>
      {examTitle && (
        <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-muted/30 px-4 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <p className="font-medium text-foreground">{examTitle}</p>
            {questionCount !== undefined && (
              <p className="text-xs text-muted-foreground">
                {t("manage.questions")}: {questionCount}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

