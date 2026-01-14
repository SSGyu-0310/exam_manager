"use client";

import { useState } from "react";
import Link from "next/link";

import { uploadPdf } from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function UploadPdfForm() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [year, setYear] = useState("");
  const [term, setTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    examId: number;
    questionCount: number;
    choiceCount: number;
  } | null>(null);

  const handleSubmit = async () => {
    if (!file) {
      setError("Select a PDF file first.");
      return;
    }
    if (!title.trim()) {
      setError("Exam title is required.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("pdf_file", file);
    formData.append("title", title.trim());
    if (subject.trim()) formData.append("subject", subject.trim());
    if (year.trim()) formData.append("year", year.trim());
    if (term.trim()) formData.append("term", term.trim());

    try {
      const data = await uploadPdf(formData);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              PDF file
            </label>
            <Input
              type="file"
              accept="application/pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Exam title
            </label>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Subject
            </label>
            <Input value={subject} onChange={(event) => setSubject(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Year
            </label>
            <Input
              type="number"
              value={year}
              onChange={(event) => setYear(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Term
            </label>
            <Input value={term} onChange={(event) => setTerm(event.target.value)} />
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        {result && (
          <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
            Uploaded successfully. {result.questionCount} questions and {result.choiceCount} choices
            created.{" "}
            <Link href={`/manage/exams/${result.examId}`} className="underline">
              View exam
            </Link>
            .
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? "Uploading..." : "Upload PDF"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
