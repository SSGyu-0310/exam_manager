import Link from "next/link";

import type { ManageExam } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { TableRow } from "@/components/ui/table-row";

type ExamsTableProps = {
  exams: ManageExam[];
  detailBasePath?: string;
  editBasePath?: string;
  showActions?: boolean;
};

export function ExamsTable({
  exams,
  detailBasePath = "/manage/exams",
  editBasePath = "/manage/exams",
  showActions = false,
}: ExamsTableProps) {
  if (!exams.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/70 p-6 text-sm text-muted-foreground">
        No exams found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/80">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <tr>
            <th className="px-5 py-3">Exam</th>
            <th className="px-5 py-3">Questions</th>
            <th className="px-5 py-3">Classified</th>
            <th className="px-5 py-3">Unclassified</th>
            <th className="px-5 py-3">Date</th>
            {showActions && <th className="px-5 py-3">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {exams.map((exam) => (
            <TableRow key={exam.id}>
              <td className="px-5 py-4">
                <Link
                  href={`${detailBasePath}/${exam.id}`}
                  className="font-semibold text-foreground hover:underline"
                >
                  {exam.title}
                </Link>
                {(exam.subject || exam.term) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[exam.subject, exam.term].filter(Boolean).join(" · ")}
                  </p>
                )}
              </td>
              <td className="px-5 py-4">
                <Badge variant="neutral">{exam.questionCount ?? 0}</Badge>
              </td>
              <td className="px-5 py-4">
                <Badge variant="success">{exam.classifiedCount ?? 0}</Badge>
              </td>
              <td className="px-5 py-4">
                <Badge variant="danger">{exam.unclassifiedCount ?? 0}</Badge>
              </td>
              <td className="px-5 py-4 text-muted-foreground">
                {exam.examDate ?? "—"}
              </td>
              {showActions && (
                <td className="px-5 py-4">
                  <Link
                    href={`${editBasePath}/${exam.id}/edit`}
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-foreground/80 hover:underline"
                  >
                    Edit
                  </Link>
                </td>
              )}
            </TableRow>
          ))}
        </tbody>
      </table>
    </div>
  );
}
