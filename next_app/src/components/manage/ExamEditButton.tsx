"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/LanguageContext";

type ExamEditButtonProps = {
  examId: number | string;
};

export function ExamEditButton({ examId }: ExamEditButtonProps) {
  const { t } = useLanguage();

  return (
    <Button size="sm" asChild>
      <Link href={`/manage/exams/${examId}/edit`}>{t("manage.editExam")}</Link>
    </Button>
  );
}
