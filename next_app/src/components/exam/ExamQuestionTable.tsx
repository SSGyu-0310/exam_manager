import Link from "next/link";

import type { ManageQuestion } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { TableRow } from "@/components/ui/table-row";

type ExamQuestionTableProps = {
  questions: ManageQuestion[];
  showActions?: boolean;
  questionDetailBasePath?: string;
  editBasePath?: string;
};

const typeLabel = (value?: string | null) => {
  if (!value) return "미지정";
  if (value === "multiple_choice") return "객관식";
  if (value === "multiple_response") return "복수정답";
  if (value === "short_answer") return "주관식";
  return value;
};

export function ExamQuestionTable({
  questions,
  showActions = false,
  questionDetailBasePath = "/manage/questions",
  editBasePath = "/manage/questions",
}: ExamQuestionTableProps) {
  if (!questions.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/70 p-6 text-sm text-muted-foreground">
        문항이 없습니다.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/80">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <tr>
            <th className="px-5 py-3">번호</th>
            <th className="px-5 py-3">유형</th>
            <th className="px-5 py-3">강의</th>
            <th className="px-5 py-3">상태</th>
            <th className="px-5 py-3">이미지</th>
            <th className="px-5 py-3">보기</th>
            {showActions && <th className="px-5 py-3">관리</th>}
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
                  <span className="text-muted-foreground">미분류</span>
                )}
              </td>
              <td className="px-5 py-4">
                {question.isClassified ? (
                  <Badge variant="success">분류됨</Badge>
                ) : (
                  <Badge variant="danger">미분류</Badge>
                )}
              </td>
              <td className="px-5 py-4 text-muted-foreground">
                {question.hasImage ? "있음" : "없음"}
              </td>
              <td className="px-5 py-4">
                <Link
                  href={`${questionDetailBasePath}/${question.id}`}
                  className="text-xs font-semibold uppercase tracking-[0.2em] text-foreground/80 hover:underline"
                >
                  보기
                </Link>
              </td>
              {showActions && (
                <td className="px-5 py-4">
                  <Link
                    href={`${editBasePath}/${question.id}/edit`}
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-foreground/80 hover:underline"
                  >
                    수정
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
