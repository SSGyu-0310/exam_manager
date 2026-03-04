import { BookOpen, PenLine, Search, Sigma, Timer } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type PracticeMode = "practice" | "timed";

type ExamOption = {
  id: number;
  title: string;
};

type PracticeStats = {
  total: number;
  objective: number;
  subjective: number;
  multiple?: number;
};

type ExamFilterState = {
  options: ExamOption[];
  selectedIds: number[];
  active: boolean;
  onToggle: (examId: number) => void;
  onApply: () => void;
  onReset?: () => void;
};

type StartCardProps = {
  title?: string;
  questionCount?: number;
  stats?: PracticeStats | null;
  examFilter?: ExamFilterState | null;
  resumeSession?: {
    answeredCount: number;
    totalQuestions: number;
  } | null;
  onResume?: () => void;
  resumeLoading?: boolean;
  mode: PracticeMode;
  onModeChange: (mode: PracticeMode) => void;
  onStart: () => void;
  loading?: boolean;
  error?: string | null;
  validationMessage?: string | null;
};

export function StartCard({
  title,
  questionCount,
  stats,
  examFilter,
  resumeSession,
  onResume,
  resumeLoading,
  mode,
  onModeChange,
  onStart,
  loading,
  error,
  validationMessage,
}: StartCardProps) {
  const hasResumeAction = Boolean(resumeSession && onResume);
  const answeredCount = resumeSession?.answeredCount ?? 0;
  const totalQuestions = resumeSession?.totalQuestions ?? 0;
  const actionBusy = Boolean(loading || resumeLoading);

  return (
    <Card className="w-full max-w-4xl border border-border/70 bg-card/85 shadow-soft backdrop-blur">
      <CardHeader className="space-y-2">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant="outline" className="text-[10px] font-semibold tracking-widest text-primary border-primary/30 bg-primary/5 uppercase">
            문제 풀이
          </Badge>
        </div>
        <CardTitle className="text-2xl font-bold tracking-tight text-foreground">학습 시작하기</CardTitle>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <CardDescription className="text-sm text-muted-foreground/80">
            {title ?? "학습을 시작할 단원을 선택하세요."}
          </CardDescription>
          {typeof questionCount === "number" && (
            <Badge variant="neutral" className="w-fit">
              총 {questionCount}문제
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {stats && (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex flex-col items-center justify-center rounded-2xl border border-border/50 bg-gradient-to-br from-card to-muted/30 p-4 text-center shadow-sm">
                <div className="mb-2 rounded-full bg-primary/10 p-2 text-primary">
                  <Sigma className="h-4 w-4" />
                </div>
                <p className="text-[10px] sm:text-xs uppercase tracking-wider text-muted-foreground font-medium">전체 문제</p>
                <p className="mt-1 text-2xl font-bold text-foreground">{stats.total}</p>
              </div>
              <div className="flex flex-col items-center justify-center rounded-2xl border border-border/50 bg-gradient-to-br from-card to-muted/30 p-4 text-center shadow-sm">
                <div className="mb-2 rounded-full bg-blue-500/10 p-2 text-blue-500">
                  <Search className="h-4 w-4" />
                </div>
                <p className="text-[10px] sm:text-xs uppercase tracking-wider text-muted-foreground font-medium">객관식</p>
                <p className="mt-1 text-2xl font-bold text-foreground">{stats.objective}</p>
              </div>
              <div className="flex flex-col items-center justify-center rounded-2xl border border-border/50 bg-gradient-to-br from-card to-muted/30 p-4 text-center shadow-sm">
                <div className="mb-2 rounded-full bg-purple-500/10 p-2 text-purple-500">
                  <PenLine className="h-4 w-4" />
                </div>
                <p className="text-[10px] sm:text-xs uppercase tracking-wider text-muted-foreground font-medium">주관식/서술형</p>
                <p className="mt-1 text-2xl font-bold text-foreground">{stats.subjective}</p>
              </div>
            </div>
            {stats.multiple && stats.multiple > 0 && (
              <p className="text-xs text-muted-foreground text-right">
                * 다중 응답 객관식: {stats.multiple}개 포함
              </p>
            )}
          </div>
        )}
        {examFilter && examFilter.options.length > 0 && (
          <div className="rounded-2xl border border-border/60 bg-muted/30 p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-semibold text-foreground">기출문제 필터</p>
              <div className="flex flex-wrap items-center gap-2">
                {examFilter.onReset && (
                  <Button size="sm" variant="ghost" onClick={examFilter.onReset} className="h-8 text-xs">
                    초기화
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={examFilter.onApply} className="h-8 text-xs bg-card">
                  적용
                </Button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {examFilter.options.map((exam) => {
                const checked = examFilter.selectedIds.includes(exam.id);
                return (
                  <button
                    key={exam.id}
                    type="button"
                    onClick={() => examFilter.onToggle(exam.id)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-200 border ${checked
                      ? "border-primary bg-primary text-primary-foreground shadow-sm"
                      : "border-border/60 bg-card text-muted-foreground hover:border-primary/50 hover:bg-muted"
                      }`}
                  >
                    {exam.title}
                  </button>
                );
              })}
            </div>
            {examFilter.active && stats && stats.total === 0 && (
              <p className="mt-3 text-xs font-medium text-danger">선택한 필터에 해당하는 문제가 없습니다.</p>
            )}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          {(
            [
              {
                value: "practice",
                title: "일반 모드 (자율 학습)",
                description: "시간 제한 없이 자유롭게 문제를 풀고 즉시 복습합니다.",
                icon: BookOpen,
                activeColor: "text-blue-500",
                activeBg: "bg-blue-500/10",
                activeBorder: "border-blue-500/50",
              },
              {
                value: "timed",
                title: "실전 모드 (타이머)",
                description: "실제 시험처럼 제한 시간 내에 문제를 푸는 모드입니다.",
                icon: Timer,
                activeColor: "text-orange-500",
                activeBg: "bg-orange-500/10",
                activeBorder: "border-orange-500/50",
              },
            ] as const
          ).map((option) => {
            const active = mode === option.value;
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onModeChange(option.value)}
                className={`relative overflow-hidden rounded-2xl border p-5 text-left transition-all duration-200 ${active
                  ? `${option.activeBorder} ${option.activeBg} shadow-sm ring-1 ring-${option.activeBorder.split("-")[1]}-500/20`
                  : "border-border/70 bg-card hover:border-border/100 hover:bg-muted/30"
                  }`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className={`rounded-xl p-2 ${active ? `${option.activeBg} ${option.activeColor}` : "bg-muted text-muted-foreground"}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <p className={`text-base font-bold ${active ? "text-foreground" : "text-foreground/80"}`}>
                    {option.title}
                  </p>
                </div>
                <p className={`text-xs leading-relaxed ${active ? "text-foreground/70" : "text-muted-foreground"}`}>
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>
        {validationMessage && (
          <div className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
            {validationMessage}
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}
        {hasResumeAction && (
          <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
            <p className="font-semibold text-foreground">진행 중인 학습이 있습니다.</p>
            <p className="mt-1 text-xs text-muted-foreground">
              진행도 {answeredCount}/{totalQuestions}
            </p>
          </div>
        )}
        {hasResumeAction ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Button
              onClick={onResume}
              disabled={actionBusy}
              className="w-full rounded-2xl py-6 text-base font-bold shadow-sm transition-transform active:scale-[0.98]"
            >
              {resumeLoading ? (
                <div className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>불러오는 중...</span>
                </div>
              ) : (
                "이어하기"
              )}
            </Button>
            <Button
              onClick={onStart}
              disabled={actionBusy}
              variant="outline"
              className="w-full rounded-2xl py-6 text-base font-bold shadow-sm transition-transform active:scale-[0.98]"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>준비 중...</span>
                </div>
              ) : (
                "새로 시작"
              )}
            </Button>
          </div>
        ) : (
          <Button
            onClick={onStart}
            disabled={actionBusy}
            className="w-full rounded-2xl py-6 text-base font-bold shadow-sm transition-transform active:scale-[0.98]"
          >
            {loading ? (
              <div className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>준비 중...</span>
              </div>
            ) : (
              "학습 시작"
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
