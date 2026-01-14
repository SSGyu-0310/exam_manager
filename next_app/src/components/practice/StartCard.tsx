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
  mode,
  onModeChange,
  onStart,
  loading,
  error,
  validationMessage,
}: StartCardProps) {
  return (
    <Card className="w-full max-w-2xl border border-border/70 bg-card/85 shadow-soft backdrop-blur">
      <CardHeader className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Practice Session
        </p>
        <CardTitle className="text-2xl text-foreground">Start your session</CardTitle>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardDescription className="text-sm text-muted-foreground">
            {title ?? "Pick a lecture to begin your practice run."}
          </CardDescription>
          {typeof questionCount === "number" && (
            <Badge variant="neutral" className="w-fit">
              {questionCount} questions available
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {stats && (
          <div className="space-y-2">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/60 bg-muted/60 p-3 text-center">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Total
                </p>
                <p className="text-lg font-semibold text-foreground">{stats.total}</p>
              </div>
              <div className="rounded-2xl border border-border/60 bg-muted/60 p-3 text-center">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Objective
                </p>
                <p className="text-lg font-semibold text-foreground">
                  {stats.objective}
                </p>
              </div>
              <div className="rounded-2xl border border-border/60 bg-muted/60 p-3 text-center">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Subjective
                </p>
                <p className="text-lg font-semibold text-foreground">
                  {stats.subjective}
                </p>
              </div>
            </div>
            {stats.multiple && stats.multiple > 0 && (
              <p className="text-xs text-muted-foreground">
                Multiple response: {stats.multiple}
              </p>
            )}
          </div>
        )}
        {examFilter && examFilter.options.length > 0 && (
          <div className="rounded-2xl border border-border/60 bg-muted/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-semibold text-foreground">Exam filter</p>
              <div className="flex flex-wrap items-center gap-2">
                {examFilter.onReset && (
                  <Button size="sm" variant="ghost" onClick={examFilter.onReset}>
                    Reset
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={examFilter.onApply}>
                  Apply
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              {examFilter.options.map((exam) => {
                const checked = examFilter.selectedIds.includes(exam.id);
                return (
                  <label key={exam.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => examFilter.onToggle(exam.id)}
                      className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                    />
                    <span>{exam.title}</span>
                  </label>
                );
              })}
            </div>
            {examFilter.active && stats && stats.total === 0 && (
              <p className="mt-2 text-xs text-danger">No questions in this filter.</p>
            )}
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              {
                value: "practice",
                title: "Practice",
                description: "Review questions at your own pace.",
              },
              {
                value: "timed",
                title: "Timed",
                description: "Simulate test conditions with a timer.",
              },
            ] as const
          ).map((option) => {
            const active = mode === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onModeChange(option.value)}
                className={`rounded-2xl border p-4 text-left transition ${
                  active
                    ? "border-primary bg-primary text-primary-foreground shadow-soft"
                    : "border-border/70 bg-card text-foreground hover:border-border/80"
                }`}
              >
                <p className="text-base font-semibold">{option.title}</p>
                <p
                  className={`text-xs ${
                    active ? "text-primary-foreground/80" : "text-muted-foreground"
                  }`}
                >
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
        <Button
          onClick={onStart}
          disabled={loading}
          className="w-full rounded-full py-6 text-base font-semibold"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Starting...
            </>
          ) : (
            "Start exam"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
