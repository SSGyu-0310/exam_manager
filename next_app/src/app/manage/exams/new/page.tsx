import { ExamForm } from "@/components/manage/ExamForm";

export default function ManageExamCreatePage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Exams
        </p>
        <h2 className="text-2xl font-semibold text-foreground">New exam</h2>
      </div>
      <ExamForm />
    </div>
  );
}
