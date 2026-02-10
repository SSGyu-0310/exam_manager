"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Copy } from "lucide-react";

import { apiFetch } from "@/lib/http";
import { resolveImageUrl } from "@/lib/image";
import { ResultSummary } from "@/components/practice/ResultSummary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  AnswerPayload,
  lectureResultSchema,
  PracticeQuestion,
} from "@/components/practice/types";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";

type StoredResult = {
  lectureId?: string;
  examId?: string;
  examTitle?: string;
  submittedAt?: string;
  summary?: {
    all?: {
      total?: number;
      answered?: number;
      correct?: number;
    };
  };
  items?: unknown[];
  answers?: Record<string, AnswerPayload>;
  mode?: string;
  examIds?: number[];
  filterActive?: boolean;
};

type ResultItem = {
  questionId: string;
  type?: string;
  isAnswered?: boolean;
  isCorrect?: boolean | null;
  userAnswer?: unknown;
  correctAnswer?: unknown;
  correctAnswerText?: string | null;
};

type ResultQuestion = PracticeQuestion & {
  explanation?: string | null;
  correctChoiceNumbers?: number[];
  correctAnswerText?: string | null;
};

const normalizeResultItem = (raw: unknown): ResultItem | null => {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const rawId = record.questionId ?? record.question_id;
  if (typeof rawId !== "string" && typeof rawId !== "number") return null;
  return {
    questionId: String(rawId),
    type: typeof record.type === "string" ? record.type : undefined,
    isAnswered: typeof record.isAnswered === "boolean" ? record.isAnswered : undefined,
    isCorrect: typeof record.isCorrect === "boolean" ? record.isCorrect : null,
    userAnswer: record.userAnswer,
    correctAnswer: record.correctAnswer,
    correctAnswerText:
      typeof record.correctAnswerText === "string" ? record.correctAnswerText : null,
  };
};

const formatAnswer = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "--";
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : "--";
  }
  if (typeof value === "number") {
    return String(value);
  }
  return "--";
};

const MARKDOWN_IMAGE_REGEX = /!\[[^\]]*]\(([^)]+)\)/g;

const parseStemContent = (value?: string) => {
  if (!value) {
    return { text: "", images: [] as string[] };
  }
  const images: string[] = [];
  const cleaned = value.replace(MARKDOWN_IMAGE_REGEX, (_match, url) => {
    if (typeof url === "string") {
      const trimmed = url.trim();
      if (trimmed) {
        images.push(trimmed);
      }
    }
    return "";
  });
  return {
    text: cleaned.replace(/\s{2,}/g, " ").trim(),
    images,
  };
};

const getPrimaryImageUrl = (question: ResultQuestion) => {
  const direct = resolveImageUrl(question.imageUrl ?? question.image);
  if (direct) return direct;
  const { images } = parseStemContent(question.stem ?? "");
  for (const candidate of images) {
    const normalized = resolveImageUrl(candidate);
    if (normalized) return normalized;
  }
  return null;
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");

const readBlobAsDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Failed to read image"));
    reader.readAsDataURL(blob);
  });

const buildCopyText = ({
  question,
  result,
  index,
}: {
  question: ResultQuestion;
  result?: ResultItem;
  index: number;
}) => {
  const { text: stemText } = parseStemContent(question.stem ?? "");
  const lines = [`Question ${index + 1}`, stemText || "No prompt available."];
  if (!question.isShortAnswer) {
    const choices = question.choices ?? [];
    if (choices.length) {
      lines.push("", "Choices:");
      choices.forEach((choice, choiceIndex) => {
        const choiceId =
          typeof choice.number === "number" ? choice.number : choiceIndex + 1;
        lines.push(`${choiceId}. ${choice.content ?? "Choice"}`);
      });
    }
  }

  const userAnswer = formatAnswer(result?.userAnswer);
  const correctAnswers =
    question.correctChoiceNumbers ??
    (Array.isArray(result?.correctAnswer) ? result?.correctAnswer : []);
  const correctAnswerText =
    question.correctAnswerText ?? result?.correctAnswerText ?? null;

  lines.push("", `Your answer: ${userAnswer}`);
  if (question.isShortAnswer) {
    lines.push(`Correct answer: ${formatAnswer(correctAnswerText)}`);
  } else {
    lines.push(`Correct answer: ${formatAnswer(correctAnswers)}`);
  }

  if (question.explanation) {
    lines.push("", "Explanation:", question.explanation);
  }

  return lines.join("\n").trim();
};

