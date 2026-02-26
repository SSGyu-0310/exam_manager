"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Check, CircleHelp, Flag, Loader2, Timer, XCircle } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import { apiFetch } from "@/lib/http";
import { resolveImageUrl } from "@/lib/image";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { QuestionView } from "@/components/practice/QuestionView";
import { ShortcutHelpDialog } from "@/components/practice/ShortcutHelpDialog";
import { SubmitDialog } from "@/components/practice/SubmitDialog";
import {
  AnswerPayload,
  PracticeChoice,
  lectureQuestionsResponseSchema,
  PracticeQuestion,
  sessionDetailSchema,
  submitResponseSchema,
} from "@/components/practice/types";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";
const PAGE_SIZE = 200;
const MARKDOWN_IMAGE_REGEX = /!\[[^\]]*]\(([^)]+)\)/g;

type ParsedStemContent = {
  text: string;
  images: string[];
};

type CopyLabels = {
  question: string;
  noPrompt: string;
  choices: string;
};

const parseStemContent = (value?: string | null): ParsedStemContent => {
  if (!value) {
    return { text: "", images: [] };
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
    text: cleaned.trim(),
    images,
  };
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

const collectQuestionImageUrls = (question: PracticeQuestion) => {
  const urls = new Set<string>();

  const directImage = resolveImageUrl(question.imageUrl ?? question.image);
  if (directImage) {
    urls.add(directImage);
  }

  const { images: stemImages } = parseStemContent(question.stem ?? "");
  stemImages.forEach((raw) => {
    const normalized = resolveImageUrl(raw);
    if (normalized) {
      urls.add(normalized);
    }
  });

  (question.choices ?? []).forEach((choice) => {
    const normalized = resolveImageUrl(choice.imageUrl ?? choice.image);
    if (normalized) {
      urls.add(normalized);
    }
  });

  return Array.from(urls);
};

const buildCopyTextPayload = ({
  question,
  index,
  labels,
}: {
  question: PracticeQuestion;
  index: number;
  labels: CopyLabels;
}) => {
  const { text: stemText } = parseStemContent(question.stem ?? "");
  const lines = [
    `${labels.question} ${index + 1}`,
    stemText || labels.noPrompt,
  ];

  if (!question.isShortAnswer && (question.choices ?? []).length > 0) {
    lines.push("", `${labels.choices}:`);
    (question.choices ?? []).forEach((choice, choiceIndex) => {
      const choiceId = getChoiceId(choice, choiceIndex);
      lines.push(`${choiceId}. ${choice.content ?? ""}`);
    });
  }

  return lines.join("\n").trim();
};


type SessionContext = {
  lectureId?: string;
  lectureTitle?: string;
  examId?: string;
  examTitle?: string;
  mode?: string;
  fallback?: boolean;
  warning?: string | null;
  source?: string;
  questionOrder?: number[];
  examIds?: number[];
  filterActive?: boolean;
};

type SubmitResult = {
  lectureId?: string;
  examId?: string;
  examTitle?: string;
  submittedAt?: string;
  summary?: unknown;
  items?: unknown[];
};

const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
};

const getChoiceId = (choice: { number?: number | null }, index: number) =>
  typeof choice.number === "number" ? choice.number : index + 1;

const isAnswerComplete = (payload?: AnswerPayload) => {
  if (!payload) return false;
  if (payload.type === "mcq") return payload.value.length > 0;
  if (payload.type === "short") return payload.value.trim().length > 0;
  return false;
};

const formatMode = (value?: string) => {
  if (!value) return "Practice";
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
};

const toOptionalString = (value: unknown): string | undefined => {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return undefined;
};

const areNumberArraysEqual = (
  left?: number[] | null,
  right?: number[] | null
) => {
  if (left === right) return true;
  if (!left || !right) return !left && !right;
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
};

const isPersistedSessionId = (value: string) => /^\d+$/.test(value);

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

const buildExamQuery = (examIds?: number[], filterActive?: boolean) => {
  const params = new URLSearchParams();
  appendExamParams(params, examIds, filterActive);
  const query = params.toString();
  return query ? `?${query}` : "";
};

