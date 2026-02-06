export type ExamTitleParts = {
  subject?: string | null;
  year?: string | number | null;
  term?: string | null;
};

export function composeExamTitle({ subject, year, term }: ExamTitleParts) {
  const pieces: string[] = [];
  const subjectText = subject?.trim();
  if (subjectText) {
    pieces.push(subjectText);
  }
  const yearValue = typeof year === "number" ? year : year ? Number(year) : null;
  if (yearValue) {
    pieces.push(String(yearValue));
  }
  const termText = term?.trim();
  if (termText) {
    pieces.push(termText);
  }
  return pieces.join("-").trim();
}
