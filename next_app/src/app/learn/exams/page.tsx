"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, ListChecks } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getExams, type ManageExam } from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { useLanguage } from "@/context/LanguageContext";

export default function ExamsPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [exams, setExams] = useState<ManageExam[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchExams = async () => {
      try {
        const data = await getExams();
        setExams(data);
      } catch (error) {
        console.error("Failed to fetch exams", error);
      } finally {
        setLoading(false);
      }
    };
    fetchExams();
  }, []);

  const handleStart = (exam: ManageExam) => {
    const sessionId = `exam-${encodeURIComponent(String(exam.id))}`;
    const examTitle = composeExamTitle(exam) || exam.title;
    const sessionPayload = {
      examId: String(exam.id),
      examTitle,
      mode: "practice",
      fallback: true,
      createdAt: Date.now(),
      source: "exam-fallback",
    };
    if (typeof window !== "undefined") {
      sessionStorage.setItem(
        `practice:session:${sessionId}`,
        JSON.stringify(sessionPayload)
      );
    }
    router.push(`/practice/session/${sessionId}`);
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {t("learn.mockExams")}
        </h1>
        <p className="text-muted-foreground">{t("learn.mockExamsDesc")}</p>
      </div>

      <Card className="border-border bg-card/60">
        <CardContent className="flex items-center justify-between gap-3 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-primary/10 p-2 text-primary">
              <ListChecks className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                {t("learn.examBasedComingSoon")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("learn.underConstruction")}
              </p>
            </div>
          </div>
          <Badge variant="neutral">{t("learn.underConstruction")}</Badge>
        </CardContent>
      </Card>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <Card key={item} className="h-32 animate-pulse border-border bg-muted" />
          ))}
        </div>
      ) : exams.length === 0 ? (
        <Card className="border-border bg-card/70">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <div className="space-y-1">
              <p className="text-base font-semibold text-foreground">
                {t("learn.examBasedEmpty")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("learn.examBasedEmptyDesc")}
              </p>
            </div>
            <Link href="/manage/exams">
              <Button variant="outline">{t("learn.examBasedManage")}</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {exams.map((exam) => {
            const questionCount = exam.questionCount ?? 0;
            return (
              <Card key={exam.id} className="border-border bg-card/80 shadow-soft">
                <CardContent className="flex h-full flex-col justify-between gap-4 py-5">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="neutral">
                        {questionCount} {t("learn.questions")}
                      </Badge>
                      <Badge variant="outline">{t("learn.underConstruction")}</Badge>
                    </div>
                  <p className="text-lg font-semibold text-foreground">
                    {composeExamTitle(exam) || exam.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {exam.subject ?? t("common.unknown")}
                  </p>
                  </div>
                  <Button onClick={() => handleStart(exam)} disabled={questionCount === 0}>
                    {t("learn.examBasedStart")}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
