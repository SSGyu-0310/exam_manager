import { getExamDetail } from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { ExamQuestionTable } from "@/components/exam/ExamQuestionTable";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ExamDetailPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const data = await getExamDetail(id);
    const exam = data.exam;

    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Exam
            </p>
            <h2 className="text-2xl font-semibold text-foreground">{exam.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {composeExamTitle({
                subject: exam.subject,
                year: exam.year,
                term: exam.term,
              })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant="neutral">{exam.questionCount ?? 0} questions</Badge>
            <Badge variant="success">{exam.classifiedCount ?? 0} classified</Badge>
            <Badge variant="danger">{exam.unclassifiedCount ?? 0} unclassified</Badge>
          </div>
        </div>

        <ExamQuestionTable questions={data.questions} />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load exam.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Exam unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
