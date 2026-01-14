"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  createExam,
  deleteExam,
  updateExam,
  type ManageExam,
  type ManageExamInput,
} from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type ExamFormProps = {
  initial?: ManageExam | null;
};

export function ExamForm({ initial }: ExamFormProps) {
  const router = useRouter();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [examDate, setExamDate] = useState(initial?.examDate ?? "");
  const [subject, setSubject] = useState(initial?.subject ?? "");
  const [year, setYear] = useState(initial?.year ?? "");
  const [term, setTerm] = useState(initial?.term ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: ManageExamInput = {
      title: title.trim(),
      examDate: examDate || null,
      subject: subject?.trim() || null,
      year: year ? Number(year) : null,
      term: term?.trim() || null,
      description: description?.trim() || null,
    };

    try {
      if (initial?.id) {
        await updateExam(initial.id, payload);
        setSuccess("Exam updated.");
      } else {
        await createExam(payload);
        setSuccess("Exam created.");
      }
      router.push("/manage/exams");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save exam.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initial?.id) return;
    const confirmed = window.confirm("Delete this exam? This cannot be undone.");
    if (!confirmed) return;
    setSaving(true);
    setError(null);
    try {
      await deleteExam(initial.id);
      router.push("/manage/exams");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete exam.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Title
          </label>
          <Input value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Exam date
            </label>
            <Input
              type="date"
              value={examDate ?? ""}
              onChange={(event) => setExamDate(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Subject
            </label>
            <Input value={subject ?? ""} onChange={(event) => setSubject(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Year
            </label>
            <Input
              type="number"
              value={year ?? ""}
              onChange={(event) => setYear(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Term
            </label>
            <Input value={term ?? ""} onChange={(event) => setTerm(event.target.value)} />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Description
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
              Delete exam
            </Button>
          ) : (
            <div />
          )}
          <Button onClick={handleSubmit} disabled={saving || !title.trim()}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
