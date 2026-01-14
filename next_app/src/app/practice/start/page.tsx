"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiFetch, HttpError } from "@/lib/http";
import { StartCard } from "@/components/practice/StartCard";
import {
  examOptionSchema,
  lectureDetailSchema,
  type PracticeQuestion,
} from "@/components/practice/types";

type PracticeMode = "practice" | "timed";
type ExamOption = {
  id: number;
  title: string;
};

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";

const extractSessionId = (payload: unknown): string | number | null => {
  if (!payload || typeof payload !== "object") return null;
  const record = payload as Record<string, unknown>;
  const candidates = [
    record.sessionId,
    record.session_id,
    record.id,
    record.sessionID,
    record.session,
  ];
  for (const entry of candidates) {
    if (typeof entry === "string" || typeof entry === "number") {
      return entry;
    }
  }
  if (record.data && typeof record.data === "object") {
    const nested = record.data as Record<string, unknown>;
    const nestedId = nested.sessionId ?? nested.id;
    if (typeof nestedId === "string" || typeof nestedId === "number") {
      return nestedId;
    }
  }
  return null;
};

const createSession = async (
  lectureId: string,
  mode: PracticeMode,
  examIds: number[],
  filterActive: boolean
) => {
  const payload = { lectureId, mode, examIds, filterActive };
  const body = JSON.stringify(payload);
  const headers = { "Content-Type": "application/json" };
  const attempts = [
    {
      path: "/api/practice/sessions",
      init: { method: "POST", headers, body },
    },
    {
      path: `/api/practice/lecture/${encodeURIComponent(lectureId)}/start`,
      init: { method: "POST", headers, body },
    },
  ];

  let lastError: string | null = null;
  let unsupported = true;
  for (const attempt of attempts) {
    try {
      const result = await apiFetch<unknown>(attempt.path, attempt.init);
      const sessionId = extractSessionId(result);
      if (sessionId !== null) {
        return { sessionId, source: attempt.path };
      }
      unsupported = false;
      lastError = CONNECTION_ERROR_MESSAGE;
    } catch (error) {
      if (error instanceof HttpError) {
        if (error.payload.status === 404 || error.payload.status === 405) {
          continue;
        }
      }
      unsupported = false;
      lastError = error instanceof Error ? error.message : CONNECTION_ERROR_MESSAGE;
    }
  }

  return { sessionId: null, error: lastError ?? null, unsupported };
};

