import Link from "next/link";

import { getExams } from "@/lib/api/manage";
import { ExamsTable } from "@/components/manage/ExamsTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default async function ManageExamsPage() {
  try {
    const exams = await getExams();
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Exams
            </p>
            <h2 className="text-2xl font-semibold text-foreground">Exam library</h2>
          </div>
          <Button asChild>
            <Link href="/manage/exams/new">New exam</Link>
          </Button>
        </div>
        <ExamsTable exams={exams} showActions />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load exams.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Exams unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
