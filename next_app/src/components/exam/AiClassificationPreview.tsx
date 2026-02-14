"use client";

import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/http";
import {
  getApiEnvelopeData,
  getApiEnvelopeMessage,
  isApiEnvelopeOk,
  type ApiEnvelope,
} from "@/lib/api/contract";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type StatusPayload = {
  status?: string;
  total_count?: number;
  processed_count?: number;
  success_count?: number;
  failed_count?: number;
  progress_percent?: number;
  is_complete?: boolean;
  error_message?: string | null;
  can_cancel?: boolean;
};

type ResultEvidence = {
  page_start?: number | null;
  page_end?: number | null;
  quote?: string | null;
  snippet?: string | null;
  chunk_id?: number | null;
};

type ResultQuestion = {
  question_id?: number;
  question_number?: number;
  exam_title?: string;
  lecture_id?: number | null;
  lecture_title?: string | null;
  block_name?: string | null;
  confidence?: number | string | null;
  reason?: string | null;
  no_match?: boolean;
  question_content?: string | null;
  question_text?: string | null;
  question_choices?: string[] | null;
  evidence?: ResultEvidence[] | null;
  study_hint?: string | null;
  current_lecture_title?: string | null;
};

type ResultPayload = {
  grouped_results?: Array<{
    block_name?: string;
    lectures?: Array<{
      lecture_id?: number;
      lecture_title?: string;
      questions?: ResultQuestion[];
    }>;
  }>;
  no_match_list?: ResultQuestion[];
  summary?: {
    total?: number;
    success?: number;
    failed?: number;
    no_match?: number;
  };
};

type FlatResult = {
  questionId: number;
  questionNumber: number;
  examTitle: string;
  lectureId: number | null;
  lectureTitle: string;
  confidence: number;
  reason: string;
  noMatch: boolean;
  questionText: string;
  choices: string[];
  evidence: ResultEvidence[];
  studyHint: string;
  currentLectureTitle: string;
};

type ApplyPayload = {
  applied_count?: number;
  requested_count?: number;
  diagnostics?: {
    applyable_count?: number;
    no_match_count?: number;
    out_of_candidates_count?: number;
    missing_result_count?: number;
  };
};

type FilterMode = "all" | "high" | "low" | "nomatch";

const CONFIDENCE_THRESHOLD = 0.7;

const toNumber = (value: unknown) => {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

const toTextList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item : ""))
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
};

const normalizeEvidence = (value: unknown): ResultEvidence[] => {
  if (!Array.isArray(value)) return [];
  const rows: ResultEvidence[] = [];
  value.forEach((item) => {
    if (!item || typeof item !== "object") return;
    const obj = item as Record<string, unknown>;

    const rawPageStart =
      typeof obj.page_start === "number"
        ? obj.page_start
        : typeof obj.page_start === "string"
        ? Number(obj.page_start)
        : null;
    const rawPageEnd =
      typeof obj.page_end === "number"
        ? obj.page_end
        : typeof obj.page_end === "string"
        ? Number(obj.page_end)
        : null;
    const rawChunkId =
      typeof obj.chunk_id === "number"
        ? obj.chunk_id
        : typeof obj.chunk_id === "string"
        ? Number(obj.chunk_id)
        : null;

    rows.push({
      page_start: Number.isFinite(rawPageStart ?? NaN) ? rawPageStart : null,
      page_end: Number.isFinite(rawPageEnd ?? NaN) ? rawPageEnd : null,
      quote: typeof obj.quote === "string" ? obj.quote : null,
      snippet: typeof obj.snippet === "string" ? obj.snippet : null,
      chunk_id: Number.isFinite(rawChunkId ?? NaN) ? rawChunkId : null,
    });
  });
  return rows;
};

