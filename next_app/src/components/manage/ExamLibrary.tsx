"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, RefreshCw, Search } from "lucide-react";

import { getExams, deleteExam, type ManageExam } from "@/lib/api/manage";
import { ExamsTable } from "@/components/manage/ExamsTable";
import { UploadPdfForm } from "@/components/manage/UploadPdfForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/context/LanguageContext";

type ExamLibraryProps = {
  initialExams: ManageExam[];
  initialError?: string | null;
};

export function ExamLibrary({ initialExams, initialError }: ExamLibraryProps) {
  const { t } = useLanguage();
  const [exams, setExams] = useState<ManageExam[]>(initialExams);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [uploadExpanded, setUploadExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setExams(initialExams);
  }, [initialExams]);

  useEffect(() => {
    setError(initialError ?? null);
  }, [initialError]);

  const refreshExams = async () => {
    setLoading(true);
    try {
      const data = await getExams();
      setExams(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.uploadedExamsError"));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (examId: number) => {
    try {
      await deleteExam(examId);
      setExams((prev) => prev.filter((exam) => exam.id !== examId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.examDeleteError"));
    }
  };

  const filteredExams = useMemo(() => {
    if (!searchQuery.trim()) return exams;
    const query = searchQuery.toLowerCase();
    return exams.filter(
      (exam) =>
        exam.title.toLowerCase().includes(query) ||
        exam.subject?.toLowerCase().includes(query) ||
        exam.year?.toString().includes(query) ||
        exam.term?.toLowerCase().includes(query)
    );
  }, [exams, searchQuery]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {t("manage.exams")}
          </p>
          <h2 className="text-2xl font-semibold text-foreground">
            {t("manage.uploadedExams")}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("manage.uploadedExamsDesc")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshExams} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {loading ? t("common.refreshing") : t("common.refresh")}
          </Button>
        </div>
      </div>

      {/* Collapsible Upload Card */}
      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <button
          type="button"
          onClick={() => setUploadExpanded(!uploadExpanded)}
          className="flex w-full items-center justify-between px-6 py-4 text-left hover:bg-muted/30 transition-colors"
        >
          <span className="text-sm font-semibold text-foreground">
            {t("manage.uploadNewExam")}
          </span>
          {uploadExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {uploadExpanded && (
          <CardContent className="border-t border-border/50 pt-0">
            <UploadPdfForm onUploaded={refreshExams} />
          </CardContent>
        )}
      </Card>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-card/60 px-4 py-3">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder={t("manage.searchExamsPlaceholder")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 border-0 bg-transparent p-0 text-sm focus:ring-0"
        />
        {searchQuery && (
          <span className="text-xs text-muted-foreground">
            {filteredExams.length} / {exams.length}
          </span>
        )}
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      ) : (
        <ExamsTable exams={filteredExams} showActions onDelete={handleDelete} />
      )}
    </div>
  );
}
