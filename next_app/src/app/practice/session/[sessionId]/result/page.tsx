"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Copy, ImageIcon } from "lucide-react";

import { apiFetch } from "@/lib/http";
import { resolveImageUrl } from "@/lib/image";
import { useLanguage } from "@/context/LanguageContext";
import { ResultSummary } from "@/components/practice/ResultSummary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  AnswerPayload,
  lectureResultSchema,
  PracticeQuestion,
} from "@/components/practice/types";
import {
  getQuestionDetail,
  updateQuestion,
  type ManageChoice,
  type ManageQuestionDetail,
} from "@/lib/api/manage";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";

type StoredResult = {
  lectureId?: string;
  lectureTitle?: string;
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

type EditableChoice = {
  number: number;
  content: string;
  isCorrect: boolean;
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

const stripStemMarkdownForDisplay = (value?: string | null) => {
  if (!value) {
    return "";
  }
  return value.replace(MARKDOWN_IMAGE_REGEX, "").replace(/\r\n?/g, "\n").trim();
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

const getManageChoiceNumber = (choice: ManageChoice, index: number) =>
  typeof choice.number === "number"
    ? choice.number
    : typeof choice.choiceNumber === "number"
      ? choice.choiceNumber
      : index + 1;

const sortManageChoices = (choices: ManageChoice[]) =>
  [...choices].sort((left, right) => {
    const leftNumber = getManageChoiceNumber(left, 0);
    const rightNumber = getManageChoiceNumber(right, 0);
    return leftNumber - rightNumber;
  });

const toEditableChoicesFromManage = (choices: ManageChoice[]): EditableChoice[] =>
  sortManageChoices(choices).map((choice, index) => ({
    number: getManageChoiceNumber(choice, index),
    content: choice.content ?? "",
    isCorrect: Boolean(choice.isCorrect),
  }));

export default function PracticeResultPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [storedResult, setStoredResult] = useState<StoredResult | null>(null);
  const [storageReady, setStorageReady] = useState(false);
  const [questions, setQuestions] = useState<ResultQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "wrong">("all");
  const [activeIndex, setActiveIndex] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const copyTimeoutRef = useRef<number | null>(null);

  // --- Edit state ---
  const [isEditMode, setIsEditMode] = useState(false);
  const [loadingEditor, setLoadingEditor] = useState(false);
  const [savingEditor, setSavingEditor] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccess, setEditSuccess] = useState<string | null>(null);
  const [questionDetail, setQuestionDetail] = useState<ManageQuestionDetail | null>(null);
  const [editedStem, setEditedStem] = useState("");
  const [editedChoices, setEditedChoices] = useState<EditableChoice[]>([]);
  const [editedCorrectAnswerText, setEditedCorrectAnswerText] = useState("");
  const latestEditQuestionIdRef = useRef<string | null>(null);
  const [showCropImage, setShowCropImage] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setStorageReady(false);
    setStoredResult(null);
    setQuestions([]);
    setError(null);
    setLoading(true);
    const stored = sessionStorage.getItem(`practice:result:${sessionId}`);
    if (stored) {
      try {
        setStoredResult(JSON.parse(stored));
      } catch {
        setStoredResult(null);
      }
    }
    setStorageReady(true);
  }, [sessionId]);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        window.clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    let active = true;
    const loadResult = async () => {
      setLoading(true);
      setError(null);
      const hasExamSet = Array.isArray(storedResult?.examIds) && storedResult.examIds.length > 0;
      if (!storedResult?.lectureId && !storedResult?.examId && !hasExamSet) {
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
        if (!storedResult.lectureId && !storedResult.examId && hasExamSet) {
          for (const examId of storedResult.examIds ?? []) {
            params.append("exam_ids", String(examId));
          }
        }
        const endpoint = storedResult.lectureId
          ? `/api/practice/lecture/${encodeURIComponent(
            storedResult.lectureId
          )}/result?${params.toString()}`
          : storedResult.examId
            ? `/api/practice/exam/${encodeURIComponent(
              storedResult.examId
            )}/result?${params.toString()}`
            : `/api/practice/exam-set/result?${params.toString()}`;
        const response = await apiFetch<unknown>(endpoint, { cache: "no-store" });
        const parsed = lectureResultSchema.safeParse(response);
        if (!parsed.success) {
          throw new Error(CONNECTION_ERROR_MESSAGE);
        }
        if (!active) return;
        setQuestions((parsed.data.questions ?? []) as ResultQuestion[]);
        setError(null);
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
  }, [
    storageReady,
    storedResult?.lectureId,
    storedResult?.examId,
    storedResult?.examIds,
    storedResult?.filterActive,
  ]);

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
        showCopyToast(String(question.questionId), t("practiceResult.copied"));
      const notifyFailure = () =>
        showCopyToast(String(question.questionId), t("practiceResult.copyFailed"));

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
    [showCopyToast, t]
  );

  const focusQuestion = useCallback(
    (index: number) => {
      if (index < 0 || index >= filteredQuestions.length) return;
      setActiveIndex(index);
      // Reset edit mode on navigation
      setIsEditMode(false);
      setShowCropImage(false);
      setEditError(null);
      setEditSuccess(null);
      setQuestionDetail(null);
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
    setShowCropImage(false);
  }, [sessionId, tab, activeIndex]);

  // --- Edit handlers ---
  const handleEnterEditMode = useCallback(async () => {
    const currentQuestion = filteredQuestions[activeIndex];
    if (!currentQuestion) return;
    const targetQuestionId = String(currentQuestion.questionId);
    latestEditQuestionIdRef.current = targetQuestionId;
    setLoadingEditor(true);
    setEditError(null);
    setEditSuccess(null);

    try {
      const detail = await getQuestionDetail(targetQuestionId);
      if (latestEditQuestionIdRef.current !== targetQuestionId) return;
      setQuestionDetail(detail);
      setEditedStem(detail.content ?? currentQuestion.stem ?? "");
      setEditedChoices(toEditableChoicesFromManage(detail.choices));
      setEditedCorrectAnswerText(
        detail.correctAnswerText ?? detail.answer ?? ""
      );
      setIsEditMode(true);
    } catch (err) {
      if (latestEditQuestionIdRef.current !== targetQuestionId) return;
      setEditError(
        err instanceof Error ? err.message : "문제 정보를 불러오는 데 실패했습니다."
      );
    } finally {
      if (latestEditQuestionIdRef.current === targetQuestionId) {
        setLoadingEditor(false);
      }
    }
  }, [filteredQuestions, activeIndex]);

  const handleCancelEdit = useCallback(() => {
    setIsEditMode(false);
    setEditError(null);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!questionDetail) {
      setEditError("문제 정보를 불러오는 데 실패했습니다.");
      return;
    }
    const currentQuestion = filteredQuestions[activeIndex];
    if (!currentQuestion) return;
    const targetQuestionId = String(currentQuestion.questionId);
    setSavingEditor(true);
    setEditError(null);
    setEditSuccess(null);

    try {
      const type = questionDetail.type || "multiple_choice";
      const choiceContentByNumber = new Map(
        editedChoices.map((choice) => [choice.number, choice])
      );
      const existingChoices = sortManageChoices(questionDetail.choices);
      const choicesPayload =
        type === "short_answer"
          ? []
          : existingChoices.map((choice, index) => {
            const number = getManageChoiceNumber(choice, index);
            const edited = choiceContentByNumber.get(number);
            return {
              id: choice.id,
              number,
              content: edited?.content ?? choice.content ?? "",
              isCorrect: edited?.isCorrect ?? Boolean(choice.isCorrect),
              imagePath: choice.imagePath ?? null,
            };
          });

      const saved = await updateQuestion(questionDetail.id, {
        content: editedStem,
        explanation: questionDetail.explanation ?? "",
        type,
        lectureId: questionDetail.lectureId ?? null,
        correctAnswerText:
          type === "short_answer" ? editedCorrectAnswerText : null,
        choices: choicesPayload,
      });
      if (latestEditQuestionIdRef.current !== targetQuestionId) return;

      // Update local questions state
      const nextChoices =
        type === "short_answer"
          ? []
          : sortManageChoices(saved.choices).map((choice, idx) => ({
            number: getManageChoiceNumber(choice, idx),
            content: choice.content ?? "",
            image: choice.imagePath ?? undefined,
          }));

      const newCorrectChoiceNumbers =
        type === "short_answer"
          ? []
          : sortManageChoices(saved.choices)
            .filter((c) => c.isCorrect)
            .map((c, idx) => getManageChoiceNumber(c, idx));

      setQuestions((prev) =>
        prev.map((item) =>
          String(item.questionId) === targetQuestionId
            ? {
              ...item,
              stem: saved.content ?? editedStem,
              choices: nextChoices,
              correctChoiceNumbers: newCorrectChoiceNumbers,
              correctAnswerText:
                type === "short_answer"
                  ? saved.correctAnswerText ?? editedCorrectAnswerText
                  : item.correctAnswerText,
            }
            : item
        )
      );

      // --- Re-grade this question against user's answer ---
      const resultItem = itemsById.get(targetQuestionId);
      if (resultItem && storedResult) {
        let newIsCorrect: boolean | null = null;
        if (type === "short_answer") {
          const newCorrectText = (saved.correctAnswerText ?? editedCorrectAnswerText ?? "").trim().toLowerCase();
          const userText = (typeof resultItem.userAnswer === "string" ? resultItem.userAnswer : "").trim().toLowerCase();
          if (newCorrectText && userText) {
            newIsCorrect = userText === newCorrectText;
          }
        } else {
          const userAnswer = resultItem.userAnswer;
          if (Array.isArray(userAnswer) && userAnswer.length > 0) {
            const userSet = new Set(userAnswer.map(Number));
            const correctSet = new Set(newCorrectChoiceNumbers);
            newIsCorrect =
              userSet.size === correctSet.size &&
              [...userSet].every((v) => correctSet.has(v));
          }
        }

        // Update storedResult items + summary
        setStoredResult((prev) => {
          if (!prev) return prev;
          const updatedItems = (prev.items ?? []).map((raw) => {
            if (!raw || typeof raw !== "object") return raw;
            const record = raw as Record<string, unknown>;
            const rawId = record.questionId ?? record.question_id;
            if (String(rawId) !== targetQuestionId) return raw;
            if (typeof newIsCorrect !== "boolean") {
              return record;
            }
            return { ...record, isCorrect: newIsCorrect };
          });

          // Recount correct answers
          let correctCount = 0;
          for (const raw of updatedItems) {
            if (raw && typeof raw === "object") {
              const r = raw as Record<string, unknown>;
              if (r.isCorrect === true) correctCount++;
            }
          }

          const updatedResult: StoredResult = {
            ...prev,
            items: updatedItems,
          };
          if (typeof newIsCorrect === "boolean") {
            updatedResult.summary = {
              ...(prev.summary ?? {}),
              all: {
                ...(prev.summary?.all ?? {}),
                correct: correctCount,
              },
            };
          }

          // Persist to sessionStorage
          if (typeof window !== "undefined") {
            sessionStorage.setItem(
              `practice:result:${sessionId}`,
              JSON.stringify(updatedResult)
            );
          }
          return updatedResult;
        });
      }

      setQuestionDetail(saved);
      setIsEditMode(false);
      setEditSuccess("수정이 저장되었습니다.");
    } catch (err) {
      if (latestEditQuestionIdRef.current !== targetQuestionId) return;
      setEditError(
        err instanceof Error ? err.message : "저장에 실패했습니다."
      );
    } finally {
      if (latestEditQuestionIdRef.current === targetQuestionId) {
        setSavingEditor(false);
      }
    }
  }, [editedChoices, editedCorrectAnswerText, editedStem, filteredQuestions, activeIndex, questionDetail, itemsById, storedResult, sessionId]);

  const updateDraftChoice = useCallback((choiceNumber: number, value: string) => {
    setEditedChoices((prev) =>
      prev.map((choice) =>
        choice.number === choiceNumber ? { ...choice, content: value } : choice
      )
    );
  }, []);

  const toggleChoiceCorrect = useCallback((choiceNumber: number) => {
    setEditedChoices((prev) =>
      prev.map((choice) =>
        choice.number === choiceNumber
          ? { ...choice, isCorrect: !choice.isCorrect }
          : choice
      )
    );
  }, []);

  const handleKeyboard = useCallback(
    (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.isComposing) return;
      if (isEditMode) return;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (!filteredQuestions.length) return;
      const key = event.key.toLowerCase();

      if (event.ctrlKey && event.shiftKey && key >= "1" && key <= "9") {
        event.preventDefault();
        const targetIndex = Number(key) - 1;
        if (targetIndex >= 0 && targetIndex < filteredQuestions.length) {
          focusQuestion(targetIndex);
        }
        return;
      }

      if (key === "arrowright" || key === "j") {
        focusQuestion(Math.min(activeIndex + 1, filteredQuestions.length - 1));
      }
      if (key === "arrowleft" || key === "k") {
        focusQuestion(Math.max(activeIndex - 1, 0));
      }
    },
    [activeIndex, filteredQuestions.length, focusQuestion, isEditMode]
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
        <div className="mx-auto w-full max-w-screen-xl space-y-6">
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
        <div className="mx-auto w-full max-w-screen-xl">
          <Card className="border border-danger/30 bg-danger/10">
            <CardContent className="space-y-2 p-6">
              <p className="text-lg font-semibold text-foreground">{t("practiceResult.errorLoad")}</p>
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button onClick={() => router.back()} className="mt-4">
                {t("practiceResult.goBack")}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const currentQuestion = filteredQuestions[activeIndex];

  return (
    <div className="min-h-screen px-4 py-10">
      <div className="mx-auto w-full max-w-screen-xl space-y-8">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {t("practiceResult.title")}
          </p>
          <h1 className="text-3xl font-semibold text-foreground">
            {storedResult?.lectureTitle || storedResult?.examTitle || t("practiceResult.sessionSummary")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("practiceResult.sessionSummaryDesc")}
          </p>
        </div>

        <ResultSummary total={total} answered={answered} correct={correct} />

        <div className="grid gap-8 xl:grid-cols-[1fr_320px]">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="inline-flex rounded-full border border-border/70 bg-muted/70 p-1 text-sm">
                <button
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${tab === "all"
                    ? "bg-primary text-primary-foreground shadow-soft"
                    : "text-muted-foreground"
                    }`}
                  onClick={() => {
                    setTab("all");
                    setActiveIndex(0);
                    setIsEditMode(false);
                    setShowCropImage(false);
                    setQuestionDetail(null);
                  }}
                  type="button"
                >
                  {t("practiceResult.all")}
                </button>
                <button
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${tab === "wrong"
                    ? "bg-primary text-primary-foreground shadow-soft"
                    : "text-muted-foreground"
                    }`}
                  onClick={() => {
                    setTab("wrong");
                    setActiveIndex(0);
                    setIsEditMode(false);
                    setShowCropImage(false);
                    setQuestionDetail(null);
                  }}
                  type="button"
                >
                  {t("practiceResult.wrongOnly")}
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
                  {t("practiceResult.previous")}
                </Button>
                <Button
                  size="sm"
                  onClick={() => focusQuestion(activeIndex + 1)}
                  disabled={
                    filteredQuestions.length === 0 ||
                    activeIndex >= filteredQuestions.length - 1
                  }
                >
                  {t("practiceResult.next")}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {editError && (
              <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
                {editError}
              </div>
            )}
            {editSuccess && (
              <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
                {editSuccess}
              </div>
            )}

            {filteredQuestions.length === 0 ? (
              <Card className="border border-border/70 bg-card/90">
                <CardContent className="space-y-2 p-6">
                  <p className="text-sm font-semibold text-foreground">
                    {t("practiceResult.noQuestions")}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {t("practiceResult.noQuestionsDesc")}
                  </p>
                </CardContent>
              </Card>
            ) : currentQuestion ? (
              (() => {
                const question = currentQuestion;
                const index = activeIndex;
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
                    ? t("practiceResult.status.correct")
                    : isCorrect === false
                      ? t("practiceResult.status.wrong")
                      : t("practiceResult.status.pending");
                const { images: stemImages } = parseStemContent(question.stem ?? "");
                const stemText = stripStemMarkdownForDisplay(question.stem ?? "");
                const imageCandidates = [
                  resolveImageUrl(question.imageUrl ?? question.image),
                  ...stemImages.map((image) => resolveImageUrl(image)),
                ].filter((value): value is string => Boolean(value));
                const questionImages = Array.from(new Set(imageCandidates));
                const detailMatchesCurrentQuestion =
                  questionDetail !== null &&
                  String(questionDetail.id) === String(question.questionId);
                const questionCropImage = resolveImageUrl(question.originalImageUrl);
                const referenceImage = detailMatchesCurrentQuestion
                  ? resolveImageUrl(questionDetail?.originalImageUrl) ?? questionCropImage
                  : questionCropImage;
                const isShortAnswerEditor =
                  questionDetail?.type === "short_answer" || Boolean(question.isShortAnswer);

                return (
                  <Card
                    key={question.questionId}
                    id={`result-question-${question.questionId}`}
                    className="border border-border/70 bg-card/90 ring-2 ring-primary/30"
                  >
                    <CardContent className="space-y-5 p-6">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-2">
                          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                            <span>
                              {t("practiceResult.question")} {index + 1} {t("practiceResult.of")} {filteredQuestions.length}
                            </span>
                            {question.examTitle && (
                              <>
                                <span>&bull;</span>
                                <span className="text-muted-foreground/80 lowercase tracking-normal bg-muted px-1.5 py-0.5 rounded-sm">
                                  {question.examTitle}
                                  {question.questionNumber ? ` - Q${question.questionNumber}` : ""}
                                </span>
                              </>
                            )}
                          </p>
                          <div className="flex items-center gap-2">
                            <Badge variant={statusVariant}>{statusLabel}</Badge>
                            {!result?.isAnswered && (
                              <Badge variant="neutral">{t("practiceResult.unanswered")}</Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
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
                            {copiedId === String(question.questionId) ? t("practiceResult.copied") : t("practiceResult.copy")}
                          </Button>
                          {!isEditMode && (
                            <Button
                              variant={showCropImage ? "secondary" : "outline"}
                              size="sm"
                              onClick={() => setShowCropImage((prev) => !prev)}
                              className="rounded-full"
                              disabled={!questionCropImage}
                            >
                              <ImageIcon className="h-4 w-4" />
                              {showCropImage ? "크롭 이미지 숨기기" : "크롭 이미지"}
                            </Button>
                          )}
                          {!isEditMode ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => { void handleEnterEditMode(); }}
                              disabled={loadingEditor}
                            >
                              {loadingEditor ? "불러오는 중..." : "수정"}
                            </Button>
                          ) : (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={handleCancelEdit}
                                disabled={savingEditor}
                              >
                                취소
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => { void handleSaveEdit(); }}
                                disabled={savingEditor}
                              >
                                {savingEditor ? "저장 중..." : "저장"}
                              </Button>
                            </>
                          )}
                        </div>
                      </div>

                      {isEditMode ? (
                        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,1fr)] items-start">
                          <div className="space-y-5">
                            <div className="space-y-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                문제 수정 모드
                              </p>
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm font-semibold text-foreground">
                                문제 내용
                              </label>
                              <Textarea
                                value={editedStem}
                                onChange={(event) => setEditedStem(event.target.value)}
                                className="min-h-[180px]"
                              />
                            </div>
                            {isShortAnswerEditor ? (
                              <div className="space-y-2">
                                <label className="text-sm font-semibold text-foreground">
                                  정답
                                </label>
                                <Input
                                  value={editedCorrectAnswerText}
                                  onChange={(event) =>
                                    setEditedCorrectAnswerText(event.target.value)
                                  }
                                  placeholder="정답 텍스트를 입력하세요"
                                />
                              </div>
                            ) : (
                              <div className="space-y-3">
                                {editedChoices.map((choice) => (
                                  <div key={`edit-choice-${choice.number}`} className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <label className="text-sm font-semibold text-foreground">
                                        선택지 {choice.number}
                                      </label>
                                      <button
                                        type="button"
                                        onClick={() => toggleChoiceCorrect(choice.number)}
                                        className={`rounded-md border px-2 py-0.5 text-xs font-semibold transition ${choice.isCorrect
                                          ? "border-success/50 bg-success/20 text-success"
                                          : "border-border/70 bg-card text-muted-foreground hover:bg-muted"
                                          }`}
                                      >
                                        {choice.isCorrect ? "✓ 정답" : "오답"}
                                      </button>
                                    </div>
                                    <Textarea
                                      value={choice.content}
                                      onChange={(event) =>
                                        updateDraftChoice(choice.number, event.target.value)
                                      }
                                      className="min-h-[96px]"
                                    />
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          <Card className="border border-border/70 bg-card/90 shadow-soft">
                            <CardContent className="space-y-3 p-6">
                              <p className="text-sm font-semibold text-foreground">
                                원본 이미지
                              </p>
                              {typeof referenceImage === "string" && referenceImage.length > 0 ? (
                                <img
                                  src={referenceImage}
                                  alt="원본 이미지"
                                  className="max-h-[640px] w-full rounded-xl border border-border/60 object-contain"
                                />
                              ) : (
                                <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-8 text-sm text-muted-foreground">
                                  원본 이미지가 없습니다
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        </div>
                      ) : (
                        <div className="grid gap-6 lg:grid-cols-2 items-start">
                          <div className="space-y-4">
                            <div className="space-y-3">
                              <p className="text-base leading-relaxed text-foreground whitespace-pre-wrap">
                                {stemText || t("practiceResult.noPrompt")}
                              </p>
                              {questionImages.length > 0 && (
                                <div className="grid gap-3 sm:grid-cols-2">
                                  {questionImages.map((src, imageIndex) => (
                                    <img
                                      key={`${question.questionId}-question-image-${imageIndex}`}
                                      src={src}
                                      alt="문제 이미지"
                                      className="max-h-96 w-full rounded-xl border border-border/60 object-contain"
                                    />
                                  ))}
                                </div>
                              )}
                              {showCropImage && questionCropImage && (
                                <div className="space-y-2">
                                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                    PDF 크롭 이미지
                                  </p>
                                  <img
                                    src={questionCropImage}
                                    alt="PDF 크롭 이미지"
                                    className="max-h-96 w-full rounded-xl border border-border/60 object-contain"
                                  />
                                </div>
                              )}
                            </div>
                            {question.explanation && (
                              <details className="rounded-xl border border-border/70 bg-muted/60 px-4 py-3 text-sm">
                                <summary className="cursor-pointer font-semibold text-foreground">
                                  {t("practiceResult.explanation")}
                                </summary>
                                <p className="mt-2 text-muted-foreground whitespace-pre-wrap">
                                  {question.explanation}
                                </p>
                              </details>
                            )}
                          </div>

                          <div className="space-y-4">
                            <div className="grid gap-2 rounded-xl border border-border/60 bg-muted/50 px-4 py-3 text-sm">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-muted-foreground">{t("practiceResult.yourAnswer")}</span>
                                <span className="font-semibold text-foreground">
                                  {formatAnswer(userAnswer)}
                                </span>
                              </div>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-muted-foreground">{t("practiceResult.correctAnswer")}</span>
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
                                  {t("practiceResult.manualGrading")}
                                </p>
                              ) : null
                            ) : (
                              <div className="space-y-2 text-sm">
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
                                      className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${isCorrectChoice
                                        ? "border-success/50 bg-success/10"
                                        : isUserChoice
                                          ? "border-danger/40 bg-danger/10"
                                          : "border-border/70 bg-card"
                                        }`}
                                    >
                                      <div className={`text-sm font-semibold shrink-0 ${isCorrectChoice || isUserChoice ? (isCorrectChoice ? "text-success" : "text-danger") : "text-muted-foreground"
                                        }`}
                                      >
                                        {choiceId}
                                      </div>
                                      <div className="flex-1 space-y-2">
                                        <p className="text-sm text-foreground">
                                          {choice.content ?? t("practiceResult.choice")}
                                        </p>
                                        {choiceImage && (
                                          <img
                                            src={choiceImage}
                                            alt={`${t("practiceResult.choice")} ${choiceId}`}
                                            className="mt-2 max-h-48 rounded-lg border border-border/60 object-contain"
                                          />
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })()
            ) : null}
          </div>

          <aside className="space-y-4 xl:sticky xl:top-24">
            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {t("practiceResult.reviewTools")}
                </p>
                <div className="grid gap-2 text-sm">
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>{t("practiceResult.view")}</span>
                    <span className="font-semibold text-foreground">
                      {tab === "all" ? t("practiceResult.allQuestions") : t("practiceResult.wrongOnly")}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>{t("practiceResult.questionsInView")}</span>
                    <span className="font-semibold text-foreground">
                      {filteredQuestions.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>{t("practiceResult.wrongAnswers")}</span>
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
                    setIsEditMode(false);
                    setShowCropImage(false);
                    setQuestionDetail(null);
                  }}
                  disabled={wrongCount === 0}
                >
                  {t("practiceResult.retryWrong")}
                </Button>
              </CardContent>
            </Card>

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {t("practiceResult.questionNavigator")}
                </p>
                {filteredQuestions.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t("practiceResult.noQuestionsToJump")}</p>
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
                          className={`relative flex h-10 w-10 items-center justify-center rounded-xl border text-sm font-semibold transition ${isActive
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
