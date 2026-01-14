import type { ManageQuestion } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { TableRow } from "@/components/ui/table-row";

type ExamQuestionTableProps = {
  questions: ManageQuestion[];
  showActions?: boolean;
};

const typeLabel = (value?: string | null) => {
  if (!value) return "Unknown";
  if (value === "multiple_choice") return "MCQ";
  if (value === "multiple_response") return "MRQ";
  if (value === "short_answer") return "Short";
  return value;
};

export function ExamQuestionTable({ questions, showActions = false }: ExamQuestionTableProps) {
  if (!questions.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/70 p-6 text-sm text-muted-foreground">
        No questions found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/80">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <tr>
            <th className="px-5 py-3">No.</th>
            <th className="px-5 py-3">Type</th>
            <th className="px-5 py-3">Lecture</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3">Image</th>
            {showActions && <th className="px-5 py-3">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {questions.map((question) => (
            <TableRow key={question.id}>
              <td className="px-5 py-4 font-semibold text-foreground">
                {question.questionNumber}
              </td>
              <td className="px-5 py-4 text-muted-foreground">{typeLabel(question.type)}</td>
              <td className="px-5 py-4">
                {question.lectureTitle ? (
                  <span className="text-foreground">{question.lectureTitle}</span>
                ) : (
                  <span className="text-muted-foreground">Unclassified</span>
                )}
              </td>
              <td className="px-5 py-4">
                {question.isClassified ? (
                  <Badge variant="success">Classified</Badge>
                ) : (
                  <Badge variant="danger">Unclassified</Badge>
                )}
              </td>
              <td className="px-5 py-4 text-muted-foreground">
                {question.hasImage ? "Yes" : "No"}
              </td>
              {showActions && (
                <td className="px-5 py-4">
                  <a
                    href={`/manage/questions/${question.id}/edit`}
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-foreground/80 hover:underline"
                  >
                    Edit
                  </a>
                </td>
              )}
            </TableRow>
          ))}
        </tbody>
      </table>
    </div>
  );
}
