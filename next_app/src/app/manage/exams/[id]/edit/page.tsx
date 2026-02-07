import { getExamDetail } from "@/lib/api/manage";
import { ExamForm } from "@/components/manage/ExamForm";
import { ExamEditHeader } from "@/components/manage/ExamEditHeader";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ManageExamEditPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const data = await getExamDetail(id);
    return (
      <div className="space-y-6">
        <ExamEditHeader
          examTitle={data.exam.title}
          questionCount={data.exam.questionCount ?? data.questions.length}
        />
        <ExamForm initial={data.exam} />
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
