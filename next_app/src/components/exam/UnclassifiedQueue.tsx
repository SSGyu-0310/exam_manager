"use client";

import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/http";
import { getUnclassifiedQueue } from "@/lib/api/exam";
import type { BlockSummary, ExamSummary, UnclassifiedQuestion } from "@/lib/api/exam";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { TableRow } from "@/components/ui/table-row";

type AiStatus = {
  jobId?: number;
  status?: string;
  progress?: number;
  error?: string | null;
  summary?: {
    total?: number;
    success?: number;
    failed?: number;
    no_match?: number;
  };
  groupedResults?: unknown[];
};

type RecentJob = {
  id: number;
  created_at: string;
  status: string;
  status_label?: string;
  total_count?: number;
  success_count?: number;
};

const extractQuestionIds = (grouped: unknown[]) => {
  const ids: number[] = [];
  grouped.forEach((block) => {
    const blockRecord = block as { lectures?: unknown[] };
    (blockRecord.lectures ?? []).forEach((lecture) => {
      const lectureRecord = lecture as { questions?: unknown[] };
      (lectureRecord.questions ?? []).forEach((question) => {
        const q = question as { question_id?: number; questionId?: number; id?: number };
        const id = q.question_id ?? q.questionId ?? q.id;
        if (typeof id === "number") ids.push(id);
      });
    });
  });
  return ids;
};

