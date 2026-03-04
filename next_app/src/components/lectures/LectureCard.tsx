import Link from "next/link";
import { useState } from "react";
import { ListChecks } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LectureStudyMeta, NormalizedLecture } from "@/components/lectures/types";

type LectureCardProps = {
  lecture: NormalizedLecture;
  questionCount?: number | null;
  studyMeta?: LectureStudyMeta | null;
};

const DAY_MS = 24 * 60 * 60 * 1000;

const toCompactDate = (value: Date) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}.${month}.${day}`;
};

export function LectureCard({ lecture, questionCount, studyMeta }: LectureCardProps) {
  const { t, language } = useLanguage();
  const [mountedAt] = useState(() => Date.now());
  const resolvedCount =
    typeof questionCount === "number"
      ? questionCount
      : typeof lecture.questionCount === "number"
        ? lecture.questionCount
        : null;
  const countLabel = typeof resolvedCount === "number" ? `${resolvedCount}` : "--";
  const lectureId = lecture.id;
  const startHref =
    lectureId !== null && lectureId !== undefined
      ? `/practice/start?lectureId=${encodeURIComponent(String(lectureId))}`
      : null;
  const resumeHref = studyMeta?.inProgressSessionId
    ? `/practice/session/${encodeURIComponent(studyMeta.inProgressSessionId)}`
    : null;
  const actionHref = resumeHref ?? startHref;
  const actionLabel = resumeHref ? t("learn.resumeStudy") : t("learn.study");
  const progressLabel =
    resumeHref && studyMeta
      ? t("learn.progressCompact")
        .replace("{answered}", String(studyMeta.answeredCount))
        .replace("{total}", String(studyMeta.totalQuestions))
      : null;

  const studyBadge = (() => {
    const lastStudiedAt = studyMeta?.lastStudiedAt;
    if (!lastStudiedAt) {
      return {
        label: t("learn.unstudied"),
        toneClass: "border-danger/30 bg-danger/10 text-danger",
      };
    }

    const studiedDate = new Date(lastStudiedAt);
    const studiedTime = studiedDate.getTime();
    if (!Number.isFinite(studiedTime)) {
      return {
        label: t("learn.recentStudy"),
        toneClass: "border-success/30 bg-success/15 text-success",
      };
    }

    const diffMs = mountedAt - studiedTime;
    const diffDays = Math.floor(diffMs / DAY_MS);
    if (diffDays >= 0 && diffDays < 7) {
      if (diffDays === 0) {
        return {
          label: t("learn.today"),
          toneClass: "border-success/50 bg-success/25 text-success",
        };
      }
      if (diffDays <= 2) {
        return {
          label: t("learn.daysAgo").replace("{days}", String(diffDays)),
          toneClass: "border-success/40 bg-success/20 text-success",
        };
      }
      return {
        label: t("learn.daysAgo").replace("{days}", String(diffDays)),
        toneClass: "border-success/35 bg-success/15 text-success",
      };
    }

    const label =
      language === "ko"
        ? toCompactDate(studiedDate)
        : new Intl.DateTimeFormat("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        }).format(studiedDate);

    return {
      label,
      toneClass: "border-success/25 bg-success/10 text-success/80",
    };
  })();

  return (
    <Card className="group flex h-full flex-col bg-card/90 backdrop-blur-sm transition hover:-translate-y-0.5 hover:shadow-float">
      <CardHeader className="gap-3 pb-3">
        <div className="flex items-center justify-between gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${studyBadge.toneClass}`}
          >
            {studyBadge.label}
          </span>
          {progressLabel && (
            <span className="text-xs font-medium text-primary">{progressLabel}</span>
          )}
        </div>
        <CardTitle className="line-clamp-2 min-h-12 text-lg leading-snug text-foreground">
          {lecture.title ?? t("learn.untitledLecture")}
        </CardTitle>
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between gap-2 pt-0">
        <div className="flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
          <ListChecks className="h-3.5 w-3.5" />
          <span className="text-sm font-semibold text-foreground">{countLabel}</span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {t("learn.questions")}
          </span>
        </div>
        {actionHref ? (
          <Button size="sm" className="h-9 rounded-full px-4" asChild>
            <Link href={actionHref}>{actionLabel}</Link>
          </Button>
        ) : (
          <Button size="sm" className="h-9 rounded-full px-4" disabled>
            {actionLabel}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
