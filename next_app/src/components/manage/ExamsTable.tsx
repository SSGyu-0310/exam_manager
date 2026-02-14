"use client";

import Link from "next/link";
import { Pencil, X } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import type { ManageExam } from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { Badge } from "@/components/ui/badge";
import { TableRow } from "@/components/ui/table-row";

type ExamsTableProps = {
  exams: ManageExam[];
  detailBasePath?: string;
  editBasePath?: string;
  showActions?: boolean;
  onDelete?: (examId: number) => void;
};

export function ExamsTable({
  exams,
  detailBasePath = "/manage/exams",
  editBasePath = "/manage/exams",
  onDelete,
}: ExamsTableProps) {
  const { t } = useLanguage();

  const handleDelete = (exam: ManageExam) => {
    const confirmed = window.confirm(
      t("manage.examDeleteConfirm").replace("{title}", exam.title)
    );
    if (confirmed && onDelete) {
      onDelete(exam.id);
    }
  };

  if (!exams.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/70 p-6 text-sm text-muted-foreground">
        {t("manage.noExams")}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/80">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <tr>
            <th className="px-5 py-3">{t("manage.exams")}</th>
            <th className="px-5 py-3">{t("manage.questions")}</th>
            <th className="px-5 py-3">{t("manage.classified")}</th>
            <th className="px-5 py-3">{t("manage.unclassified")}</th>
          </tr>
        </thead>
        <tbody>
          {exams.map((exam) => (
            <TableRow key={exam.id}>
              <td className="px-5 py-4">
                <div className="flex items-center gap-2">
                  <Link
                    href={`${detailBasePath}/${exam.id}`}
                    className="font-semibold text-foreground hover:underline"
                  >
                    {exam.title}
                  </Link>
                  <Link
                    href={`${editBasePath}/${exam.id}/edit`}
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                    title={t("common.edit")}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Link>
                  {onDelete && (
                    <button
                      type="button"
                      onClick={() => handleDelete(exam)}
                      className="rounded p-1 text-muted-foreground hover:bg-danger/10 hover:text-danger transition-colors"
                      title={t("common.delete")}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                {composeExamTitle({
                  subject: exam.subject,
                  year: exam.year,
                  term: exam.term,
                }) && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {composeExamTitle({
                        subject: exam.subject,
                        year: exam.year,
                        term: exam.term,
                      })}
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
            </TableRow>
          ))}
        </tbody>
      </table>
    </div>
  );
}

