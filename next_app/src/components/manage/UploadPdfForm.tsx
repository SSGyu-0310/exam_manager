"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getSubjects, uploadPdf, type UploadPdfResult } from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useLanguage } from "@/context/LanguageContext";

type UploadPdfFormProps = {
  onUploaded?: (result: UploadPdfResult) => void;
};

export function UploadPdfForm({ onUploaded }: UploadPdfFormProps) {
  const { t } = useLanguage();
  const [file, setFile] = useState<File | null>(null);
  const [subjectSelect, setSubjectSelect] = useState("");
  const [subjectCustom, setSubjectCustom] = useState("");
  const [year, setYear] = useState("");
  const [termPreset, setTermPreset] = useState("");
  const [termCustom, setTermCustom] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    examId: number;
    questionCount: number;
    choiceCount: number;
  } | null>(null);

  const [subjects, setSubjects] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    getSubjects()
      .then((data) => {
        if (cancelled) return;
        setSubjects(data.map((subject) => subject.name));
      })
      .catch(() => {
        if (!cancelled) setSubjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const years = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const list: string[] = [];
    for (let y = currentYear + 1; y >= 2000; y -= 1) {
      list.push(String(y));
    }
    return list;
  }, []);

  const resolvedSubject =
    subjectSelect === "__custom" ? subjectCustom.trim() : subjectSelect;
  const resolvedTerm = termPreset === "__custom" ? termCustom.trim() : termPreset;
  const computedTitle = useMemo(
    () =>
      composeExamTitle({
        subject: resolvedSubject,
        year,
        term: resolvedTerm,
      }),
    [resolvedSubject, resolvedTerm, year]
  );

  const handleSubmit = async () => {
    if (!file) {
      setError(t("manage.uploadForm.selectPdfError"));
      return;
    }
    if (!resolvedSubject || !year.trim() || !resolvedTerm) {
      setError(t("manage.uploadForm.missingFieldsError"));
      return;
    }
    if (!computedTitle) {
      setError(t("manage.uploadForm.titleGenerateError"));
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("pdf_file", file);
    formData.append("title", computedTitle);
    if (resolvedSubject) formData.append("subject", resolvedSubject);
    if (year.trim()) formData.append("year", year.trim());
    if (resolvedTerm) formData.append("term", resolvedTerm);

    try {
      const data = await uploadPdf(formData);
      setResult(data);
      onUploaded?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.uploadForm.uploadFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.uploadForm.pdfFile")}
          </label>
          <Input
            type="file"
            accept="application/pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.uploadForm.subject")}
          </label>
          <Select
            value={subjectSelect}
            onChange={(event) => setSubjectSelect(event.target.value)}
          >
            <option value="">{t("manage.uploadForm.selectSubject")}</option>
            {subjects.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
            <option value="__custom">{t("manage.uploadForm.custom")}</option>
          </Select>
          {subjectSelect === "__custom" && (
            <Input
              value={subjectCustom}
              onChange={(event) => setSubjectCustom(event.target.value)}
              placeholder={t("manage.uploadForm.customSubjectPlaceholder")}
            />
          )}
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.uploadForm.year")}
          </label>
          <Select value={year} onChange={(event) => setYear(event.target.value)}>
            <option value="">{t("manage.uploadForm.selectYear")}</option>
            {years.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.uploadForm.term")}
          </label>
          <div className="flex flex-wrap gap-2">
            {["1차", "2차", "3차", "4차"].map((item) => (
              <Button
                key={item}
                type="button"
                variant={termPreset === item ? "primary" : "outline"}
                size="sm"
                onClick={() => setTermPreset(item)}
              >
                {item}
              </Button>
            ))}
            <Button
              type="button"
              variant={termPreset === "__custom" ? "primary" : "outline"}
              size="sm"
              onClick={() => setTermPreset("__custom")}
            >
              {t("manage.uploadForm.custom")}
            </Button>
          </div>
          {termPreset === "__custom" && (
            <Input
              value={termCustom}
              onChange={(event) => setTermCustom(event.target.value)}
              placeholder={t("manage.uploadForm.customTermPlaceholder")}
            />
          )}
        </div>
        <div className="grid gap-4 md:col-span-2 md:grid-cols-[1fr_auto] md:items-end">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("manage.uploadForm.generatedTitle")}
            </label>
            <div className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
              {computedTitle || t("manage.uploadForm.generatedTitleHint")}
            </div>
          </div>
          <div className="flex md:justify-end">
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? t("manage.uploadForm.uploading") : t("manage.uploadForm.uploadButton")}
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
          {t("manage.uploadForm.uploadSuccessPrefix")}
          {result.questionCount}
          {t("manage.uploadForm.uploadSuccessMiddle")}
          {result.choiceCount}
          {t("manage.uploadForm.uploadSuccessSuffix")}{" "}
          <Link href={`/manage/exams/${result.examId}`} className="underline">
            {t("manage.uploadForm.viewExam")}
          </Link>
          .
        </div>
      )}
    </div>
  );
}