const flattenResults = (payload: ResultPayload): FlatResult[] => {
  const rows: FlatResult[] = [];
  (payload.grouped_results ?? []).forEach((block) => {
    (block.lectures ?? []).forEach((lecture) => {
      (lecture.questions ?? []).forEach((question) => {
        const questionId = toNumber(question.question_id);
        if (!questionId) return;
        rows.push({
          questionId,
          questionNumber: toNumber(question.question_number),
          examTitle: question.exam_title || "",
          lectureId: lecture.lecture_id ?? question.lecture_id ?? null,
          lectureTitle:
            [block.block_name, lecture.lecture_title]
              .filter((part) => typeof part === "string" && part.trim().length > 0)
              .join(" > ") || "미분류",
          confidence: toNumber(question.confidence),
          reason: question.reason || "",
          noMatch: Boolean(question.no_match || !lecture.lecture_id),
          questionText: (question.question_content || question.question_text || "").trim(),
          choices: toTextList(question.question_choices),
          evidence: normalizeEvidence(question.evidence),
          studyHint: (question.study_hint || "").trim(),
          currentLectureTitle: (question.current_lecture_title || "").trim(),
        });
      });
    });
  });

  (payload.no_match_list ?? []).forEach((question) => {
    const questionId = toNumber(question.question_id);
    if (!questionId) return;
    rows.push({
      questionId,
      questionNumber: toNumber(question.question_number),
      examTitle: question.exam_title || "",
      lectureId: null,
      lectureTitle: "분류 불가",
      confidence: toNumber(question.confidence),
      reason: question.reason || "",
      noMatch: true,
      questionText: (question.question_content || question.question_text || "").trim(),
      choices: toTextList(question.question_choices),
      evidence: normalizeEvidence(question.evidence),
      studyHint: (question.study_hint || "").trim(),
      currentLectureTitle: (question.current_lecture_title || "").trim(),
    });
  });

  rows.sort((a, b) => a.questionId - b.questionId);
  return rows;
};

const pageLabel = (evidence: ResultEvidence) => {
  const start = evidence.page_start;
  const end = evidence.page_end;
  if (typeof start !== "number" || Number.isNaN(start)) return "p.?";
  if (typeof end !== "number" || Number.isNaN(end) || end === start) return `p.${start}`;
  return `p.${start}-${end}`;
};