export function UnclassifiedQueue() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<UnclassifiedQuestion[]>([]);
  const [blocks, setBlocks] = useState<BlockSummary[]>([]);
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [examFilter, setExamFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"unclassified" | "all">(
    "unclassified"
  );
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [targetLecture, setTargetLecture] = useState<string>("");
  const [aiStatus, setAiStatus] = useState<AiStatus>({});
  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([]);

  const loadQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getUnclassifiedQueue({
        status: statusFilter,
        examId: examFilter || undefined,
        query: query || undefined,
      });
      setItems(data.items);
      setBlocks(data.blocks);
      setExams(data.exams);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadQueue();
  }, [statusFilter, examFilter, query]);

  useEffect(() => {
    const loadRecent = async () => {
      try {
        const data = await apiFetch<{ success?: boolean; jobs?: RecentJob[] }>(
          "/ai/classify/recent",
          { cache: "no-store" }
        );
        if (data.success && Array.isArray(data.jobs)) {
          setRecentJobs(data.jobs);
        }
      } catch {
        // ignore
      }
    };
    void loadRecent();
  }, []);

  const lectures = useMemo(() => {
    const flat: { id: number; label: string }[] = [];
    blocks.forEach((block) => {
      block.lectures.forEach((lecture) => {
        const subject = block.subject ?? "Unassigned";
        flat.push({ id: lecture.id, label: `${subject} · ${block.name} · ${lecture.title}` });
      });
    });
    return flat;
  }, [blocks]);

  const toggleSelected = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      if (prev.size === items.length) return new Set();
      return new Set(items.map((item) => item.id));
    });
  };

  const handleBulkClassify = async () => {
    if (!selected.size || !targetLecture) return;
    try {
      await apiFetch("/exam/questions/bulk-classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_ids: Array.from(selected),
          lecture_id: Number(targetLecture),
        }),
      });
      setSelected(new Set());
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk classify failed.");
    }
  };

  const handleBulkReset = async () => {
    if (!selected.size) return;
    try {
      await apiFetch("/manage/questions/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_ids: Array.from(selected),
        }),
      });
      setSelected(new Set());
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.");
    }
  };

  const handleBulkMove = async () => {
    if (!selected.size || !targetLecture) return;
    try {
      await apiFetch("/manage/questions/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_ids: Array.from(selected),
          target_lecture_id: Number(targetLecture),
        }),
      });
      setSelected(new Set());
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Move failed.");
    }
  };

  const startAiClassification = async () => {
    if (!selected.size) {
      setError("Select questions before starting AI.");
      return;
    }
    try {
      const response = await apiFetch<{
        success?: boolean;
        job_id?: number;
        status?: string;
        error?: string;
      }>("/ai/classify/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_ids: Array.from(selected) }),
      });
      if (!response.success || !response.job_id) {
        throw new Error(response.error || "AI start failed.");
      }
      setAiStatus({ jobId: response.job_id, status: response.status, error: null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI start failed.");
    }
  };

  useEffect(() => {
    if (!aiStatus.jobId) return;
    const poll = async () => {
      try {
        const response = await apiFetch<{
          success?: boolean;
          status?: string;
          progress_percent?: number;
          is_complete?: boolean;
          error_message?: string;
        }>(`/ai/classify/status/${aiStatus.jobId}`, { cache: "no-store" });
        if (!response.success) {
          throw new Error(response.error_message || "AI status failed.");
        }
        setAiStatus((prev) => ({
          ...prev,
          status: response.status,
          progress: response.progress_percent,
          error: response.error_message ?? null,
        }));
        if (response.is_complete) {
          const result = await apiFetch<{
            success?: boolean;
            grouped_results?: unknown[];
            summary?: AiStatus["summary"];
          }>(`/ai/classify/result/${aiStatus.jobId}`, { cache: "no-store" });
          if (result.success) {
            setAiStatus((prev) => ({
              ...prev,
              groupedResults: result.grouped_results ?? [],
              summary: result.summary,
            }));
          }
        }
      } catch (err) {
        setAiStatus((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : "AI polling failed.",
        }));
      }
    };
    const id = window.setInterval(poll, 3000);
    void poll();
    return () => window.clearInterval(id);
  }, [aiStatus.jobId]);

  const applyAiResults = async () => {
    if (!aiStatus.jobId || !aiStatus.groupedResults) return;
    const ids = extractQuestionIds(aiStatus.groupedResults);
    if (!ids.length) {
      setError("No AI results to apply.");
      return;
    }
    try {
      await apiFetch("/ai/classify/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: aiStatus.jobId, question_ids: ids }),
      });
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Apply failed.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Filters
                </p>
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search content..."
                />
              </div>
              <div className="min-w-[180px]">
                <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "unclassified")}>
                  <option value="unclassified">Unclassified</option>
                  <option value="all">All</option>
                </Select>
              </div>
              <div className="min-w-[200px]">
                <Select value={examFilter} onChange={(event) => setExamFilter(event.target.value)}>
                  <option value="">All exams</option>
                  {exams.map((exam) => (
                    <option key={exam.id} value={exam.id}>
                      {exam.title}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <Select
                  value={targetLecture}
                  onChange={(event) => setTargetLecture(event.target.value)}
                >
                  <option value="">Select lecture</option>
                  {lectures.map((lecture) => (
                    <option key={lecture.id} value={lecture.id}>
                      {lecture.label}
                    </option>
                  ))}
                </Select>
              </div>
              <Badge variant="neutral">Selected {selected.size}</Badge>
              <Button onClick={handleBulkClassify} disabled={!selected.size || !targetLecture}>
                Classify selected
              </Button>
              <Button variant="outline" onClick={handleBulkMove} disabled={!selected.size || !targetLecture}>
                Move selected
              </Button>
              <Button variant="outline" onClick={handleBulkReset} disabled={!selected.size}>
                Reset selected
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              AI classification
            </p>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>Selected: {selected.size}</p>
              {aiStatus.status && (
                <p>
                  Status: {aiStatus.status}{" "}
                  {typeof aiStatus.progress === "number" ? `(${aiStatus.progress}%)` : ""}
                </p>
              )}
              {aiStatus.summary && (
                <p>
                  Summary: {aiStatus.summary.success}/{aiStatus.summary.total} success,{" "}
                  {aiStatus.summary.failed} failed
                </p>
              )}
              {aiStatus.error && <p className="text-danger">{aiStatus.error}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={startAiClassification} disabled={!selected.size}>
                Start AI
              </Button>
              <Button
                variant="outline"
                onClick={applyAiResults}
                disabled={!aiStatus.groupedResults?.length}
              >
                Apply AI results
              </Button>
            </div>
            {recentJobs.length > 0 && (
              <div className="rounded-2xl border border-border/70 bg-muted/60 p-3 text-xs text-muted-foreground">
                <p className="font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Recent jobs
                </p>
                <div className="mt-2 space-y-1">
                  {recentJobs.map((job) => (
                    <div key={job.id} className="flex items-center justify-between">
                      <span>#{job.id} · {job.created_at}</span>
                      <span>{job.status_label ?? job.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
              <tr>
                <th className="px-5 py-3">
                  <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} />
                </th>
                <th className="px-5 py-3">Exam</th>
                <th className="px-5 py-3">Question</th>
                <th className="px-5 py-3">Snippet</th>
                <th className="px-5 py-3">Lecture</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableRow>
                  <td className="px-5 py-4 text-muted-foreground" colSpan={6}>
                    Loading...
                  </td>
                </TableRow>
              ) : items.length === 0 ? (
                <TableRow>
                  <td className="px-5 py-4 text-muted-foreground" colSpan={6}>
                    No questions found.
                  </td>
                </TableRow>
              ) : (
                items.map((item) => (
                  <TableRow key={item.id}>
                    <td className="px-5 py-4">
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        onChange={() => toggleSelected(item.id)}
                      />
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {item.examTitle ?? `Exam ${item.examId}`}
                    </td>
                    <td className="px-5 py-4 font-semibold text-foreground">
                      Q{item.questionNumber}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {item.snippet ?? ""}
                    </td>
                    <td className="px-5 py-4">
                      {item.lectureTitle ? (
                        <span className="text-foreground">{item.lectureTitle}</span>
                      ) : (
                        <span className="text-muted-foreground">Unclassified</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {item.isClassified ? (
                        <Badge variant="success">Classified</Badge>
                      ) : (
                        <Badge variant="danger">Unclassified</Badge>
                      )}
                    </td>
                  </TableRow>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
