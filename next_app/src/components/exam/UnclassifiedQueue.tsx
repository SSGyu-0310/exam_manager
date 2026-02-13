"use client";

import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/http";
import { getUnclassifiedQueue } from "@/lib/api/exam";
import type { BlockSummary, ExamSummary, UnclassifiedQuestion } from "@/lib/api/exam";
import {
  getApiEnvelopeData,
  getApiEnvelopeMessage,
  isApiEnvelopeOk,
  type ApiEnvelope,
} from "@/lib/api/contract";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { TableRow } from "@/components/ui/table-row";
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
      setError(err instanceof Error ? err.message : t("classifications.errorLoadQueue"));
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

  const lectures = useMemo(() => {
    const flat: { id: number; label: string }[] = [];
    blocks.forEach((block) => {
      block.lectures.forEach((lecture) => {
        const subject = block.subject ?? t("classifications.unassigned");
        flat.push({ id: lecture.id, label: `${subject} · ${block.name} · ${lecture.title}` });
      });
    });
    return flat;
  }, [blocks, t]);

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
      setError(err instanceof Error ? err.message : t("classifications.errorBulkClassify"));
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
      setError(err instanceof Error ? err.message : t("classifications.errorBulkReset"));
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
      setError(err instanceof Error ? err.message : t("classifications.errorBulkMove"));
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
  }, [aiStatus.jobId]);

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

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {t("classifications.filters")}
                </p>
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t("classifications.searchPlaceholder")}
                />
              </div>
              <div className="min-w-[180px]">
                <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "unclassified")}>
                  <option value="unclassified">{t("classifications.statusUnclassified")}</option>
                  <option value="all">{t("classifications.statusAll")}</option>
                </Select>
              </div>
              <div className="min-w-[200px]">
                <Select value={examFilter} onChange={(event) => setExamFilter(event.target.value)}>
                  <option value="">{t("classifications.allExams")}</option>
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
                  <option value="">{t("classifications.selectLecture")}</option>
                  {lectures.map((lecture) => (
                    <option key={lecture.id} value={lecture.id}>
                      {lecture.label}
                    </option>
                  ))}
                </Select>
              </div>
              <Badge variant="neutral">{t("classifications.selected")} {selected.size}</Badge>
              <Button onClick={handleBulkClassify} disabled={!selected.size || !targetLecture}>
                {t("classifications.classifySelected")}
              </Button>
              <Button variant="outline" onClick={handleBulkMove} disabled={!selected.size || !targetLecture}>
                {t("classifications.moveSelected")}
              </Button>
              <Button variant="outline" onClick={handleBulkReset} disabled={!selected.size}>
                {t("classifications.resetSelected")}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-5">
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
                onClick={applyAiResults}
                disabled={!aiStatus.groupedResults?.length}
              >
                {t("classifications.applyAiResults")}
              </Button>
            </div>
            {recentJobs.length > 0 && (
              <div className="rounded-2xl border border-border/70 bg-muted/60 p-3 text-xs text-muted-foreground">
                <p className="font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {t("classifications.recentJobs")}
                </p>
                <div className="mt-2 space-y-1">
                  {recentJobs.map((job) => (
                    <button
                      key={job.id}
                      type="button"
                      className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-left transition hover:bg-muted"
                      onClick={() => {
                        window.location.href = previewRoute(job.id);
                      }}
                    >
                      <span>#{job.id} · {job.created_at}</span>
                      <span>{job.status_label ?? job.status}</span>
                    </button>
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
                <th className="px-5 py-3">{t("classifications.tableExam")}</th>
                <th className="px-5 py-3">{t("classifications.tableQuestion")}</th>
                <th className="px-5 py-3">{t("classifications.tableSnippet")}</th>
                <th className="px-5 py-3">{t("classifications.tableLecture")}</th>
                <th className="px-5 py-3">{t("classifications.tableStatus")}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableRow>
                  <td className="px-5 py-4 text-muted-foreground" colSpan={6}>
                    {t("classifications.loading")}
                  </td>
                </TableRow>
              ) : items.length === 0 ? (
                <TableRow>
                  <td className="px-5 py-4 text-muted-foreground" colSpan={6}>
                    {t("classifications.noQuestions")}
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
                        <span className="text-muted-foreground">{t("classifications.unclassified")}</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {item.isClassified ? (
                        <Badge variant="success">{t("classifications.classified")}</Badge>
                      ) : (
                        <Badge variant="danger">{t("classifications.unclassified")}</Badge>
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