export default function PracticeStartPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const lectureIdParam = searchParams.get("lectureId");

  const [mode, setMode] = useState<PracticeMode>("practice");
  const [lectureTitle, setLectureTitle] = useState<string | undefined>();
  const [questionCount, setQuestionCount] = useState<number | undefined>();
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [examOptions, setExamOptions] = useState<ExamOption[]>([]);
  const [selectedExamIds, setSelectedExamIds] = useState<number[]>([]);
  const [appliedExamIds, setAppliedExamIds] = useState<number[]>([]);
  const [filterActive, setFilterActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [startLoading, setStartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const safeLectureId = useMemo(() => lectureIdParam ?? "", [lectureIdParam]);

  useEffect(() => {
    let active = true;
    if (!lectureIdParam) {
      setLoading(false);
      setError("Missing lecture selection.");
      return;
    }

    apiFetch<unknown>(`/api/practice/lecture/${encodeURIComponent(lectureIdParam)}`, {
      cache: "no-store",
    })
      .then((payload) => {
        if (!active) return;
        const parsed = lectureDetailSchema.safeParse(payload);
        if (!parsed.success) {
          setLectureTitle(undefined);
          setQuestionCount(undefined);
          return;
        }
        setLectureTitle(parsed.data.title ?? "Lecture");
        const parsedQuestions = parsed.data.questions ?? [];
        setQuestions(parsedQuestions);
        const options = parsed.data.examOptions ?? [];
        const validOptions = examOptionSchema.array().safeParse(options);
        const normalizedOptions = validOptions.success ? validOptions.data : [];
        setExamOptions(normalizedOptions);
        const fallbackIds = normalizedOptions.map((option) => option.id);
        const parsedSelected = parsed.data.selectedExamIds;
        const initialIds =
          Array.isArray(parsedSelected) && parsedSelected.length > 0
            ? parsedSelected
            : fallbackIds;
        setSelectedExamIds(initialIds);
        setAppliedExamIds(initialIds);
        setFilterActive(Boolean(parsed.data.filterActive));
        if (typeof parsed.data.totalCount === "number") {
          setQuestionCount(parsed.data.totalCount);
        } else if (Array.isArray(parsedQuestions)) {
          setQuestionCount(parsedQuestions.length);
        }
      })
      .catch(() => {
        if (!active) return;
        setError(CONNECTION_ERROR_MESSAGE);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [lectureIdParam]);

  const allExamIds = useMemo(
    () => examOptions.map((option) => option.id),
    [examOptions]
  );

  const activeExamIds = filterActive ? appliedExamIds : allExamIds;

  const filteredQuestions = useMemo(() => {
    if (!questions.length) return [];
    if (!examOptions.length) return questions;
    if (!filterActive) return questions;
    if (!activeExamIds.length) return [];
    const allowed = new Set(activeExamIds);
    return questions.filter(
      (question) => typeof question.examId === "number" && allowed.has(question.examId)
    );
  }, [questions, examOptions.length, filterActive, activeExamIds]);

  const stats = useMemo(() => {
    const total = filteredQuestions.length;
    const objective = filteredQuestions.filter((question) => !question.isShortAnswer).length;
    const subjective = filteredQuestions.filter((question) => question.isShortAnswer).length;
    const multiple = filteredQuestions.filter(
      (question) => !question.isShortAnswer && question.isMultipleResponse
    ).length;
    return { total, objective, subjective, multiple };
  }, [filteredQuestions]);

  const handleExamToggle = (examId: number) => {
    setSelectedExamIds((prev) =>
      prev.includes(examId) ? prev.filter((id) => id !== examId) : [...prev, examId]
    );
  };

  const handleApplyFilter = () => {
    setAppliedExamIds(selectedExamIds);
    setFilterActive(true);
  };

  const handleResetFilter = () => {
    setSelectedExamIds(allExamIds);
    setAppliedExamIds(allExamIds);
    setFilterActive(false);
  };

  const startDisabled = filterActive && appliedExamIds.length === 0;
  const validationMessage =
    filterActive && appliedExamIds.length === 0
      ? "Select at least one exam to continue."
      : null;
  const displayQuestionCount = filterActive ? stats.total : questionCount ?? stats.total;

  const handleStart = async () => {
    if (!lectureIdParam) {
      setError("Missing lecture selection.");
      return;
    }
    if (startDisabled) {
      setError("Select at least one exam to continue.");
      return;
    }
    setStartLoading(true);
    setError(null);

    const result = await createSession(
      lectureIdParam,
      mode,
      filterActive ? appliedExamIds : [],
      filterActive
    );
    const sessionId =
      result.sessionId ?? `lecture-${encodeURIComponent(String(lectureIdParam))}`;
    const shouldWarn = result.sessionId === null && result.error && !result.unsupported;

    const sessionPayload = {
      lectureId: lectureIdParam,
      lectureTitle,
      mode,
      fallback: result.sessionId === null,
      examIds: filterActive ? appliedExamIds : [],
      filterActive,
      createdAt: Date.now(),
      warning: shouldWarn ? result.error : null,
      source: result.sessionId === null ? "lecture-fallback" : result.source,
    };

    if (typeof window !== "undefined") {
      sessionStorage.setItem(
        `practice:session:${sessionId}`,
        JSON.stringify(sessionPayload)
      );
      if (shouldWarn) {
        sessionStorage.setItem(
          `practice:warning:${sessionId}`,
          result.error ?? CONNECTION_ERROR_MESSAGE
        );
      }
    }

    router.push(`/practice/session/${sessionId}`);
  };

  return (
    <div className="min-h-[70vh]">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-center gap-8">
        {loading ? (
          <div className="w-full max-w-2xl animate-pulse rounded-3xl border border-border/60 bg-card/70 p-8 shadow-soft backdrop-blur">
            <div className="h-4 w-32 rounded-full bg-muted" />
            <div className="mt-4 h-6 w-64 rounded-full bg-muted" />
            <div className="mt-2 h-4 w-48 rounded-full bg-muted" />
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="h-24 rounded-2xl bg-muted" />
              <div className="h-24 rounded-2xl bg-muted" />
            </div>
            <div className="mt-6 h-12 rounded-full bg-muted" />
          </div>
        ) : (
          <StartCard
            title={lectureTitle}
            questionCount={displayQuestionCount}
            stats={stats}
            examFilter={{
              options: examOptions,
              selectedIds: selectedExamIds,
              active: filterActive,
              onToggle: handleExamToggle,
              onApply: handleApplyFilter,
              onReset: handleResetFilter,
            }}
            mode={mode}
            onModeChange={setMode}
            onStart={handleStart}
            loading={startLoading}
            error={error}
            validationMessage={validationMessage}
          />
        )}
        {!safeLectureId && (
          <p className="text-sm text-muted-foreground">Select a lecture to continue.</p>
        )}
      </div>
    </div>
  );
}
