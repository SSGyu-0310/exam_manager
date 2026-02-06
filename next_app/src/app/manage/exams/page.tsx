import { getExams, type ManageExam } from "@/lib/api/manage";
import { ExamLibrary } from "@/components/manage/ExamLibrary";

export default async function ManageExamsPage() {
  let exams: ManageExam[] = [];
  let errorMessage: string | null = null;

  try {
    exams = await getExams();
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : "Unable to load exams.";
  }

  return <ExamLibrary initialExams={exams} initialError={errorMessage} />;
}