export default function PracticeSessionPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const SOLVER_SHORTCUT_SECTIONS = [
    {
      title: t("practiceSession.shortcuts.navigation"),
      items: [
        { keys: "Arrow Left / Arrow Right", description: t("practiceSession.shortcuts.prevNext") },
        { keys: "J / K", description: t("practiceSession.shortcuts.prevNext") },
        { keys: "Ctrl+Shift+1-9", description: t("practiceSession.shortcuts.jumpQuestion") },
      ],
    },
    {
      title: t("practiceSession.shortcuts.answering"),
      items: [
        { keys: "1-5", description: t("practiceSession.shortcuts.selectChoice") },
        { keys: "Ctrl+Alt+V", description: t("practiceSession.shortcuts.bookmarkWin") },
        { keys: "Cmd+Shift+V", description: t("practiceSession.shortcuts.bookmarkMac") },
        { keys: "Ctrl/Cmd+Shift+C", description: t("practiceSession.shortcuts.copyQuestion") },
      ],
    },
    {
      title: t("practiceSession.shortcuts.session"),
      items: [
        { keys: "Ctrl/Cmd+Enter", description: t("practiceSession.shortcuts.submit") },
        { keys: "?", description: t("practiceSession.shortcuts.help") },
      ],
    },
  ];

  const [sessionContext, setSessionContext] = useState<SessionContext>({});
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [questionOrder, setQuestionOrder] = useState<number[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, AnswerPayload>>({});
  const [bookmarks, setBookmarks] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [loadMoreLoading, setLoadMoreLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [isQuestionEditing, setIsQuestionEditing] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const [resumeMessage, setResumeMessage] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    total: 0,
    offset: 0,
    limit: PAGE_SIZE,
    hasMore: false,
  });
  const questionTopRef = useRef<HTMLDivElement | null>(null);
  const previousQuestionIdRef = useRef<string | null>(null);
  const copyTimeoutRef = useRef<number | null>(null);
  const autoSaveTimerRef = useRef<number | null>(null);
  const autoSavePendingRef = useRef(false);
  const resumeTimerRef = useRef<number | null>(null);
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const currentIndexRef = useRef(currentIndex);
  currentIndexRef.current = currentIndex;
  const timerSecondsRef = useRef(timerSeconds);
  timerSecondsRef.current = timerSeconds;

  const isTimed = sessionContext.mode === "timed";

  const fallbackLectureId = useMemo(() => {
    if (sessionId?.startsWith("lecture-")) {
      return decodeURIComponent(sessionId.replace("lecture-", ""));
    }
    return null;
  }, [sessionId]);

  const fallbackExamId = useMemo(() => {
    if (sessionId?.startsWith("exam-")) {
      return decodeURIComponent(sessionId.replace("exam-", ""));
    }
    return null;
  }, [sessionId]);

  const fallbackExamIds = useMemo(() => {
    if (sessionId?.startsWith("examset-")) {
      const raw = decodeURIComponent(sessionId.replace("examset-", ""));
      return raw
        .split(",")
        .map((token) => Number(token.trim()))
        .filter((value) => Number.isFinite(value) && value > 0);
    }
    return [] as number[];
  }, [sessionId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem(`practice:session:${sessionId}`);
    if (stored) {
      try {
        setSessionContext(JSON.parse(stored));
      } catch {
        setSessionContext({});
      }
    }
  }, [sessionId]);

  useEffect(() => {
    if (!isTimed) {
      setTimerSeconds(0);
      return;
    }
    const timerId = setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timerId);
  }, [isTimed]);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        window.clearTimeout(copyTimeoutRef.current);
      }
      if (autoSaveTimerRef.current) {
        window.clearTimeout(autoSaveTimerRef.current);
      }
      if (resumeTimerRef.current) {
        window.clearTimeout(resumeTimerRef.current);
      }
    };
  }, []);

  // ---- Auto-save logic ----
  const flushAutoSave = useCallback(async () => {
    if (!isPersistedSessionId(sessionId)) return;
    const currentAnswers = answersRef.current;
    const idx = currentIndexRef.current;
    const elapsed = timerSecondsRef.current;
    try {
      setAutoSaveStatus("saving");
      await apiFetch<unknown>(
        `/api/practice/sessions/${encodeURIComponent(sessionId)}/progress`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            currentQuestionIndex: idx,
            answers: currentAnswers,
            elapsedSeconds: elapsed,
          }),
        }
      );
      autoSavePendingRef.current = false;
      setAutoSaveStatus("saved");
    } catch {
      setAutoSaveStatus("error");
    }
  }, [sessionId]);

  // Debounced auto-save on answers or currentIndex change
  useEffect(() => {
    if (!isPersistedSessionId(sessionId)) return;
    if (!sessionLoadedRef.current) return;
    autoSavePendingRef.current = true;
    if (autoSaveTimerRef.current) {
      window.clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = window.setTimeout(() => {
      void flushAutoSave();
    }, 3000);
    return () => {
      if (autoSaveTimerRef.current) {
        window.clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [answers, currentIndex, sessionId, flushAutoSave]);

  // Flush on page unload
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (!autoSavePendingRef.current) return;
      if (!isPersistedSessionId(sessionId)) return;
      const currentAnswers = answersRef.current;
      const idx = currentIndexRef.current;
      const elapsed = timerSecondsRef.current;
      const body = JSON.stringify({
        currentQuestionIndex: idx,
        answers: currentAnswers,
        elapsedSeconds: elapsed,
      });
      const url = `/api/proxy/api/practice/sessions/${encodeURIComponent(sessionId)}/progress`;
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrf_access_token="))
        ?.split("=")[1];

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (csrfToken) {
        headers["X-CSRF-TOKEN"] = csrfToken;
      }

      if (typeof fetch === "function") {
        void fetch(url, {
          method: "PATCH",
          body,
          keepalive: true,
          headers,
          credentials: "include",
        }).catch(() => {
          if (typeof navigator.sendBeacon === "function") {
            navigator.sendBeacon(
              url,
              new Blob([body], { type: "application/json" })
            );
          }
        });
        return;
      }

      if (typeof navigator.sendBeacon === "function") {
        navigator.sendBeacon(
          url,
          new Blob([body], { type: "application/json" })
        );
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sessionId]);

  // Clear resume message after delay
  useEffect(() => {
    if (!resumeMessage) return;
    resumeTimerRef.current = window.setTimeout(() => {
      setResumeMessage(null);
    }, 5000);
    return () => {
      if (resumeTimerRef.current) {
        window.clearTimeout(resumeTimerRef.current);
      }
    };
  }, [resumeMessage]);

  const fetchLectureQuestions = useCallback(
    async (
      lectureId: string,
      offset = 0,
      examIds?: number[],
      filterActive?: boolean
    ) => {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));
      appendExamParams(params, examIds, filterActive);
      const response = await apiFetch<unknown>(
        `/api/practice/lecture/${encodeURIComponent(
          lectureId
        )}/questions?${params.toString()}`,
        { cache: "no-store" }
      );
      const parsed = lectureQuestionsResponseSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error(CONNECTION_ERROR_MESSAGE);
      }
      const data = parsed.data;
      return {
        questions: data.questions ?? [],
        total: data.total ?? 0,
        offset: data.offset ?? offset,
        limit: data.limit ?? PAGE_SIZE,
      };
    },
    []
  );

  const fetchExamQuestions = useCallback(
    async (examId: string, offset = 0) => {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));
      const response = await apiFetch<unknown>(
        `/api/practice/exam/${encodeURIComponent(examId)}/questions?${params.toString()}`,
        { cache: "no-store" }
      );
      const parsed = lectureQuestionsResponseSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error(CONNECTION_ERROR_MESSAGE);
      }
      const data = parsed.data;
      return {
        questions: data.questions ?? [],
        total: data.total ?? 0,
        offset: data.offset ?? offset,
        limit: data.limit ?? PAGE_SIZE,
      };
    },
    []
  );

  const fetchExamSetQuestions = useCallback(
    async (examIds: number[], offset = 0) => {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));
      examIds.forEach((id) => params.append("exam_ids", String(id)));
      const response = await apiFetch<unknown>(
        `/api/practice/exam-set/questions?${params.toString()}`,
        { cache: "no-store" }
      );
      const parsed = lectureQuestionsResponseSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error(CONNECTION_ERROR_MESSAGE);
      }
      const data = parsed.data;
      return {
        questions: data.questions ?? [],
        total: data.total ?? 0,
        offset: data.offset ?? offset,
        limit: data.limit ?? PAGE_SIZE,
      };
    },
    []
  );

  const sessionLoadedRef = useRef(false);

  useEffect(() => {
    let active = true;

    const loadSession = async () => {
      if (sessionLoadedRef.current) return;

      setLoading(true);
      setError(null);
      setSubmitError(null);

      let lectureId = sessionContext.lectureId ?? fallbackLectureId ?? undefined;
      let examId = sessionContext.examId ?? fallbackExamId ?? undefined;
      let examIds = sessionContext.examIds ?? fallbackExamIds;
      let order = sessionContext.questionOrder ?? [];
      const filterActive = sessionContext.filterActive;

      if (
        !lectureId &&
        !examId &&
        sessionId &&
        isPersistedSessionId(sessionId)
      ) {
        try {
          const response = await apiFetch<unknown>(
            `/api/practice/sessions/${encodeURIComponent(sessionId)}`,
            { cache: "no-store" }
          );
          const parsed = sessionDetailSchema.safeParse(response);
          if (parsed.success) {
            // Redirect if session is already finished
            if (parsed.data.finishedAt) {
              router.replace(`/practice/session/${sessionId}/result`);
              return;
            }

            lectureId = toOptionalString(parsed.data.lectureId);
            order = parsed.data.questionOrder ?? [];
            const newExamIds = parsed.data.examIds;

            // Restore draft answers from server
            const serverItems = parsed.data.items;
            if (serverItems && serverItems.length > 0) {
              const restoredAnswers: Record<string, AnswerPayload> = {};
              for (const item of serverItems) {
                if (!item.isAnswered || !item.answer) continue;
                const answerData = item.answer;
                if (
                  answerData &&
                  typeof answerData === "object" &&
                  "type" in answerData &&
                  "value" in answerData
                ) {
                  restoredAnswers[String(item.questionId)] =
                    answerData as AnswerPayload;
                }
              }
              if (Object.keys(restoredAnswers).length > 0) {
                setAnswers(restoredAnswers);
                setResumeMessage(t("practiceSession.resumeMessage"));
              }
            }

            // Restore current question index
            const savedIndex = parsed.data.currentQuestionIndex;
            if (
              typeof savedIndex === "number" &&
              savedIndex > 0
            ) {
              setCurrentIndex(savedIndex);
            }

            setSessionContext((prev) => {
              const nextLectureId = lectureId ?? prev.lectureId;
              const nextExamIds = newExamIds ?? prev.examIds;
              const nextExamTitle = parsed.data.examTitle ?? prev.examTitle;
              const nextLectureTitle =
                parsed.data.lectureTitle ?? prev.lectureTitle;
              const nextMode = parsed.data.mode ?? prev.mode;

              if (
                prev.lectureId === nextLectureId &&
                prev.examTitle === nextExamTitle &&
                prev.lectureTitle === nextLectureTitle &&
                prev.mode === nextMode &&
                areNumberArraysEqual(prev.examIds, nextExamIds)
              ) {
                return prev;
              }

              return {
                ...prev,
                lectureId: nextLectureId,
                examIds: nextExamIds,
                examTitle: nextExamTitle,
                lectureTitle: nextLectureTitle,
                mode: nextMode,
              };
            });
            examIds = newExamIds ?? examIds;
          }
        } catch {
          setSessionContext((prev) => ({
            ...prev,
            warning: prev.warning ?? CONNECTION_ERROR_MESSAGE,
          }));
        }
      }

      if (!lectureId && !examId && (!examIds || examIds.length === 0)) {
        setError("Unable to resolve content for this session.");
        setLoading(false);
        return;
      }

      try {
        const page = lectureId
          ? await fetchLectureQuestions(lectureId, 0, examIds, filterActive)
          : examId
            ? await fetchExamQuestions(examId, 0)
            : await fetchExamSetQuestions(examIds, 0);
        if (!active) return;
        sessionLoadedRef.current = true;
        setQuestions(page.questions);
        setQuestionOrder(order);
        setPagination({
          total: page.total,
          offset: page.offset,
          limit: page.limit,
          hasMore: page.total > page.questions.length,
        });
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadSession();

    return () => {
      active = false;
    };
  }, [
    fetchLectureQuestions,
    fetchExamQuestions,
    fetchExamSetQuestions,
    fallbackLectureId,
    fallbackExamId,
    fallbackExamIds,
    sessionContext.lectureId,
    sessionContext.examId,
    sessionId,
    sessionContext.questionOrder,
    sessionContext.examIds,
    sessionContext.filterActive,
    router,
    t,
  ]);

  const orderedQuestions = useMemo(() => {
    if (!questionOrder.length) return questions;
    const map = new Map(questions.map((question) => [String(question.questionId), question]));
    const ordered = questionOrder
      .map((id) => map.get(String(id)))
      .filter((item): item is PracticeQuestion => Boolean(item));
    const remaining = questions.filter(
      (question) => !questionOrder.includes(Number(question.questionId))
    );
    return [...ordered, ...remaining];
  }, [questions, questionOrder]);

  useEffect(() => {
    if (orderedQuestions.length === 0) {
      return;
    }
    if (currentIndex >= orderedQuestions.length) {
      setCurrentIndex(0);
    }
  }, [currentIndex, orderedQuestions.length]);

  const currentQuestion = orderedQuestions[currentIndex];
  const currentQuestionId = currentQuestion
    ? String(currentQuestion.questionId)
    : null;

  useEffect(() => {
    if (!currentQuestionId) return;
    if (previousQuestionIdRef.current === null) {
      previousQuestionIdRef.current = currentQuestionId;
      return;
    }
    if (previousQuestionIdRef.current === currentQuestionId) return;
    previousQuestionIdRef.current = currentQuestionId;
    if (questionTopRef.current) {
      const y = questionTopRef.current.getBoundingClientRect().top + window.scrollY - 120;
      window.scrollTo({ top: Math.max(0, y), behavior: "smooth" });
    }
  }, [currentQuestionId]);

  const answeredCount = useMemo(() => {
    return orderedQuestions.reduce((count, question) => {
      const answer = answers[String(question.questionId)];
      return count + (isAnswerComplete(answer) ? 1 : 0);
    }, 0);
  }, [answers, orderedQuestions]);

  const unansweredCount = orderedQuestions.length - answeredCount;

  const bookmarkedCount = useMemo(
    () => Object.values(bookmarks).filter(Boolean).length,
    [bookmarks]
  );

  const shortAnswerCount = useMemo(
    () => orderedQuestions.filter((question) => question.isShortAnswer).length,
    [orderedQuestions]
  );

  const multipleResponseCount = useMemo(
    () =>
      orderedQuestions.filter(
        (question) => !question.isShortAnswer && question.isMultipleResponse
      ).length,
    [orderedQuestions]
  );

  const singleChoiceCount =
    orderedQuestions.length - shortAnswerCount - multipleResponseCount;

  const answeredIds = useMemo(() => {
    const set = new Set<string>();
    orderedQuestions.forEach((question) => {
      if (isAnswerComplete(answers[String(question.questionId)])) {
        set.add(String(question.questionId));
      }
    });
    return set;
  }, [answers, orderedQuestions]);

  const totalLoaded = orderedQuestions.length;
  const totalQuestions = pagination.total || totalLoaded;
  const hasUnloaded = totalQuestions > totalLoaded;
  const completion = totalLoaded
    ? Math.round((answeredCount / totalLoaded) * 100)
    : 0;

  const handleAnswerChange = useCallback(
    (questionId: string, payload?: AnswerPayload) => {
      setAnswers((prev) => {
        const next = { ...prev };
        if (!payload) {
          delete next[questionId];
          return next;
        }
        if (payload.type === "mcq" && payload.value.length === 0) {
          delete next[questionId];
          return next;
        }
        if (payload.type === "short" && payload.value.trim().length === 0) {
          delete next[questionId];
          return next;
        }
        next[questionId] = payload;
        return next;
      });
    },
    []
  );

  const toggleBookmark = useCallback((questionId: string) => {
    setBookmarks((prev) => ({ ...prev, [questionId]: !prev[questionId] }));
  }, []);

  const handleQuestionUpdated = useCallback(
    (questionId: string, payload: { stem: string; choices: PracticeChoice[] }) => {
      setQuestions((prev) =>
        prev.map((item) =>
          String(item.questionId) === questionId
            ? {
              ...item,
              stem: payload.stem,
              choices: payload.choices,
            }
            : item
        )
      );
    },
    []
  );

  const showCopyToast = useCallback((message: string) => {
    setCopyMessage(message);
    if (copyTimeoutRef.current) {
      window.clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = window.setTimeout(() => {
      setCopyMessage(null);
    }, 2000);
  }, []);

  const handleCopyCurrentQuestion = useCallback(async () => {
    if (!currentQuestion) return;
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      showCopyToast(t("practiceSession.copyFailed"));
      return;
    }

    const imageUrls = collectQuestionImageUrls(currentQuestion);
    const textPayload = buildCopyTextPayload({
      question: currentQuestion,
      index: currentIndex,
      labels: {
        question: t("practiceSession.question"),
        noPrompt: t("practiceSession.noPrompt"),
        choices: t("practiceSession.copyChoicesHeader"),
      },
    });

    if (
      typeof navigator.clipboard.write === "function" &&
      typeof ClipboardItem !== "undefined"
    ) {
      try {
        const imageAssets = (
          await Promise.allSettled(
            imageUrls.map(async (url) => {
              const response = await fetch(url);
              if (!response.ok) {
                throw new Error("Failed to fetch image");
              }
              const blob = await response.blob();
              return {
                blob,
                dataUrl: await readBlobAsDataUrl(blob),
              };
            })
          )
        )
          .filter(
            (
              result
            ): result is PromiseFulfilledResult<{ blob: Blob; dataUrl: string }> =>
              result.status === "fulfilled"
          )
          .map((result) => result.value);

        const { text: stemText } = parseStemContent(currentQuestion.stem ?? "");
        const promptHtml = escapeHtml(
          stemText || t("practiceSession.noPrompt")
        ).replace(/\n/g, "<br>");
        const choicesHtml = !currentQuestion.isShortAnswer
          ? (currentQuestion.choices ?? [])
            .map((choice, index) => {
              const choiceId = getChoiceId(choice, index);
              const choiceText = escapeHtml(choice.content ?? "").replace(
                /\n/g,
                "<br>"
              );
              return `<li><strong>${choiceId}.</strong> ${choiceText}</li>`;
            })
            .join("")
          : "";
        const imagesHtml = imageAssets
          .map((asset, index) => {
            const label = `${escapeHtml(t("practiceSession.copyImageLabel"))} ${index + 1
              }`;
            return `<figure style="margin: 0 0 10px;"><figcaption style="margin-bottom: 4px; font-size: 12px;">${label}</figcaption><img src="${asset.dataUrl}" alt="${label}" style="max-width: 100%; height: auto;" /></figure>`;
          })
          .join("");

        const htmlPayload = [
          `<section>`,
          `<h3>${escapeHtml(t("practiceSession.question"))} ${currentIndex + 1}</h3>`,
          `<p>${promptHtml}</p>`,
          choicesHtml
            ? `<h4>${escapeHtml(
              t("practiceSession.copyChoicesHeader")
            )}</h4><ol>${choicesHtml}</ol>`
            : "",
          imagesHtml
            ? `<h4>${escapeHtml(t("practiceSession.copyImageHeader"))}</h4>${imagesHtml}`
            : "",
          `</section>`,
        ].join("");

        const clipboardData: Record<string, Blob> = {
          "text/plain": new Blob([textPayload], { type: "text/plain" }),
          "text/html": new Blob([htmlPayload], { type: "text/html" }),
        };
        const firstImageBlob = imageAssets.find((asset) =>
          asset.blob.type.startsWith("image/")
        )?.blob;
        if (firstImageBlob?.type) {
          clipboardData[firstImageBlob.type] = firstImageBlob;
        }

        await navigator.clipboard.write([new ClipboardItem(clipboardData)]);
        showCopyToast(t("practiceSession.copySuccess"));
        return;
      } catch {
        // Fallback to plain text copy
      }
    }

    try {
      await navigator.clipboard.writeText(textPayload);
      showCopyToast(t("practiceSession.copySuccess"));
    } catch {
      showCopyToast(t("practiceSession.copyFailed"));
    }
  }, [currentIndex, currentQuestion, showCopyToast, t]);

  const handleKeyboard = useCallback(
    (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.isComposing) {
        return;
      }
      if (isQuestionEditing) {
        return;
      }
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        return;
      }
      if (!currentQuestion) return;

      if (event.key === "?" || (event.key === "/" && event.shiftKey)) {
        event.preventDefault();
        setShowShortcutHelp(true);
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        setShowSubmitDialog(true);
        return;
      }

      const shortcutKey = event.key.toLowerCase();
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && shortcutKey === "c") {
        event.preventDefault();
        void handleCopyCurrentQuestion();
        return;
      }
      if (
        ((event.ctrlKey && event.altKey) || (event.metaKey && event.shiftKey)) &&
        shortcutKey === "v"
      ) {
        event.preventDefault();
        toggleBookmark(String(currentQuestion.questionId));
        return;
      }

      if (event.ctrlKey && event.shiftKey && shortcutKey >= "1" && shortcutKey <= "9") {
        event.preventDefault();
        const targetIndex = Number(shortcutKey) - 1;
        if (targetIndex >= 0 && targetIndex < orderedQuestions.length) {
          setCurrentIndex(targetIndex);
        }
        return;
      }

      const key = shortcutKey;
      if (key === "arrowright" || key === "j") {
        setCurrentIndex((prev) => Math.min(prev + 1, orderedQuestions.length - 1));
        return;
      }
      if (key === "arrowleft" || key === "k") {
        setCurrentIndex((prev) => Math.max(prev - 1, 0));
        return;
      }

      if (key >= "1" && key <= "5") {
        const index = Number(key) - 1;
        const choice = currentQuestion.choices?.[index];
        if (!choice) return;
        const choiceId = getChoiceId(choice, index);
        const current = answers[String(currentQuestion.questionId)];
        if (currentQuestion.isMultipleResponse) {
          const existing =
            current && current.type === "mcq" && Array.isArray(current.value)
              ? current.value
              : [];
          const next = existing.includes(choiceId)
            ? existing.filter((value) => value !== choiceId)
            : [...existing, choiceId];
          handleAnswerChange(String(currentQuestion.questionId), {
            type: "mcq",
            value: next,
          });
        } else {
          handleAnswerChange(String(currentQuestion.questionId), {
            type: "mcq",
            value: [choiceId],
          });
        }
      }
    },
    [
      answers,
      currentQuestion,
      handleCopyCurrentQuestion,
      handleAnswerChange,
      isQuestionEditing,
      orderedQuestions.length,
      toggleBookmark,
    ]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboard);
    return () => window.removeEventListener("keydown", handleKeyboard);
  }, [handleKeyboard]);

  const handleSubmit = async () => {
    const lectureId = sessionContext.lectureId ?? fallbackLectureId;
    const examId = sessionContext.examId ?? fallbackExamId;
    const examIds = sessionContext.examIds ?? fallbackExamIds;
    if (!lectureId && !examId && examIds.length === 0) {
      setSubmitError("Unable to resolve content for submission.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);

    const answersPayload: Record<string, AnswerPayload> = {};
    for (const [questionId, payload] of Object.entries(answers)) {
      if (payload.type === "mcq" && payload.value.length === 0) continue;
      if (payload.type === "short" && payload.value.trim().length === 0) continue;
      answersPayload[questionId] = payload;
    }

    const body = JSON.stringify({ version: 1, answers: answersPayload });
    const headers = { "Content-Type": "application/json" };

    const submitViaSession = async () =>
      apiFetch<unknown>(
        `/api/practice/sessions/${encodeURIComponent(sessionId)}/submit`,
        { method: "POST", headers, body }
      );

    const filterQuery = buildExamQuery(
      sessionContext.examIds,
      sessionContext.filterActive
    );
    const submitViaLecture = async () =>
      apiFetch<unknown>(
        `/api/practice/lecture/${encodeURIComponent(lectureId!)}/submit${filterQuery}`,
        { method: "POST", headers, body }
      );

    const submitViaExam = async () =>
      apiFetch<unknown>(
        `/api/practice/exam/${encodeURIComponent(examId!)}/submit`,
        { method: "POST", headers, body }
      );

    const submitViaExamSet = async () =>
      apiFetch<unknown>(
        `/api/practice/exam-set/submit`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ version: 1, answers: answersPayload, examIds }),
        }
      );

    let response: unknown = null;
    try {
      if (isPersistedSessionId(sessionId)) {
        response = await submitViaSession();
      }
    } catch {
      response = null;
    }

    if (!response) {
      try {
        response = examId
          ? await submitViaExam()
          : examIds.length > 0
            ? await submitViaExamSet()
            : await submitViaLecture();
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
        setSubmitting(false);
        return;
      }
    }

    const parsed = submitResponseSchema.safeParse(response);
    const resultPayload: SubmitResult = parsed.success
      ? {
        lectureId: toOptionalString(parsed.data.lectureId) ?? (lectureId ?? undefined),
        submittedAt: parsed.data.submittedAt ?? undefined,
        summary: parsed.data.summary,
        items: parsed.data.items ?? [],
      }
      : {
        lectureId: lectureId ?? undefined,
        summary: undefined,
        items: [],
      };

    if (typeof window !== "undefined") {
      sessionStorage.setItem(
        `practice:result:${sessionId}`,
        JSON.stringify({
          ...resultPayload,
          lectureId,
          examId,
          examIds,
          examTitle: sessionContext.examTitle,
          answers: answersPayload,
          mode: sessionContext.mode,
          filterActive: sessionContext.filterActive,
        })
      );
    }

    router.push(`/practice/session/${sessionId}/result`);
  };

  const handleLoadMore = async () => {
    if (loadMoreLoading || !pagination.hasMore) return;
    const lectureId = sessionContext.lectureId ?? fallbackLectureId;
    const examId = sessionContext.examId ?? fallbackExamId;
    const examIds = sessionContext.examIds ?? fallbackExamIds;
    if (!lectureId && !examId && examIds.length === 0) return;
    setLoadMoreLoading(true);
    try {
      const nextOffset = pagination.offset + pagination.limit;
      const page = lectureId
        ? await fetchLectureQuestions(
          lectureId,
          nextOffset,
          sessionContext.examIds,
          sessionContext.filterActive
        )
        : examId
          ? await fetchExamQuestions(examId, nextOffset)
          : await fetchExamSetQuestions(examIds, nextOffset);
      setQuestions((prev) => [...prev, ...page.questions]);
      setPagination({
        total: page.total,
        offset: page.offset,
        limit: page.limit,
        hasMore: nextOffset + page.questions.length < page.total,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
    } finally {
      setLoadMoreLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen px-4 py-10">
        <div className="mx-auto w-full max-w-5xl space-y-6">
          <div className="h-8 w-48 animate-pulse rounded-full bg-muted" />
          <div className="h-48 animate-pulse rounded-3xl bg-muted" />
          <div className="h-56 animate-pulse rounded-3xl bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !currentQuestion) {
    return (
      <div className="min-h-screen px-4 py-10">
        <div className="mx-auto w-full max-w-3xl">
          <Card className="border border-danger/30 bg-danger/10">
            <CardContent className="space-y-2 p-6">
              <p className="text-lg font-semibold text-foreground">Unable to load session</p>
              <p className="text-sm text-muted-foreground">
                {error ?? CONNECTION_ERROR_MESSAGE}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const answerForCurrent = answers[String(currentQuestion.questionId)];

  return (
    <div className="min-h-screen px-4 py-10">
      <div className="mx-auto w-full max-w-[1400px] space-y-6">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            {sessionContext.warning && (
              <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
                {sessionContext.warning}
              </div>
            )}
            {submitError && (
              <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
                {submitError}
              </div>
            )}
            {resumeMessage && (
              <div className="rounded-lg border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-primary">
                {resumeMessage}
              </div>
            )}
            {copyMessage && (
              <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
                {copyMessage}
              </div>
            )}
            <div ref={questionTopRef} className="scroll-mt-32">
              <QuestionView
                question={currentQuestion}
                index={currentIndex}
                total={orderedQuestions.length}
                answer={answerForCurrent}
                onAnswerChange={(payload) =>
                  handleAnswerChange(String(currentQuestion.questionId), payload)
                }
                bookmarked={Boolean(bookmarks[String(currentQuestion.questionId)])}
                onToggleBookmark={() => toggleBookmark(String(currentQuestion.questionId))}
                onQuestionUpdated={handleQuestionUpdated}
                onEditModeChange={setIsQuestionEditing}
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button
                variant="outline"
                onClick={() => setCurrentIndex((prev) => Math.max(prev - 1, 0))}
                disabled={currentIndex === 0}
              >
                {t("practiceSession.previous")}
              </Button>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Flag className="h-4 w-4" />
                {bookmarks[String(currentQuestion.questionId)]
                  ? t("practiceSession.bookmarked")
                  : t("practiceSession.bookmark")}
              </div>
              <Button
                onClick={() =>
                  setCurrentIndex((prev) =>
                    Math.min(prev + 1, orderedQuestions.length - 1)
                  )
                }
                disabled={currentIndex >= orderedQuestions.length - 1}
              >
                {t("practiceSession.next")}
              </Button>
            </div>

            {pagination.hasMore && (
              <div className="flex flex-col items-center gap-2">
                <Button
                  variant="outline"
                  onClick={handleLoadMore}
                  disabled={loadMoreLoading}
                >
                  {loadMoreLoading ? "Loading more..." : "Load more questions"}
                </Button>
                {hasUnloaded && (
                  <span className="text-xs text-muted-foreground">
                    Showing {totalLoaded} of {totalQuestions} questions
                  </span>
                )}
              </div>
            )}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24">
            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-foreground">
                      {sessionContext.lectureTitle ??
                        sessionContext.examTitle ??
                        t("common.practice")}
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      {autoSaveStatus === "saving" && (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          <span>{t("practiceSession.autoSaving")}</span>
                        </>
                      )}
                      {autoSaveStatus === "saved" && (
                        <>
                          <Check className="h-3 w-3 text-success" />
                          <span className="text-success">{t("practiceSession.autoSaved")}</span>
                        </>
                      )}
                      {autoSaveStatus === "error" && (
                        <>
                          <XCircle className="h-3 w-3 text-danger" />
                          <span className="text-danger">{t("practiceSession.autoSaveFailed")}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {hasUnloaded && (
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="neutral">
                        Loaded {totalLoaded} / {totalQuestions}
                      </Badge>
                    </div>
                  )}
                </div>
                {isTimed && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Timer className="h-4 w-4" />
                    <span>{formatTime(timerSeconds)}</span>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setShowSubmitDialog(true)}
                >
                  {t("practiceSession.submit")}
                </Button>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{t("practiceSession.progress")}</span>
                    <span>{completion}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${completion}%` }}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-border/60 bg-muted/40 px-3 py-3 text-xs text-muted-foreground">
                  <p className="font-semibold text-foreground">{t("practiceSession.tip")}</p>
                  <p>
                    {t("practiceSession.tipDesc")}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    {t("practiceSession.questionNavigator")}
                  </p>
                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60" />
                      {t("practiceSession.unanswered")}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      {t("practiceSession.answered")}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                      {t("practiceSession.bookmark")}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-6 gap-2">
                  {orderedQuestions.map((question, index) => {
                    const id = String(question.questionId);
                    const isActive = index === currentIndex;
                    const isAnswered = answeredIds.has(id);
                    const isBookmarked = Boolean(bookmarks[id]);
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setCurrentIndex(index)}
                        className={cn(
                          "relative flex h-10 w-10 items-center justify-center rounded-xl border text-sm font-semibold transition",
                          isActive
                            ? "border-primary bg-primary text-primary-foreground shadow-soft"
                            : isAnswered
                              ? "border-success/40 bg-success/20 text-success"
                              : "border-border/70 bg-card text-muted-foreground hover:bg-muted"
                        )}
                      >
                        {index + 1}
                        {isBookmarked && (
                          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-warning" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>

      <SubmitDialog
        open={showSubmitDialog}
        unansweredCount={unansweredCount}
        onClose={() => setShowSubmitDialog(false)}
        onConfirm={() => {
          setShowSubmitDialog(false);
          void handleSubmit();
        }}
        loading={submitting}
      />
      <ShortcutHelpDialog
        open={showShortcutHelp}
        title="Practice shortcuts"
        description="Keyboard controls for faster solving and navigation."
        sections={SOLVER_SHORTCUT_SECTIONS}
        onClose={() => setShowShortcutHelp(false)}
      />
    </div>
  );
}