const appendExamParams = (
  params: URLSearchParams,
  examIds?: number[],
  filterActive?: boolean
) => {
  if (filterActive) {
    params.set("filter", "1");
    if (examIds && examIds.length > 0) {
      examIds.forEach((id) => params.append("exam_ids", String(id)));
    }
  }
};

export default function PracticeResultPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [storedResult, setStoredResult] = useState<StoredResult | null>(null);
  const [questions, setQuestions] = useState<ResultQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "wrong">("all");
  const [activeIndex, setActiveIndex] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const copyTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem(`practice:result:${sessionId}`);
    if (stored) {
      try {
        setStoredResult(JSON.parse(stored));
      } catch {
        setStoredResult(null);
      }
    }
  }, [sessionId]);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        window.clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let active = true;
    const loadResult = async () => {
    if (!storedResult?.lectureId && !storedResult?.examId) {
      setLoading(false);
      setError("Result data missing. Please submit again.");
      return;
    }

    try {
        const params = new URLSearchParams();
        params.set("includeAnswer", "true");
        if (storedResult.lectureId) {
          appendExamParams(params, storedResult.examIds, storedResult.filterActive);
        }
        const endpoint = storedResult.lectureId
          ? `/api/practice/lecture/${encodeURIComponent(
              storedResult.lectureId
            )}/result?${params.toString()}`
          : `/api/practice/exam/${encodeURIComponent(
              storedResult.examId ?? ""
            )}/result?${params.toString()}`;
        const response = await apiFetch<unknown>(endpoint, { cache: "no-store" });
        const parsed = lectureResultSchema.safeParse(response);
        if (!parsed.success) {
          throw new Error(CONNECTION_ERROR_MESSAGE);
        }
        if (!active) return;
        setQuestions((parsed.data.questions ?? []) as ResultQuestion[]);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadResult();

    return () => {
      active = false;
    };
  }, [storedResult?.lectureId, storedResult?.examId]);

  const resultItems = useMemo(() => {
    const items = storedResult?.items ?? [];
    return items
      .map(normalizeResultItem)
      .filter((item): item is ResultItem => Boolean(item));
  }, [storedResult?.items]);

  const itemsById = useMemo(() => {
    const map = new Map<string, ResultItem>();
    resultItems.forEach((item) => {
      map.set(item.questionId, item);
    });
    return map;
  }, [resultItems]);

  const combinedQuestions = useMemo(() => {
    if (!questions.length) return [];
    return questions.map((question) => ({
      ...question,
      result: itemsById.get(String(question.questionId)),
    }));
  }, [questions, itemsById]);

  const filteredQuestions = useMemo(() => {
    if (tab === "all") return combinedQuestions;
    return combinedQuestions.filter((question) => question.result?.isCorrect === false);
  }, [combinedQuestions, tab]);

  const wrongCount = useMemo(
    () =>
      combinedQuestions.filter((question) => question.result?.isCorrect === false)
        .length,
    [combinedQuestions]
  );

  const showCopyToast = useCallback((questionId: string, message: string) => {
    setCopiedId(questionId);
    setCopyMessage(message);
    if (copyTimeoutRef.current) {
      window.clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = window.setTimeout(() => {
      setCopiedId(null);
      setCopyMessage(null);
    }, 2000);
  }, []);

  const handleCopy = useCallback(
    async (question: ResultQuestion, result: ResultItem | undefined, index: number) => {
      const textPayload = buildCopyText({ question, result, index });
      const imageUrl = getPrimaryImageUrl(question);
      const notifySuccess = () =>
        showCopyToast(String(question.questionId), `Copied question ${index + 1}.`);
      const notifyFailure = () =>
        showCopyToast(String(question.questionId), "Copy failed.");

      if (typeof navigator === "undefined" || !navigator.clipboard) {
        notifyFailure();
        return;
      }

      if (
        imageUrl &&
        typeof navigator.clipboard.write === "function" &&
        typeof ClipboardItem !== "undefined"
      ) {
        try {
          const response = await fetch(imageUrl);
          const blob = await response.blob();
          const dataUrl = await readBlobAsDataUrl(blob);
          const htmlText = escapeHtml(textPayload).replace(/\n/g, "<br>");
          const htmlPayload = `<p>${htmlText}</p><img src="${dataUrl}" alt="question image">`;
          const items: Record<string, Blob> = {
            "text/plain": new Blob([textPayload], { type: "text/plain" }),
            "text/html": new Blob([htmlPayload], { type: "text/html" }),
          };
          if (blob.type) {
            items[blob.type] = blob;
          }
          await navigator.clipboard.write([new ClipboardItem(items)]);
          notifySuccess();
          return;
        } catch {
          // fallback to plain text
        }
      }

      try {
        await navigator.clipboard.writeText(textPayload);
        notifySuccess();
      } catch {
        notifyFailure();
      }
    },
    [showCopyToast]
  );

  const scrollToQuestion = useCallback((questionId: string | number) => {
    if (typeof document === "undefined") return;
    const element = document.getElementById(`result-question-${questionId}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  const focusQuestion = useCallback(
    (index: number) => {
      if (index < 0 || index >= filteredQuestions.length) return;
      setActiveIndex(index);
    },
    [filteredQuestions]
  );

  useEffect(() => {
    if (!filteredQuestions.length) return;
    if (activeIndex >= filteredQuestions.length) {
      setActiveIndex(0);
    }
  }, [activeIndex, filteredQuestions.length]);

  useEffect(() => {
    if (!filteredQuestions.length) return;
    const question = filteredQuestions[activeIndex];
    if (!question) return;
    scrollToQuestion(question.questionId);
  }, [activeIndex, filteredQuestions, scrollToQuestion]);

  const handleKeyboard = useCallback(
    (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) {
        return;
      }
      if (!filteredQuestions.length) return;
      const key = event.key.toLowerCase();
      if (key === "arrowright" || key === "j") {
        focusQuestion(Math.min(activeIndex + 1, filteredQuestions.length - 1));
      }
      if (key === "arrowleft" || key === "k") {
        focusQuestion(Math.max(activeIndex - 1, 0));
      }
    },
    [activeIndex, filteredQuestions.length, focusQuestion]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboard);
    return () => window.removeEventListener("keydown", handleKeyboard);
  }, [handleKeyboard]);

  const summary = storedResult?.summary?.all;
  const total = summary?.total ?? resultItems.length;
  const answered =
    summary?.answered ??
    resultItems.filter((item) => item.isAnswered || item.userAnswer).length;
  const correct = summary?.correct ?? resultItems.filter((item) => item.isCorrect).length;

  if (loading) {
    return (
      <div className="min-h-screen px-4 py-10">
        <div className="mx-auto w-full max-w-7xl space-y-6">
          <div className="h-10 w-40 animate-pulse rounded-full bg-muted" />
          <div className="h-32 animate-pulse rounded-3xl bg-muted" />
          <div className="h-64 animate-pulse rounded-3xl bg-muted" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen px-4 py-10">
        <div className="mx-auto w-full max-w-5xl">
          <Card className="border border-danger/30 bg-danger/10">
            <CardContent className="space-y-2 p-6">
              <p className="text-lg font-semibold text-foreground">Unable to load results</p>
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button onClick={() => router.back()} className="mt-4">
                Go back
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-10">
      <div className="mx-auto w-full max-w-7xl space-y-8">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Result
          </p>
          <h1 className="text-3xl font-semibold text-foreground">Session summary</h1>
          <p className="text-sm text-muted-foreground">
            Review your answers and revisit incorrect questions.
          </p>
        </div>

        <ResultSummary total={total} answered={answered} correct={correct} />

        <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="inline-flex rounded-full border border-border/70 bg-muted/70 p-1 text-sm">
                <button
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    tab === "all"
                      ? "bg-primary text-primary-foreground shadow-soft"
                      : "text-muted-foreground"
                  }`}
                  onClick={() => {
                    setTab("all");
                    setActiveIndex(0);
                  }}
                  type="button"
                >
                  All
                </button>
                <button
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    tab === "wrong"
                      ? "bg-primary text-primary-foreground shadow-soft"
                      : "text-muted-foreground"
                  }`}
                  onClick={() => {
                    setTab("wrong");
                    setActiveIndex(0);
                  }}
                  type="button"
                >
                  Wrong only
                </button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => focusQuestion(activeIndex - 1)}
                  disabled={activeIndex === 0 || filteredQuestions.length === 0}
                >
                  <ArrowLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  size="sm"
                  onClick={() => focusQuestion(activeIndex + 1)}
                  disabled={
                    filteredQuestions.length === 0 ||
                    activeIndex >= filteredQuestions.length - 1
                  }
                >
                  Next
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {filteredQuestions.length === 0 ? (
              <Card className="border border-border/70 bg-card/90">
                <CardContent className="space-y-2 p-6">
                  <p className="text-sm font-semibold text-foreground">
                    No questions in this view.
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Try switching back to the full list to continue reviewing.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-6">
                {filteredQuestions.map((question, index) => {
                  const result = question.result;
                  const isCorrect = result?.isCorrect;
                  const userAnswer = result?.userAnswer;
                  const correctAnswers =
                    question.correctChoiceNumbers ??
                    (Array.isArray(result?.correctAnswer) ? result?.correctAnswer : []);
                  const correctAnswerText =
                    question.correctAnswerText ?? result?.correctAnswerText ?? null;
                  const statusVariant =
                    isCorrect === true
                      ? "success"
                      : isCorrect === false
                        ? "danger"
                        : "neutral";
                  const statusLabel =
                    isCorrect === true
                      ? "Correct"
                      : isCorrect === false
                        ? "Wrong"
                        : "Pending";
                  const isActive = index === activeIndex;
                  const { text: stemText, images: stemImages } = parseStemContent(
                    question.stem ?? ""
                  );
                  const imageCandidates = [
                    resolveImageUrl(question.imageUrl ?? question.image),
                    ...stemImages.map((image) => resolveImageUrl(image)),
                  ].filter((value): value is string => Boolean(value));
                  const questionImages = Array.from(new Set(imageCandidates));
                  return (
                    <Card
                      key={question.questionId}
                      id={`result-question-${question.questionId}`}
                      className={`scroll-mt-24 border border-border/70 bg-card/90 ${
                        isActive ? "ring-2 ring-primary/30" : ""
                      }`}
                    >
                      <CardContent className="space-y-5 p-6">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                              Question {index + 1} of {filteredQuestions.length}
                            </p>
                            <div className="flex items-center gap-2">
                              <Badge variant={statusVariant}>{statusLabel}</Badge>
                              {!result?.isAnswered && (
                                <Badge variant="neutral">Unanswered</Badge>
                              )}
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleCopy(question, result, index)}
                            className="rounded-full"
                          >
                            {copiedId === String(question.questionId) ? (
                              <Check className="h-4 w-4" />
                            ) : (
                              <Copy className="h-4 w-4" />
                            )}
                            {copiedId === String(question.questionId) ? "Copied" : "Copy"}
                          </Button>
                        </div>

                        <div className="space-y-3">
                          <p className="text-base leading-relaxed text-foreground">
                            {stemText || "No prompt available."}
                          </p>
                          {questionImages.length > 0 && (
                            <div className="grid gap-3 sm:grid-cols-2">
                              {questionImages.map((src, imageIndex) => (
                                <img
                                  key={`${question.questionId}-image-${imageIndex}`}
                                  src={src}
                                  alt="Question visual"
                                  className="max-h-96 w-full rounded-xl border border-border/60 object-contain"
                                />
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="grid gap-2 rounded-xl border border-border/60 bg-muted/50 px-4 py-3 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-muted-foreground">Your answer</span>
                            <span className="font-semibold text-foreground">
                              {formatAnswer(userAnswer)}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-muted-foreground">Correct answer</span>
                            <span className="font-semibold text-foreground">
                              {question.isShortAnswer
                                ? formatAnswer(correctAnswerText)
                                : formatAnswer(correctAnswers)}
                            </span>
                          </div>
                        </div>

                        {question.isShortAnswer ? (
                          isCorrect === null ? (
                            <p className="text-xs text-muted-foreground">
                              Short answers may require manual grading.
                            </p>
                          ) : null
                        ) : (
                          <div className="space-y-2 text-sm">
                            <div className="space-y-2">
                              {(question.choices ?? []).map((choice, choiceIndex) => {
                                const choiceId =
                                  typeof choice.number === "number"
                                    ? choice.number
                                    : choiceIndex + 1;
                                const isUserChoice = Array.isArray(userAnswer)
                                  ? userAnswer.includes(choiceId)
                                  : false;
                                const isCorrectChoice = Array.isArray(correctAnswers)
                                  ? correctAnswers.includes(choiceId)
                                  : false;
                                const choiceImage = resolveImageUrl(
                                  choice.imageUrl ?? choice.image
                                );
                                return (
                                  <div
                                    key={choiceId}
                                    className={`rounded-xl border px-4 py-3 ${
                                      isCorrectChoice
                                        ? "border-success/50 bg-success/10"
                                        : isUserChoice
                                          ? "border-danger/40 bg-danger/10"
                                          : "border-border/70 bg-card"
                                    }`}
                                  >
                                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                      {choiceId}
                                    </div>
                                    <p className="text-sm text-foreground">
                                      {choice.content ?? "Choice"}
                                    </p>
                                    {choiceImage && (
                                      <img
                                        src={choiceImage}
                                        alt={`Choice ${choiceId}`}
                                        className="mt-2 max-h-48 rounded-lg border border-border/60 object-contain"
                                      />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {question.explanation && (
                          <details className="rounded-xl border border-border/70 bg-muted/60 px-4 py-3 text-sm">
                            <summary className="cursor-pointer font-semibold text-foreground">
                              Explanation
                            </summary>
                            <p className="mt-2 text-muted-foreground">
                              {question.explanation}
                            </p>
                          </details>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>

          <aside className="space-y-4 xl:sticky xl:top-24">
            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Review tools
                </p>
                <div className="grid gap-2 text-sm">
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>View</span>
                    <span className="font-semibold text-foreground">
                      {tab === "all" ? "All questions" : "Wrong only"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>Questions in view</span>
                    <span className="font-semibold text-foreground">
                      {filteredQuestions.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>Wrong answers</span>
                    <span className="font-semibold text-foreground">{wrongCount}</span>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setTab("wrong");
                    setActiveIndex(0);
                  }}
                  disabled={wrongCount === 0}
                >
                  Retry wrong answers
                </Button>
              </CardContent>
            </Card>

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Question navigator
                </p>
                {filteredQuestions.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No questions to jump to.</p>
                ) : (
                  <div className="grid grid-cols-6 gap-2">
                    {filteredQuestions.map((question, index) => {
                      const result = question.result;
                      const isCorrect = result?.isCorrect;
                      const isActive = index === activeIndex;
                      return (
                        <button
                          key={question.questionId}
                          type="button"
                          onClick={() => focusQuestion(index)}
                          className={`relative flex h-10 w-10 items-center justify-center rounded-xl border text-sm font-semibold transition ${
                            isActive
                              ? "border-primary bg-primary text-primary-foreground shadow-soft"
                              : isCorrect === true
                                ? "border-success/40 bg-success/20 text-success"
                                : isCorrect === false
                                  ? "border-danger/40 bg-danger/10 text-danger"
                                  : "border-border/70 bg-card text-muted-foreground hover:bg-muted"
                          }`}
                        >
                          {index + 1}
                        </button>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>

      {copyMessage && (
        <div className="fixed bottom-6 left-1/2 z-50 w-[min(90vw,360px)] -translate-x-1/2 rounded-full bg-success px-4 py-2 text-center text-sm font-semibold text-white shadow-float">
          {copyMessage}
        </div>
      )}
    </div>
  );
}
