import { Card, CardContent } from "@/components/ui/card";

type ResultSummaryProps = {
  total: number;
  answered: number;
  correct: number;
  labels: {
    accuracy: string;
    correct: string;
    answered: string;
    total: string;
  };
};

export function ResultSummary({
  total,
  answered,
  correct,
  labels,
}: ResultSummaryProps) {
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-1 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {labels.accuracy}
          </p>
          <p className="text-2xl font-semibold text-foreground">{accuracy}%</p>
        </CardContent>
      </Card>
      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-1 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {labels.correct}
          </p>
          <p className="text-2xl font-semibold text-foreground">{correct}</p>
        </CardContent>
      </Card>
      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-1 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {labels.answered}
          </p>
          <p className="text-2xl font-semibold text-foreground">{answered}</p>
        </CardContent>
      </Card>
      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-1 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {labels.total}
          </p>
          <p className="text-2xl font-semibold text-foreground">{total}</p>
        </CardContent>
      </Card>
    </div>
  );
}
