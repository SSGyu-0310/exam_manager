"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  deleteExam,
  updateExam,
  type ManageExam,
  type ManageExamInput,
  getSubjects,
} from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useLanguage } from "@/context/LanguageContext";

type ExamFormProps = {
  initial?: ManageExam | null;
};

export function ExamForm({ initial }: ExamFormProps) {
  const { t } = useLanguage();
  const router = useRouter();
  const presetTerms = ["1차", "2차", "3차", "4차"];
  const initialTerm = initial?.term ?? "";
  const isPresetTerm = presetTerms.includes(initialTerm);

  const [subjects, setSubjects] = useState<string[]>([]);
  const [subjectSelect, setSubjectSelect] = useState(initial?.subject ?? "");
  const [subjectCustom, setSubjectCustom] = useState("");
  const [year, setYear] = useState(initial?.year ? String(initial.year) : "");
  const [termPreset, setTermPreset] = useState(isPresetTerm ? initialTerm : initialTerm ? "__custom" : "");
  const [termCustom, setTermCustom] = useState(isPresetTerm ? "" : initialTerm);
  const [description, setDescription] = useState(initial?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
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
    [resolvedSubject, year, resolvedTerm]
  );

  const years = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const list: string[] = [];
    for (let y = currentYear + 1; y >= 2000; y -= 1) {
      list.push(String(y));
    }
    return list;
  }, []);

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

  useEffect(() => {
    if (!initial?.subject || subjects.length === 0) return;
    if (subjects.includes(initial.subject)) {
      setSubjectSelect(initial.subject);
      setSubjectCustom("");
    } else {
      setSubjectSelect("__custom");
      setSubjectCustom(initial.subject);
    }
  }, [subjects, initial?.subject]);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    if (!initial?.id) {
      setError(t("manage.examForm.saveError"));
      setSaving(false);
      return;
    }

    if (!resolvedSubject || !year || !resolvedTerm) {
      setError(t("manage.examForm.missingFieldsError"));
      setSaving(false);
      return;
    }

    if (!computedTitle) {
      setError(t("manage.examForm.titleGenerateError"));
      setSaving(false);
      return;
    }

    const payload: ManageExamInput = {
      title: computedTitle,
      subject: resolvedSubject || null,
      year: year ? Number(year) : null,
      term: resolvedTerm || null,
      description: description?.trim() || null,
    };

    try {
      await updateExam(initial.id, payload);
      setSuccess(t("manage.examForm.updated"));
      router.push("/manage/exams");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.examForm.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initial?.id) return;
    const confirmed = window.confirm(t("manage.examForm.deleteConfirm"));
    if (!confirmed) return;
    setSaving(true);
    setError(null);
    try {
      await deleteExam(initial.id);
      router.push("/manage/exams");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.examForm.deleteError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("manage.examForm.subject")}
            </label>
            <Select
              value={subjectSelect}
              onChange={(event) => setSubjectSelect(event.target.value)}
            >
              <option value="">{t("manage.examForm.selectSubject")}</option>
              {subjects.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
              <option value="__custom">{t("manage.examForm.custom")}</option>
            </Select>
            {subjectSelect === "__custom" && (
              <Input
                value={subjectCustom}
                onChange={(event) => setSubjectCustom(event.target.value)}
                placeholder={t("manage.examForm.customSubjectPlaceholder")}
              />
            )}
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("manage.examForm.year")}
            </label>
            <Select value={year} onChange={(event) => setYear(event.target.value)}>
              <option value="">{t("manage.examForm.selectYear")}</option>
              {years.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("manage.examForm.term")}
            </label>
            <div className="flex flex-wrap gap-2">
              {presetTerms.map((item) => (
                <Button
                  key={item}
                  type="button"
                  variant={termPreset === item ? "primary" : "outline"}
                  size="sm"
                  onClick={() => {
                    setTermPreset(item);
                    setTermCustom("");
                  }}
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
                {t("manage.examForm.custom")}
              </Button>
            </div>
            {termPreset === "__custom" && (
              <Input
                value={termCustom}
                onChange={(event) => setTermCustom(event.target.value)}
                placeholder={t("manage.examForm.customTermPlaceholder")}
              />
            )}
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.examForm.generatedTitle")}
          </label>
          <div className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            {computedTitle || t("manage.examForm.generatedTitleHint")}
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("manage.examForm.description")}
          </label>
          <Textarea
            value={description ?? ""}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
            {success}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {initial?.id ? (
            <Button variant="outline" onClick={handleDelete} disabled={saving}>
              {t("manage.examForm.delete")}
            </Button>
          ) : (
            <div />
          )}
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? t("manage.examForm.saving") : t("manage.examForm.save")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
