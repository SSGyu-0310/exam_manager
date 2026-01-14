import { getManageSummary } from "@/lib/api/manage";
import { StatCard } from "@/components/manage/StatCard";
import { ExamsTable } from "@/components/manage/ExamsTable";
import { Card, CardContent } from "@/components/ui/card";

export default async function ManageDashboardPage() {
  try {
    const summary = await getManageSummary();

    return (
      <div className="space-y-8">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Blocks" value={summary.counts.blocks} />
          <StatCard label="Lectures" value={summary.counts.lectures} />
          <StatCard label="Exams" value={summary.counts.exams} />
          <StatCard label="Questions" value={summary.counts.questions} />
          <StatCard label="Unclassified" value={summary.counts.unclassified} />
        </div>

        <section className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Recent exams
            </p>
            <h2 className="text-xl font-semibold text-foreground">Latest uploads</h2>
          </div>
          <ExamsTable exams={summary.recentExams} />
        </section>
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load dashboard.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Dashboard unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
