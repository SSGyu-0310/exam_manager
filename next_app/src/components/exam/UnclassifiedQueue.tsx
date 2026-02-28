"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/http";
import { getUnclassifiedQueue } from "@/lib/api/exam";
import type { BlockSummary, ExamSummary, UnclassifiedQuestion } from "@/lib/api/exam";
import {
  getApiEnvelopeData,
  getApiEnvelopeMessage,
  isApiEnvelopeOk,
  type ApiEnvelope,
} from "@/lib/api/contract";
import { ExamExplorer } from "./ExamExplorer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLanguage } from "@/context/LanguageContext";

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
  exam_id?: number | null;
  exam_title?: string | null;
  block_id?: number | null;
  block_name?: string | null;
  super_classify?: boolean;
};

type AiRecentPayload = {
  jobs?: RecentJob[];
};

type AiStartPayload = {
  job_id?: number;
  status?: string;
  reused?: boolean;
};

type AiStatusPayload = {
  status?: string;
  progress_percent?: number;
  is_complete?: boolean;
  error_message?: string;
};

type AiResultPayload = {
  grouped_results?: unknown[];
  summary?: AiStatus["summary"];
};

const previewRoute = (jobId: number) => `/manage/classifications/${jobId}`;

const normalizeSubject = (value: string | null | undefined) =>
  (value ?? "").trim().toLowerCase().replace(/\s+/g, " ");

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
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<UnclassifiedQuestion[]>([]);
  const [blocks, setBlocks] = useState<BlockSummary[]>([]);
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [examFilter, setExamFilter] = useState<string>("");
  const [superBlockFilter, setSuperBlockFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"unclassified" | "all">(
    "unclassified"
  );
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [aiStatus, setAiStatus] = useState<AiStatus>({});
  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([]);
  const [recentJobsOpen, setRecentJobsOpen] = useState(false);

  const loadQueue = useCallback(async () => {
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
      setError(err instanceof Error ? err.message : t("classifications.errorLoadQueue"));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, examFilter, query, t]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);



  useEffect(() => {
    const loadRecent = async () => {
      try {
        const payload = await apiFetch<ApiEnvelope<AiRecentPayload>>(
          "/ai/classify/recent",
          { cache: "no-store" }
        );
        const data = getApiEnvelopeData(payload);
        if (isApiEnvelopeOk(payload) && Array.isArray(data?.jobs)) {
          setRecentJobs(data.jobs);
        }
      } catch {
        // ignore
      }
    };
    void loadRecent();
  }, []);

  const selectedExam = useMemo(
    () => exams.find((exam) => String(exam.id) === examFilter) ?? null,
    [exams, examFilter]
  );
  const recentJobsPreview = useMemo(() => recentJobs.slice(0, 2), [recentJobs]);
  const displayedRecentJobs = useMemo(
    () => (recentJobsOpen ? recentJobs : recentJobsPreview),
    [recentJobs, recentJobsOpen, recentJobsPreview]
  );

  const formatRecentScope = useCallback(
    (job: RecentJob) => {
      const examTitle = (job.exam_title ?? "").trim();
      const blockName = (job.block_name ?? "").trim();
      if (examTitle && blockName) return `${examTitle} · ${blockName}`;
      if (examTitle) return `${examTitle} · ${t("classifications.recentUnknownBlock")}`;
      if (blockName) return `${t("classifications.recentUnknownExam")} · ${blockName}`;
      return t("classifications.recentScopeUnknown");
    },
    [t]
  );

  const superCandidateBlocks = useMemo(() => {
    if (!selectedExam) return [];
    const examSubject = normalizeSubject(selectedExam.subject);
    if (!examSubject) return [];
    return blocks.filter(
      (block) => normalizeSubject(block.subject) === examSubject
    );
  }, [blocks, selectedExam]);

  useEffect(() => {
    if (!superBlockFilter) return;
    if (!superCandidateBlocks.some((block) => String(block.id) === superBlockFilter)) {
      setSuperBlockFilter("");
    }
  }, [superCandidateBlocks, superBlockFilter]);

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
      setError(err instanceof Error ? err.message : t("classifications.errorBulkReset"));
    }
  };

  const startAiClassification = async () => {
    if (!selected.size) {
      setError(t("classifications.errorSelectFirst"));
      return;
    }
    try {
      const payload = await apiFetch<ApiEnvelope<AiStartPayload>>("/ai/classify/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_ids: Array.from(selected),
          force: true,
          retry_failed: true,
        }),
      });
      const data = getApiEnvelopeData(payload);
      if (!isApiEnvelopeOk(payload) || !data?.job_id) {
        throw new Error(getApiEnvelopeMessage(payload, t("classifications.errorAiStart")));
      }
      setAiStatus({ jobId: data.job_id, status: data.status, error: null });
      window.location.href = previewRoute(data.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("classifications.errorAiStart"));
    }
  };

  const startSuperClassification = async () => {
    if (!examFilter) {
      setError(t("classifications.errorSuperExamRequired"));
      return;
    }
    if (!superBlockFilter) {
      setError(t("classifications.errorSuperBlockRequired"));
      return;
    }
    try {
      const blockId = Number(superBlockFilter);
      const payload = await apiFetch<ApiEnvelope<AiStartPayload & { super_classify?: boolean }>>(
        "/ai/classify/super/start",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam_id: Number(examFilter),
            block_id: blockId,
            scope: {
              block_id: blockId,
              include_descendants: true,
            },
          }),
        }
      );
      const data = getApiEnvelopeData(payload);
      if (!isApiEnvelopeOk(payload) || !data?.job_id) {
        throw new Error(
          getApiEnvelopeMessage(payload, t("classifications.errorSuperStart"))
        );
      }
      setAiStatus({ jobId: data.job_id, status: data.status, error: null });
      window.location.href = previewRoute(data.job_id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("classifications.errorSuperStart")
      );
    }
  };

  useEffect(() => {
    if (!aiStatus.jobId) return;
    const poll = async () => {
      try {
        const statusPayload = await apiFetch<ApiEnvelope<AiStatusPayload>>(
          `/ai/classify/status/${aiStatus.jobId}`,
          { cache: "no-store" }
        );
        const statusData = getApiEnvelopeData(statusPayload);
        if (!isApiEnvelopeOk(statusPayload)) {
          throw new Error(
            getApiEnvelopeMessage(
              statusPayload,
              statusData?.error_message || "AI status failed."
            )
          );
        }
        setAiStatus((prev) => ({
          ...prev,
          status: statusData?.status,
          progress: statusData?.progress_percent,
          error: statusData?.error_message ?? null,
        }));
        if (statusData?.is_complete) {
          const resultPayload = await apiFetch<ApiEnvelope<AiResultPayload>>(
            `/ai/classify/result/${aiStatus.jobId}`,
            { cache: "no-store" }
          );
          const resultData = getApiEnvelopeData(resultPayload);
          if (isApiEnvelopeOk(resultPayload)) {
            setAiStatus((prev) => ({
              ...prev,
              groupedResults: resultData?.grouped_results ?? [],
              summary: resultData?.summary,
            }));
          }
        }
      } catch (err) {
        setAiStatus((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : t("classifications.errorAiPolling"),
        }));
      }
    };
    const id = window.setInterval(poll, 3000);
    void poll();
    return () => window.clearInterval(id);
  }, [aiStatus.jobId, t]);

  const applyAiResults = async () => {
    if (!aiStatus.jobId || !aiStatus.groupedResults) return;
    const ids = extractQuestionIds(aiStatus.groupedResults);
    if (!ids.length) {
      setError(t("classifications.errorNoAiResults"));
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
      setError(err instanceof Error ? err.message : t("classifications.errorApply"));
    }
  };

  /* ── Group items by exam ── */
  const examGroups = useMemo(() => {
    const map = new Map<number, { title: string; items: typeof items }>();
    items.forEach((item) => {
      const key = item.examId;
      if (!map.has(key)) {
        map.set(key, { title: item.examTitle ?? `Exam ${item.examId}`, items: [] });
      }
      map.get(key)!.items.push(item);
    });
    return Array.from(map.entries());
  }, [items]);

  return (
    <div className="space-y-5">
      {/* ── Top: Explorer + Filters/AI side by side ── */}
      <div className="flex flex-col gap-5 lg:flex-row">
        {/* Left Sidebar: Exam Explorer */}
        <div className="w-full lg:w-[460px] shrink-0">
          <div className="sticky top-6">
            <ExamExplorer
              exams={exams}
              blocks={blocks}
              examFilter={examFilter}
              setExamFilter={setExamFilter}
              superBlockFilter={superBlockFilter}
              setSuperBlockFilter={setSuperBlockFilter}
            />
          </div>
        </div>

        {/* Right: Filters + AI */}
        <div className="flex-1 space-y-4 min-w-0">
          {/* Filter & Action Bar */}
          <Card className="overflow-hidden border border-border/70 bg-card/85 shadow-soft">
            <div className="px-4 py-3 space-y-3">
              {/* Row 1: Status toggle + Search */}
              <div className="flex items-center gap-3">
                <div className="flex items-center rounded-lg border border-border/70 bg-muted/40 p-0.5">
                  <button
                    onClick={() => setStatusFilter("unclassified")}
                    className={`whitespace-nowrap rounded-md px-3 py-1 text-xs font-medium transition-all ${statusFilter === "unclassified"
                      ? "bg-amber-500 text-white shadow-sm"
                      : "text-muted-foreground hover:bg-muted"
                      }`}
                  >
                    {t("classifications.statusUnclassified")}
                  </button>
                  <button
                    onClick={() => setStatusFilter("all")}
                    className={`whitespace-nowrap rounded-md px-3 py-1 text-xs font-medium transition-all ${statusFilter === "all"
                      ? "bg-blue-500 text-white shadow-sm"
                      : "text-muted-foreground hover:bg-muted"
                      }`}
                  >
                    {t("classifications.statusAll")}
                  </button>
                </div>
                <div className="flex-1">
                  <Input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t("classifications.searchPlaceholder")}
                    className="h-8 text-xs"
                  />
                </div>
              </div>

              {/* Row 2: Action buttons */}
              <div className="flex items-center gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">
                    {t("classifications.selected")} {selected.size}
                  </span>
                  <Button size="sm" disabled title="추후 백엔드 개선 후 활성화 예정">
                    수동 분류
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleBulkReset} disabled={!selected.size}>
                    {t("classifications.resetSelected")}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* AI Classification */}
          <Card className="border border-border/70 bg-card/85 shadow-soft">
            <CardContent className="space-y-3 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {t("classifications.aiClassification")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("classifications.previewHint")}
              </p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>{t("classifications.selected")}: {selected.size}</p>
                {aiStatus.status && (
                  <p>
                    {t("classifications.status")}: {aiStatus.status}{" "}
                    {typeof aiStatus.progress === "number" ? `(${aiStatus.progress}%)` : ""}
                  </p>
                )}
                {aiStatus.summary && (
                  <p>
                    {t("classifications.summary")}: {aiStatus.summary.success}/{aiStatus.summary.total} {t("classifications.success")},{" "}
                    {aiStatus.summary.failed} {t("classifications.failed")}
                  </p>
                )}
                {aiStatus.error && <p className="text-danger">{aiStatus.error}</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={startAiClassification} disabled={!selected.size}>
                  {t("classifications.startAi")}
                </Button>
                <Button
                  variant="outline"
                  onClick={startSuperClassification}
                  disabled={!examFilter || !superBlockFilter}
                  title={t("classifications.superButtonTitle")}
                >
                  {t("classifications.startSuperAi")}
                </Button>
                <Button
                  variant="outline"
                  onClick={applyAiResults}
                  disabled={!aiStatus.groupedResults?.length}
                >
                  {t("classifications.applyAiResults")}
                </Button>
              </div>
              {recentJobs.length > 0 && (
                <div className="rounded-2xl border border-border/70 bg-muted/60 p-3 text-xs text-muted-foreground">
                  <div className="flex w-full items-center justify-between text-left">
                    <span className="font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {t("classifications.recentJobs")}
                    </span>
                    {recentJobs.length > 2 && (
                      <button
                        type="button"
                        className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
                        onClick={() => setRecentJobsOpen((prev) => !prev)}
                      >
                        {recentJobsOpen
                          ? t("classifications.recentJobsLess")
                          : t("classifications.recentJobsMore")}
                      </button>
                    )}
                  </div>
                  <div className="mt-2 space-y-1">
                    {displayedRecentJobs.map((job) => (
                      <button
                        key={job.id}
                        type="button"
                        className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-left transition hover:bg-muted"
                        onClick={() => { window.location.href = previewRoute(job.id); }}
                      >
                        <span className="flex min-w-0 flex-col">
                          <span className="truncate text-foreground">{formatRecentScope(job)}</span>
                          <span className="text-[11px] text-muted-foreground">{job.created_at}</span>
                        </span>
                        <span>{job.status_label ?? job.status}</span>
                      </button>
                    ))}
                    {!recentJobsOpen && recentJobs.length > 2 && (
                      <p className="px-2 pt-1 text-[11px] text-muted-foreground">
                        {t("classifications.recentJobsLimited")}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom: Full-width questions grouped by exam ── */}
      <div>
        {/* Header with select-all */}
        <div className="mb-3 flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={selected.size === items.length && items.length > 0}
              onChange={toggleAll}
              className="rounded"
            />
            {t("classifications.selected")} {selected.size}/{items.length}
          </label>
        </div>

        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">{t("classifications.loading")}</p>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">{t("classifications.noQuestions")}</p>
        ) : (
          <div className="space-y-4">
            {examGroups.map(([examId, group]) => (
              <Card key={examId} className="border border-border/70 bg-card/85 shadow-soft overflow-hidden">
                {/* Exam header */}
                <div className="border-b border-border/40 bg-muted/30 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground">{group.title}</span>
                  <span className="text-[10px] text-muted-foreground">{group.items.length}문항</span>
                </div>
                {/* Question mini-cards */}
                <div className="grid grid-cols-1 gap-2.5 p-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                  {group.items.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => toggleSelected(item.id)}
                      className={`cursor-pointer rounded-lg border p-2.5 transition-all hover:shadow-sm ${selected.has(item.id)
                        ? "border-primary/60 bg-primary/5 ring-1 ring-primary/30"
                        : "border-border/50 bg-background hover:border-border"
                        }`}
                    >
                      {/* Q number + status */}
                      <div className="mb-1.5 flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={selected.has(item.id)}
                          onChange={(e) => { e.stopPropagation(); toggleSelected(item.id); }}
                          className="rounded"
                        />
                        <span className="text-xs font-bold text-foreground">Q{item.questionNumber}</span>
                        {item.isClassified ? (
                          <Badge variant="success" className="text-[9px] px-1 py-0 leading-tight">분류</Badge>
                        ) : (
                          <Badge variant="danger" className="text-[9px] px-1 py-0 leading-tight">미분류</Badge>
                        )}
                      </div>
                      {/* Content preview */}
                      <div className="rounded-md bg-muted/30 px-2.5 py-2 text-xs leading-relaxed text-foreground/70 line-clamp-4 min-h-[60px]">
                        {item.content || item.snippet || <span className="italic text-muted-foreground">미리보기 없음</span>}
                      </div>
                      {/* Lecture */}
                      {item.lectureTitle && (
                        <p className="mt-1 truncate text-[9px] text-muted-foreground">
                          📚 {item.lectureTitle}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