export function AiClassificationPreview({ jobId }: { jobId: number }) {
  const [status, setStatus] = useState<StatusPayload>({});
  const [result, setResult] = useState<ResultPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [appliedIds, setAppliedIds] = useState<Set<number>>(new Set());
  const [applying, setApplying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [applyMessage, setApplyMessage] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [currentIndex, setCurrentIndex] = useState(0);

  const rows = useMemo(() => flattenResults(result || {}), [result]);
  const visibleRows = useMemo(
    () => rows.filter((row) => !appliedIds.has(row.questionId)),
    [rows, appliedIds]
  );
  const selectableRows = useMemo(
    () => visibleRows.filter((row) => !row.noMatch && row.lectureId),
    [visibleRows]
  );
  const filteredRows = useMemo(() => {
    return visibleRows.filter((row) => {
      if (filterMode === "high") {
        return !row.noMatch && row.confidence >= CONFIDENCE_THRESHOLD;
      }
      if (filterMode === "low") {
        return !row.noMatch && row.confidence > 0 && row.confidence < CONFIDENCE_THRESHOLD;
      }
      if (filterMode === "nomatch") {
        return row.noMatch;
      }
      return true;
    });
  }, [visibleRows, filterMode]);

  const currentRow = filteredRows[currentIndex] || null;

  useEffect(() => {
    if (!filteredRows.length) {
      if (currentIndex !== 0) {
        setCurrentIndex(0);
      }
      return;
    }
    if (currentIndex > filteredRows.length - 1) {
      setCurrentIndex(filteredRows.length - 1);
    }
  }, [filteredRows, currentIndex]);

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;

    const loadResult = async () => {
      const payload = await apiFetch<ApiEnvelope<ResultPayload>>(`/ai/classify/result/${jobId}`, {
        cache: "no-store",
      });
      if (stopped) return;
      if (!isApiEnvelopeOk(payload)) {
        setError(getApiEnvelopeMessage(payload, "분류 결과를 불러오지 못했습니다."));
        return;
      }
      const data = getApiEnvelopeData(payload) || {};
      setResult(data);
      setAppliedIds(new Set());
      const autoSelected = new Set<number>();
      flattenResults(data).forEach((row) => {
        if (!row.noMatch && row.lectureId && row.confidence >= CONFIDENCE_THRESHOLD) {
          autoSelected.add(row.questionId);
        }
      });
      setSelected(autoSelected);
    };

    const poll = async () => {
      try {
        const payload = await apiFetch<ApiEnvelope<StatusPayload>>(`/ai/classify/status/${jobId}`, {
          cache: "no-store",
        });
        if (stopped) return;
        const data = getApiEnvelopeData(payload) || {};
        if (!isApiEnvelopeOk(payload)) {
          setError(
            getApiEnvelopeMessage(payload, data.error_message || "분류 상태를 확인하지 못했습니다.")
          );
          return;
        }
        setStatus(data);
        if (data.is_complete) {
          if (data.status === "completed" || data.status === "cancelled") {
            await loadResult();
            if (data.status === "cancelled") {
              setApplyMessage("분류 작업이 취소되었습니다. 완료된 결과만 적용할 수 있습니다.");
            }
          } else {
            setError(data.error_message || "분류 작업이 실패했습니다.");
          }
          return;
        }
        timer = window.setTimeout(poll, 1500);
      } catch (err) {
        if (!stopped) {
          setError(err instanceof Error ? err.message : "분류 상태 조회 중 오류가 발생했습니다.");
        }
      }
    };

    void poll();

    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [jobId]);

  const handleCancelJob = async () => {
    if (!jobId) return;
    setCancelling(true);
    setError(null);
    try {
      const payload = await apiFetch<ApiEnvelope<{ status?: string }>>(
        `/ai/classify/cancel/${jobId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );
      if (!isApiEnvelopeOk(payload)) {
        throw new Error(getApiEnvelopeMessage(payload, "분류 취소에 실패했습니다."));
      }
      const data = getApiEnvelopeData(payload) || {};
      setStatus((prev) => ({ ...prev, status: data.status, can_cancel: false }));
      setApplyMessage("분류 취소 요청을 보냈습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "분류 취소 중 오류가 발생했습니다.");
    } finally {
      setCancelling(false);
    }
  };

  const toggleSelected = (questionId: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  };

  const applyQuestions = async (questionIds: number[]) => {
    if (!questionIds.length) {
      setApplyMessage("적용할 문항이 없습니다.");
      return;
    }
    setApplying(true);
    setApplyMessage(null);
    setError(null);
    try {
      const payload = await apiFetch<ApiEnvelope<ApplyPayload>>("/ai/classify/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          question_ids: questionIds,
          apply_mode: "all",
        }),
      });
      if (!isApiEnvelopeOk(payload)) {
        throw new Error(getApiEnvelopeMessage(payload, "적용에 실패했습니다."));
      }
      const response = getApiEnvelopeData(payload) || {};
      const diagnostics = response.diagnostics || {};
      setApplyMessage(
        `${response.applied_count ?? 0}/${response.requested_count ?? questionIds.length} 적용 완료 · no_match ${diagnostics.no_match_count ?? 0} · 후보불일치 ${diagnostics.out_of_candidates_count ?? 0}`
      );
      setSelected((prev) => {
        const next = new Set(prev);
        questionIds.forEach((id) => next.delete(id));
        return next;
      });
      if ((response.applied_count ?? 0) === questionIds.length) {
        setAppliedIds((prev) => {
          const next = new Set(prev);
          questionIds.forEach((id) => next.add(id));
          return next;
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "적용 중 오류가 발생했습니다.");
    } finally {
      setApplying(false);
    }
  };

  const handleApplySelected = async () => {
    await applyQuestions(Array.from(selected));
  };

  const handleApplyHighConfidence = async () => {
    await applyQuestions(
      selectableRows
        .filter((row) => row.confidence >= CONFIDENCE_THRESHOLD)
        .map((row) => row.questionId)
    );
  };

  const handleApplyAllSuggested = async () => {
    await applyQuestions(selectableRows.map((row) => row.questionId));
  };

  const handleApplyCurrent = async () => {
    if (!currentRow || currentRow.noMatch || !currentRow.lectureId) return;
    await applyQuestions([currentRow.questionId]);
  };

  const toggleCurrentSelection = () => {
    if (!currentRow || currentRow.noMatch || !currentRow.lectureId) return;
    toggleSelected(currentRow.questionId);
  };

  const progressTitle =
    status.status === "processing"
      ? `분류 진행 중... (${status.processed_count ?? 0}/${status.total_count ?? 0})`
      : status.status === "completed"
      ? "분류 완료"
      : status.status === "cancelled"
      ? "분류 취소됨"
      : status.status === "failed"
      ? "분류 실패"
      : "분류 대기 중";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            AI Classification Review
          </p>
          <h2 className="text-2xl font-semibold text-foreground">작업 #{jobId}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{progressTitle}</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="neutral">진행률 {status.progress_percent ?? 0}%</Badge>
          <Badge variant="success">성공 {status.success_count ?? 0}</Badge>
          <Badge variant="danger">실패 {status.failed_count ?? 0}</Badge>
        </div>
      </div>

      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-4 p-5">
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-ai transition-all"
              style={{ width: `${status.progress_percent ?? 0}%` }}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Button onClick={handleApplySelected} disabled={applying || selected.size === 0}>
              선택 적용 ({selected.size})
            </Button>
            <Button
              variant="outline"
              onClick={handleApplyHighConfidence}
              disabled={applying || selectableRows.length === 0}
            >
              고신뢰({Math.round(CONFIDENCE_THRESHOLD * 100)}%+) 적용
            </Button>
            <Button
              variant="outline"
              onClick={handleApplyAllSuggested}
              disabled={applying || selectableRows.length === 0}
            >
              전체 제안 적용
            </Button>
            <Button
              variant="outline"
              onClick={handleCancelJob}
              disabled={
                cancelling ||
                !["pending", "processing"].includes(status.status ?? "")
              }
            >
              {cancelling ? "취소 중..." : "분류 취소"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                window.location.href = "/manage/classifications";
              }}
            >
              분류 대기열로 이동
            </Button>
          </div>
          {applyMessage && (
            <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-foreground">
              {applyMessage}
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border border-border/70 bg-card/85 shadow-soft">
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={filterMode === "all" ? "default" : "outline"}
              onClick={() => setFilterMode("all")}
            >
              전체
            </Button>
            <Button
              variant={filterMode === "high" ? "default" : "outline"}
              onClick={() => setFilterMode("high")}
            >
              고신뢰
            </Button>
            <Button
              variant={filterMode === "low" ? "default" : "outline"}
              onClick={() => setFilterMode("low")}
            >
              저신뢰
            </Button>
            <Button
              variant={filterMode === "nomatch" ? "default" : "outline"}
              onClick={() => setFilterMode("nomatch")}
            >
              분류 불가
            </Button>
            <Badge variant="neutral">
              {filteredRows.length} / {visibleRows.length}
            </Badge>
          </div>

          {currentRow ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  {currentIndex + 1} / {filteredRows.length}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                    disabled={currentIndex === 0}
                  >
                    이전
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setCurrentIndex((prev) =>
                        Math.min(filteredRows.length - 1, prev + 1)
                      )
                    }
                    disabled={currentIndex >= filteredRows.length - 1}
                  >
                    다음
                  </Button>
                </div>
              </div>

              <div className="rounded-xl border border-border/70 bg-background/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold text-foreground">
                      Q{currentRow.questionNumber || currentRow.questionId}
                    </div>
                    <div className="text-xs text-muted-foreground">{currentRow.examTitle || "-"}</div>
                    {currentRow.currentLectureTitle && (
                      <div className="text-xs text-muted-foreground">
                        현재 분류: {currentRow.currentLectureTitle}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={currentRow.noMatch ? "danger" : "success"}>
                      {currentRow.noMatch ? "분류 불가" : currentRow.lectureTitle}
                    </Badge>
                    <Badge
                      variant={
                        currentRow.noMatch
                          ? "danger"
                          : currentRow.confidence >= CONFIDENCE_THRESHOLD
                          ? "success"
                          : "neutral"
                      }
                    >
                      {Math.round(currentRow.confidence * 100)}%
                    </Badge>
                  </div>
                </div>

                <div className="mt-4 space-y-3 text-sm">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      문제
                    </p>
                    <p className="whitespace-pre-wrap text-foreground">
                      {currentRow.questionText || "문항 텍스트 없음"}
                    </p>
                  </div>

                  {currentRow.choices.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        보기
                      </p>
                      <ol className="list-decimal space-y-1 pl-5 text-foreground">
                        {currentRow.choices.map((choice, index) => (
                          <li key={`${currentRow.questionId}-choice-${index}`}>{choice}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      AI 분류 기준
                    </p>
                    <p className="whitespace-pre-wrap text-foreground">
                      {currentRow.reason || "근거 없음"}
                    </p>
                    {currentRow.studyHint && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        학습 포인트: {currentRow.studyHint}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      근거 문맥
                    </p>
                    {currentRow.evidence.length === 0 ? (
                      <p className="text-muted-foreground">근거가 없습니다.</p>
                    ) : (
                      <div className="space-y-2">
                        {currentRow.evidence.slice(0, 3).map((evidence, index) => (
                          <div
                            key={`${currentRow.questionId}-evidence-${index}`}
                            className="rounded-md border border-border/60 bg-muted/40 p-2"
                          >
                            <div className="text-xs text-muted-foreground">
                              {pageLabel(evidence)}
                              {evidence.chunk_id ? ` · chunk ${evidence.chunk_id}` : ""}
                            </div>
                            <p className="text-foreground">
                              {(evidence.quote || evidence.snippet || "").trim() || "-"}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  onClick={toggleCurrentSelection}
                  disabled={currentRow.noMatch || !currentRow.lectureId}
                >
                  {selected.has(currentRow.questionId) ? "현재 문항 선택 해제" : "현재 문항 선택"}
                </Button>
                <Button
                  onClick={handleApplyCurrent}
                  disabled={applying || currentRow.noMatch || !currentRow.lectureId}
                >
                  현재 문항 적용
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-border/70 bg-muted/20 p-6 text-sm text-muted-foreground">
              선택한 필터에서 표시할 결과가 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
