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
              시험지
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
            <Badge variant="neutral">전체 {exam.questionCount ?? 0}문항</Badge>
            <Badge variant="success">분류 {exam.classifiedCount ?? 0}문항</Badge>
            <Badge variant="danger">미분류 {exam.unclassifiedCount ?? 0}문항</Badge>
          </div>
        </div>

        <ExamQuestionTable questions={data.questions} questionDetailBasePath="/manage/questions" />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "시험지 정보를 불러오지 못했습니다.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">시험지 정보를 불러올 수 없습니다</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
