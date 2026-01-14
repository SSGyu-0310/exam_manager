import { getLectures, getQuestionDetail } from "@/lib/api/manage";
import { QuestionEditor } from "@/components/manage/QuestionEditor";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ManageQuestionEditPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const [question, lectures] = await Promise.all([
      getQuestionDetail(id),
      getLectures(),
    ]);

    return (
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Question edit
          </p>
          <h2 className="text-2xl font-semibold text-foreground">
            Q{question.questionNumber} · {question.examTitle ?? "Exam"}
          </h2>
        </div>
        <QuestionEditor question={question} lectures={lectures} />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load question.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Question unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
