import Link from "next/link";
import { BookOpen, ListChecks } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { NormalizedLecture } from "@/components/lectures/types";

type LectureCardProps = {
  lecture: NormalizedLecture;
  questionCount?: number | null;
};

export function LectureCard({ lecture, questionCount }: LectureCardProps) {
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

  return (
    <Card className="group flex h-full flex-col bg-card/90 backdrop-blur-sm transition hover:-translate-y-0.5 hover:shadow-float">
      <CardHeader className="gap-4">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            <span>Lecture</span>
          </div>
          <Badge variant="neutral" className="px-2.5 py-1 text-[10px] tracking-[0.25em]">
            Ready
          </Badge>
        </div>
        <CardTitle className="text-lg leading-snug text-foreground">
          {lecture.title ?? "Untitled Lecture"}
        </CardTitle>
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 rounded-full bg-muted px-3 py-1 text-sm text-muted-foreground">
          <ListChecks className="h-4 w-4" />
          <span className="text-base font-semibold text-foreground">{countLabel}</span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Questions
          </span>
        </div>
        {startHref ? (
          <Button size="sm" className="rounded-full px-4" asChild>
            <Link href={startHref}>Study</Link>
          </Button>
        ) : (
          <Button size="sm" className="rounded-full px-4" disabled>
            Study
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
