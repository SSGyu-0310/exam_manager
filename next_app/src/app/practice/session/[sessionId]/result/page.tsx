"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  Copy,
  ImageIcon,
  Loader2,
  SendHorizontal,
  Sparkles,
} from "lucide-react";

import { apiFetch } from "@/lib/http";
import { resolveImageUrl } from "@/lib/image";
import { useLanguage } from "@/context/LanguageContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { mergeChoicesIntoStem } from "@/lib/question_edit";
import {
  AnswerPayload,
  lectureResultSchema,
  PracticeQuestion,
  sessionDetailSchema,
} from "@/components/practice/types";
import {
  getQuestionDetail,
  updateQuestion,
  type ManageChoice,
  type ManageQuestionDetail,
} from "@/lib/api/manage";

const CONNECTION_ERROR_MESSAGE = "연결 실패(엔드포인트/응답 확인 필요)";
const RESULT_MISSING_MESSAGE = "Result data missing. Please submit again.";
const RESULT_NOT_SUBMITTED_MESSAGE = "This session has not been submitted yet.";
const DEFAULT_PRACTICE_CHAT_MODEL = "gemini-3.1-flash-lite-preview";
const DEFAULT_EXPLANATION_PROMPT =
  "현재 문제를 JSON 기준으로 풀이해줘. 핵심 개념 강의 + 정답 근거 + 오답 포인트 + 실전에서 빠르게 푸는 팁까지 설명해줘.";

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

type EditableQuestionType =
  | "multiple_choice"
  | "multiple_response"
  | "short_answer";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  canSaveToExplanation?: boolean;
  relatedQuestionId?: string;
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

const isPersistedSessionId = (value: string) => /^\d+$/.test(value);

const toOptionalString = (value: unknown): string | undefined => {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return undefined;
};

const normalizeRecoveredResultItems = (items: unknown): ResultItem[] => {
  if (!Array.isArray(items)) {
    return [];
  }
  const normalized: ResultItem[] = [];
  for (const raw of items) {
    if (!raw || typeof raw !== "object") continue;
    const record = raw as Record<string, unknown>;
    const rawId = record.questionId ?? record.question_id;
    if (typeof rawId !== "string" && typeof rawId !== "number") continue;
    const answer =
      record.answer && typeof record.answer === "object"
        ? (record.answer as Record<string, unknown>)
        : null;
    const answerType =
      answer && typeof answer.type === "string" ? answer.type : undefined;
    const answerValue = answer ? answer.value : undefined;
    const isAnswered =
      typeof record.isAnswered === "boolean"
        ? record.isAnswered
        : answerValue !== undefined;

    normalized.push({
      questionId: String(rawId),
      type: answerType,
      isAnswered,
      isCorrect: typeof record.isCorrect === "boolean" ? record.isCorrect : null,
      userAnswer: answerValue,
    });
  }
  return normalized;
};

const buildStoredResultFromSessionDetail = (
  payload: unknown
): StoredResult | null => {
  const parsed = sessionDetailSchema.safeParse(payload);
  if (!parsed.success) {
    return null;
  }

  const normalizedItems = normalizeRecoveredResultItems(parsed.data.items ?? []);
  const answered = normalizedItems.filter(
    (item) => item.isAnswered || item.userAnswer !== undefined
  ).length;
  const correct = normalizedItems.filter((item) => item.isCorrect === true).length;

  return {
    lectureId: toOptionalString(parsed.data.lectureId),
    lectureTitle: parsed.data.lectureTitle ?? undefined,
    examTitle: parsed.data.examTitle ?? undefined,
    submittedAt: parsed.data.finishedAt ?? undefined,
    summary: {
      all: {
        total: normalizedItems.length,
        answered,
        correct,
      },
    },
    items: normalizedItems,
    mode: parsed.data.mode ?? undefined,
    examIds: parsed.data.examIds ?? undefined,
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

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const extractPracticeChatReply = (payload: unknown) => {
  const root = toRecord(payload);
  if (!root) {
    throw new Error("AI 응답 형식이 올바르지 않습니다.");
  }

  const data = toRecord(root.data);
  const replyCandidate = data?.reply ?? root.reply;
  const modelCandidate = data?.model ?? root.model;
  const reply =
    typeof replyCandidate === "string" ? replyCandidate.trim() : "";
  if (!reply) {
    throw new Error("AI 응답 본문이 비어 있습니다.");
  }

  const model =
    typeof modelCandidate === "string" && modelCandidate.trim().length > 0
      ? modelCandidate.trim()
      : DEFAULT_PRACTICE_CHAT_MODEL;

  return { reply, model };
};

const renderInlineMarkdown = (text: string): ReactNode[] => {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let keyIndex = 0;

  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      nodes.push(text.slice(lastIndex, start));
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      nodes.push(
        <strong key={`strong-${keyIndex}`}>{token.slice(2, -2)}</strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      nodes.push(
        <code
          key={`code-${keyIndex}`}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.92em]"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else {
      nodes.push(token);
    }
    keyIndex += 1;
    lastIndex = start + token.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length ? nodes : [text];
};

const ChatMarkdown = ({
  content,
  className,
}: {
  content: string;
  className?: string;
}) => {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let paragraphLines: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let listItems: string[] = [];
  let blockIndex = 0;

  const flushParagraph = () => {
    if (!paragraphLines.length) return;
    const paragraphText = paragraphLines.join(" ").trim();
    if (paragraphText) {
      blocks.push(
        <p key={`p-${blockIndex}`} className="leading-relaxed">
          {renderInlineMarkdown(paragraphText)}
        </p>
      );
      blockIndex += 1;
    }
    paragraphLines = [];
  };

  const flushList = () => {
    if (!listType || !listItems.length) {
      listType = null;
      listItems = [];
      return;
    }
    const Tag = listType;
    blocks.push(
      <Tag
        key={`${listType}-${blockIndex}`}
        className={listType === "ul" ? "list-disc space-y-1 pl-5" : "list-decimal space-y-1 pl-5"}
      >
        {listItems.map((item, itemIndex) => (
          <li key={`${listType}-${blockIndex}-${itemIndex}`}>
            {renderInlineMarkdown(item)}
          </li>
        ))}
      </Tag>
    );
    blockIndex += 1;
    listType = null;
    listItems = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    if (/^---+$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push(<hr key={`hr-${blockIndex}`} className="my-4 border-border/70" />);
      blockIndex += 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(4, headingMatch[1].length);
      const headingText = headingMatch[2].trim();
      const headingClass =
        level === 1
          ? "text-xl font-bold tracking-tight"
          : level === 2
            ? "text-lg font-bold tracking-tight"
            : level === 3
              ? "text-base font-semibold"
              : "text-sm font-semibold";
      blocks.push(
        <p key={`h-${blockIndex}`} className={headingClass}>
          {renderInlineMarkdown(headingText)}
        </p>
      );
      blockIndex += 1;
      continue;
    }

    const unorderedMatch = line.match(/^[-*]\s+(.+)$/);
    const orderedMatch = line.match(/^\d+\.\s+(.+)$/);
    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      const nextType: "ul" | "ol" = unorderedMatch ? "ul" : "ol";
      const itemText = (unorderedMatch?.[1] ?? orderedMatch?.[1] ?? "").trim();
      if (listType && listType !== nextType) {
        flushList();
      }
      if (!listType) {
        listType = nextType;
      }
      if (itemText) {
        listItems.push(itemText);
      }
      continue;
    }

    flushList();
    paragraphLines.push(line);
  }

  flushParagraph();
  flushList();

  return (
    <div className={className ?? "space-y-3 text-[15px] leading-7"}>{blocks}</div>
  );
};

const extractEvidenceSection = (content: string) => {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const startIndex = lines.findIndex((line) =>
    /근거\s*설명/i.test(line.trim())
  );
  if (startIndex < 0) {
    return content;
  }

  const sectionLines: string[] = [];
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    const isMarkdownHeading = /^#{1,6}\s+/.test(trimmed);
    const isNumberedHeading = /^\d+\)\s+/.test(trimmed);
    const isNextSectionTitle =
      /오답|함정|실전|복습|체크|핵심\s*결론|요약|추가\s*설명/i.test(trimmed);

    if ((isMarkdownHeading || isNumberedHeading) && isNextSectionTitle) {
      break;
    }
    if (isMarkdownHeading && !/근거\s*설명/i.test(trimmed)) {
      break;
    }
    sectionLines.push(line);
  }

  const section = sectionLines.join("\n").trim();
  return section || content;
};

const markdownToPlainTextWithBreaks = (content: string) => {
  const normalized = extractEvidenceSection(content)
    .replace(/\r\n?/g, "\n")
    .replace(/^```[^\n]*$/gm, "")
    .replace(/!\[[^\]]*]\(([^)]+)\)/g, "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/^\s*\d+\)\s+/gm, "")
    .replace(/^\s*-{3,}\s*$/gm, "");

  const lines = normalized
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/g, ""))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return lines;
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

const resolveQuestionType = (
  rawType: string | null | undefined,
  fallback: ResultQuestion
): EditableQuestionType => {
  if (rawType === "short_answer") return "short_answer";
  if (rawType === "multiple_response") return "multiple_response";
  if (rawType === "multiple_choice") return "multiple_choice";
  if (fallback.isShortAnswer) return "short_answer";
  if (fallback.isMultipleResponse) return "multiple_response";
  return "multiple_choice";
};

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
  const [editedType, setEditedType] = useState<EditableQuestionType>("multiple_choice");
  const [editedStem, setEditedStem] = useState("");
  const [editedChoices, setEditedChoices] = useState<EditableChoice[]>([]);
  const [editedCorrectAnswerText, setEditedCorrectAnswerText] = useState("");
  const latestEditQuestionIdRef = useRef<string | null>(null);
  const [showCropImage, setShowCropImage] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    {
      id: "assistant-welcome",
      role: "assistant",
      content:
        "현재 보고 있는 문제 JSON을 함께 보내서 해설해드립니다. 질문을 입력하거나 아래 기본 해설 요청 버튼을 눌러주세요.",
      createdAt: Date.now(),
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatModelName, setChatModelName] = useState(DEFAULT_PRACTICE_CHAT_MODEL);
  const chatMessagesRef = useRef<ChatMessage[]>([]);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const [savingExplanationMessageId, setSavingExplanationMessageId] =
    useState<string | null>(null);
  const [savedExplanationByMessageId, setSavedExplanationByMessageId] = useState<
    Record<string, true>
  >({});
  const [explanationSaveErrorByMessageId, setExplanationSaveErrorByMessageId] =
    useState<Record<string, string>>({});

  useEffect(() => {
    if (typeof window === "undefined") return;
    setStorageReady(false);
    setStoredResult(null);
    setQuestions([]);
    setError(null);
    setLoading(true);
    setChatInput("");
    setChatError(null);
    setChatModelName(DEFAULT_PRACTICE_CHAT_MODEL);
    setSavingExplanationMessageId(null);
    setSavedExplanationByMessageId({});
    setExplanationSaveErrorByMessageId({});
    setChatMessages([
      {
        id: "assistant-welcome",
        role: "assistant",
        content:
          "현재 보고 있는 문제 JSON을 함께 보내서 해설해드립니다. 질문을 입력하거나 아래 기본 해설 요청 버튼을 눌러주세요.",
        createdAt: Date.now(),
      },
    ]);
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
    chatMessagesRef.current = chatMessages;
  }, [chatMessages]);

  useEffect(() => {
    if (!chatScrollRef.current) {
      return;
    }
    const container = chatScrollRef.current;
    container.scrollTop = container.scrollHeight;
  }, [chatMessages, chatLoading]);

  useEffect(() => {
    if (!storageReady) return;
    let active = true;
    const loadResult = async () => {
      setLoading(true);
      setError(null);
      let effectiveResult = storedResult;
      let hasExamSet =
        Array.isArray(effectiveResult?.examIds) &&
        effectiveResult.examIds.length > 0;

      if (!effectiveResult?.lectureId && !effectiveResult?.examId && !hasExamSet) {
        if (!isPersistedSessionId(sessionId)) {
          if (!active) return;
          setLoading(false);
          setError(RESULT_MISSING_MESSAGE);
          return;
        }

        try {
          const sessionResponse = await apiFetch<unknown>(
            `/api/practice/sessions/${encodeURIComponent(sessionId)}`,
            { cache: "no-store" }
          );
          const recovered = buildStoredResultFromSessionDetail(sessionResponse);
          if (!recovered) {
            throw new Error(CONNECTION_ERROR_MESSAGE);
          }
          if (!recovered.submittedAt) {
            if (!active) return;
            setLoading(false);
            setError(RESULT_NOT_SUBMITTED_MESSAGE);
            return;
          }

          effectiveResult = recovered;
          hasExamSet =
            Array.isArray(effectiveResult.examIds) &&
            effectiveResult.examIds.length > 0;

          if (active) {
            setStoredResult(recovered);
            if (typeof window !== "undefined") {
              sessionStorage.setItem(
                `practice:result:${sessionId}`,
                JSON.stringify(recovered)
              );
            }
          }
        } catch (err) {
          if (!active) return;
          setLoading(false);
          setError(err instanceof Error ? err.message : CONNECTION_ERROR_MESSAGE);
          return;
        }
      }

      if (!effectiveResult?.lectureId && !effectiveResult?.examId && !hasExamSet) {
        if (!active) return;
        setLoading(false);
        setError(RESULT_MISSING_MESSAGE);
        return;
      }
      if (!effectiveResult) {
        if (!active) return;
        setLoading(false);
        setError(RESULT_MISSING_MESSAGE);
        return;
      }

      try {
        const params = new URLSearchParams();
        params.set("includeAnswer", "true");
        if (effectiveResult.lectureId) {
          appendExamParams(
            params,
            effectiveResult.examIds,
            effectiveResult.filterActive
          );
        }
        if (!effectiveResult.lectureId && !effectiveResult.examId && hasExamSet) {
          for (const examId of effectiveResult.examIds ?? []) {
            params.append("exam_ids", String(examId));
          }
        }
        const endpoint = effectiveResult.lectureId
          ? `/api/practice/lecture/${encodeURIComponent(
            effectiveResult.lectureId
          )}/result?${params.toString()}`
          : effectiveResult.examId
            ? `/api/practice/exam/${encodeURIComponent(
              effectiveResult.examId
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
    sessionId,
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
  const currentQuestion = filteredQuestions[activeIndex];

  const activeQuestionPayload = useMemo(() => {
    if (!currentQuestion) {
      return null;
    }
    const { images: stemImages } = parseStemContent(currentQuestion.stem ?? "");
    const result = currentQuestion.result;
    const choiceImageUrls = (currentQuestion.choices ?? [])
      .map((choice) => resolveImageUrl(choice.imageUrl ?? choice.image))
      .filter((value): value is string => Boolean(value));
    const questionImageUrls = Array.from(
      new Set(
        [
          resolveImageUrl(currentQuestion.imageUrl ?? currentQuestion.image),
          resolveImageUrl(currentQuestion.originalImageUrl),
          ...stemImages.map((imageUrl) => resolveImageUrl(imageUrl)),
          ...choiceImageUrls,
        ].filter((value): value is string => Boolean(value))
      )
    );

    return {
      sessionId,
      lectureTitle: storedResult?.lectureTitle ?? null,
      examTitle: currentQuestion.examTitle ?? storedResult?.examTitle ?? null,
      questionImageUrls,
      question: {
        questionId: currentQuestion.questionId,
        questionNumber: currentQuestion.questionNumber ?? null,
        stem: currentQuestion.stem ?? "",
        choices: (currentQuestion.choices ?? []).map((choice, index) => ({
          number:
            typeof choice.number === "number" ? choice.number : index + 1,
          content: choice.content ?? "",
          imageUrl: resolveImageUrl(choice.imageUrl ?? choice.image),
        })),
        isShortAnswer: Boolean(currentQuestion.isShortAnswer),
        isMultipleResponse: Boolean(currentQuestion.isMultipleResponse),
        explanation: currentQuestion.explanation ?? null,
        correctChoiceNumbers: currentQuestion.correctChoiceNumbers ?? [],
        correctAnswerText: currentQuestion.correctAnswerText ?? null,
        imageUrl: resolveImageUrl(currentQuestion.imageUrl ?? currentQuestion.image),
        stemImageUrls: stemImages
          .map((imageUrl) => resolveImageUrl(imageUrl))
          .filter((value): value is string => Boolean(value)),
        originalImageUrl: resolveImageUrl(currentQuestion.originalImageUrl),
      },
      result: {
        isAnswered: Boolean(result?.isAnswered),
        isCorrect:
          typeof result?.isCorrect === "boolean" ? result.isCorrect : null,
        userAnswer: result?.userAnswer ?? null,
        correctAnswer: result?.correctAnswer ?? null,
        correctAnswerText: result?.correctAnswerText ?? null,
      },
    };
  }, [
    currentQuestion,
    sessionId,
    storedResult?.examTitle,
    storedResult?.lectureTitle,
  ]);

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

  const sendPracticeChat = useCallback(
    async (
      message: string,
      options?: { source?: "manual" | "default_explanation" }
    ) => {
      const trimmed = message.trim();
      if (!trimmed || chatLoading) {
        return;
      }
      if (!activeQuestionPayload) {
        setChatError("현재 문제를 불러온 뒤 다시 시도해주세요.");
        return;
      }
      const source = options?.source ?? "manual";
      const relatedQuestionId = String(activeQuestionPayload.question.questionId);
      const displayUserMessage =
        source === "default_explanation" ? "기본해설요청" : trimmed;

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: displayUserMessage,
        createdAt: Date.now(),
      };
      const historyForRequest = chatMessagesRef.current
        .filter((item) => item.id !== "assistant-welcome")
        .slice(-12)
        .map((item) => ({ role: item.role, content: item.content }));

      setChatMessages((prev) => [...prev, userMessage]);
      setChatInput("");
      setChatError(null);
      setChatLoading(true);

      try {
        const payload = await apiFetch<unknown>("/ai/practice-chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            model: DEFAULT_PRACTICE_CHAT_MODEL,
            message: trimmed,
            requestSource: source,
            messages: historyForRequest,
            currentQuestion: activeQuestionPayload,
          }),
        });
        const { reply, model } = extractPracticeChatReply(payload);
        setChatModelName(model);
        setChatMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: reply,
            createdAt: Date.now(),
            canSaveToExplanation: source === "default_explanation",
            relatedQuestionId,
          },
        ]);
      } catch (err) {
        setChatError(
          err instanceof Error ? err.message : "AI 응답 요청에 실패했습니다."
        );
      } finally {
        setChatLoading(false);
      }
    },
    [activeQuestionPayload, chatLoading]
  );

  const handleAskDefaultExplanation = useCallback(() => {
    void sendPracticeChat(DEFAULT_EXPLANATION_PROMPT, {
      source: "default_explanation",
    });
  }, [sendPracticeChat]);

  const handleSaveAiExplanation = useCallback(async (message: ChatMessage) => {
    if (!message.canSaveToExplanation || !message.relatedQuestionId) {
      return;
    }
    if (savedExplanationByMessageId[message.id]) {
      return;
    }

    setSavingExplanationMessageId(message.id);
    setExplanationSaveErrorByMessageId((prev) => {
      const next = { ...prev };
      delete next[message.id];
      return next;
    });

    try {
      const detail = await getQuestionDetail(message.relatedQuestionId);
      const aiExplanation = markdownToPlainTextWithBreaks(message.content);
      if (!aiExplanation) {
        throw new Error("저장할 해설 본문이 비어 있습니다.");
      }

      const targetType: EditableQuestionType =
        detail.type === "short_answer"
          ? "short_answer"
          : detail.type === "multiple_response"
            ? "multiple_response"
            : "multiple_choice";

      const choicesPayload =
        targetType === "short_answer"
          ? []
          : sortManageChoices(detail.choices).map((choice, index) => ({
            id: choice.id,
            number: getManageChoiceNumber(choice, index),
            content: choice.content ?? "",
            isCorrect: Boolean(choice.isCorrect),
            imagePath: choice.imagePath ?? null,
          }));

      const saved = await updateQuestion(detail.id, {
        content: detail.content ?? "",
        explanation: aiExplanation,
        type: targetType,
        lectureId: detail.lectureId ?? null,
        correctAnswerText:
          targetType === "short_answer"
            ? detail.correctAnswerText ?? detail.answer ?? ""
            : null,
        choices: choicesPayload,
      });

      setQuestions((prev) =>
        prev.map((item) =>
          String(item.questionId) === String(saved.id)
            ? { ...item, explanation: saved.explanation ?? aiExplanation }
            : item
        )
      );
      setQuestionDetail((prev) =>
        prev && String(prev.id) === String(saved.id) ? saved : prev
      );
      setSavedExplanationByMessageId((prev) => ({ ...prev, [message.id]: true }));
      setEditSuccess("AI 해설을 문제 해설에 저장했습니다.");
    } catch (err) {
      setExplanationSaveErrorByMessageId((prev) => ({
        ...prev,
        [message.id]:
          err instanceof Error ? err.message : "해설 저장에 실패했습니다.",
      }));
    } finally {
      setSavingExplanationMessageId((prev) =>
        prev === message.id ? null : prev
      );
    }
  }, [savedExplanationByMessageId]);

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
      setEditedType(resolveQuestionType(detail.type, currentQuestion));
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
    const currentQuestion = filteredQuestions[activeIndex];
    if (questionDetail && currentQuestion) {
      setEditedType(resolveQuestionType(questionDetail.type, currentQuestion));
      setEditedStem(questionDetail.content ?? currentQuestion.stem ?? "");
      setEditedChoices(toEditableChoicesFromManage(questionDetail.choices));
      setEditedCorrectAnswerText(
        questionDetail.correctAnswerText ?? questionDetail.answer ?? ""
      );
    }
    setIsEditMode(false);
    setEditError(null);
  }, [activeIndex, filteredQuestions, questionDetail]);

  const handleTypeChange = useCallback(
    (nextType: EditableQuestionType) => {
      if (editedType === nextType) return;
      if (nextType === "short_answer" && editedType !== "short_answer") {
        setEditedStem((prev) => mergeChoicesIntoStem(prev, editedChoices));
      }
      setEditedType(nextType);
    },
    [editedChoices, editedType]
  );

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
      const type = editedType;
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
              isShortAnswer: type === "short_answer",
              isMultipleResponse: type === "multiple_response",
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
              return {
                ...record,
                type: type === "short_answer" ? "short" : "mcq",
              };
            }
            return {
              ...record,
              isCorrect: newIsCorrect,
              type: type === "short_answer" ? "short" : "mcq",
            };
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
      setEditedType(resolveQuestionType(saved.type, currentQuestion));
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
  }, [
    activeIndex,
    editedChoices,
    editedCorrectAnswerText,
    editedStem,
    editedType,
    filteredQuestions,
    itemsById,
    questionDetail,
    sessionId,
    storedResult,
  ]);

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
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        if (!isEditMode || savingEditor) return;
        event.preventDefault();
        void handleSaveEdit();
        return;
      }
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
    [
      activeIndex,
      filteredQuestions.length,
      focusQuestion,
      handleSaveEdit,
      isEditMode,
      savingEditor,
    ]
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
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
  const accuracyValue = Math.max(0, Math.min(100, accuracy));
  const accuracyRingRadius = 32;
  const accuracyRingCircumference = 2 * Math.PI * accuracyRingRadius;
  const accuracyRingOffset =
    accuracyRingCircumference * (1 - accuracyValue / 100);
  const accuracyStrokeColor =
    accuracyValue >= 80
      ? "var(--color-success)"
      : accuracyValue >= 60
        ? "var(--color-warning)"
        : "var(--color-danger)";
  const accuracyTrackColor =
    accuracyValue >= 80
      ? "rgb(var(--color-success-rgb) / 0.18)"
      : accuracyValue >= 60
        ? "rgb(var(--color-warning-rgb) / 0.18)"
        : "rgb(var(--color-danger-rgb) / 0.18)";

  if (loading) {
    return (
      <div className="min-h-screen px-4 py-6">
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
      <div className="min-h-screen px-4 py-6">
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

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto w-full max-w-screen-xl space-y-6">
        <Card className="border border-border/70 bg-card/90 shadow-soft">
          <CardContent className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 space-y-2">
                <h1 className="truncate text-3xl font-semibold text-foreground">
                  {storedResult?.lectureTitle || storedResult?.examTitle || t("practiceResult.sessionSummary")}
                </h1>
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <span className="font-medium">{t("practiceResult.metricTotal")} {total}</span>
                  <span>&middot;</span>
                  <span className="font-medium">{t("practiceResult.metricAnswered")} {answered}</span>
                  <span>&middot;</span>
                  <span className="font-medium">{t("practiceResult.metricCorrect")} {correct}</span>
                </div>
              </div>
              <div className="shrink-0">
                <div className="relative h-24 w-24">
                  <svg className="h-24 w-24" viewBox="0 0 96 96" aria-hidden="true">
                    <circle
                      cx="48"
                      cy="48"
                      r={accuracyRingRadius}
                      fill="none"
                      stroke={accuracyTrackColor}
                      strokeWidth="10"
                    />
                    <circle
                      cx="48"
                      cy="48"
                      r={accuracyRingRadius}
                      fill="none"
                      stroke={accuracyStrokeColor}
                      strokeWidth="10"
                      strokeLinecap="round"
                      strokeDasharray={accuracyRingCircumference}
                      strokeDashoffset={accuracyRingOffset}
                      transform="rotate(-90 48 48)"
                      style={{ filter: "drop-shadow(0 1px 3px rgba(15,23,42,0.18))" }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
                    <span className="text-base font-bold text-foreground">{accuracyValue}%</span>
                    <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      {t("practiceResult.metricAccuracy")}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-8 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
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
                const isShortAnswerEditor = editedType === "short_answer";

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
                                문제 유형
                              </label>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  variant={editedType === "multiple_choice" ? "primary" : "outline"}
                                  size="sm"
                                  onClick={() => handleTypeChange("multiple_choice")}
                                  disabled={savingEditor}
                                >
                                  객관식
                                </Button>
                                <Button
                                  type="button"
                                  variant={editedType === "multiple_response" ? "primary" : "outline"}
                                  size="sm"
                                  onClick={() => handleTypeChange("multiple_response")}
                                  disabled={savingEditor}
                                >
                                  복수정답
                                </Button>
                                <Button
                                  type="button"
                                  variant={editedType === "short_answer" ? "primary" : "outline"}
                                  size="sm"
                                  onClick={() => handleTypeChange("short_answer")}
                                  disabled={savingEditor}
                                >
                                  주관식
                                </Button>
                              </div>
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
            <Card className="overflow-hidden border border-border/70 bg-card/90 shadow-soft">
              <CardContent className="p-0">
                <div className="flex items-center justify-between gap-2 border-b border-border/70 px-4 py-3">
                  <div>
                    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      <Bot className="h-3.5 w-3.5" />
                      AI Tutor
                    </p>
                    <p className="text-xs text-muted-foreground">{chatModelName}</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleAskDefaultExplanation}
                    disabled={chatLoading || !activeQuestionPayload}
                  >
                    <Sparkles className="h-4 w-4" />
                    기본 해설 요청
                  </Button>
                </div>

                <div
                  ref={chatScrollRef}
                  className="min-h-[420px] max-h-[56vh] overflow-y-auto bg-card"
                >
                  {chatMessages.map((message, index) =>
                    message.role === "user" ? (
                      <div key={message.id} className="flex justify-end px-4 pb-2 pt-4">
                        <p className="max-w-[90%] rounded-full bg-muted px-4 py-2 text-[13px] leading-relaxed text-foreground">
                          {message.content}
                        </p>
                      </div>
                    ) : (
                      <article
                        key={message.id}
                        className={`px-4 py-5 ${index === 0 ? "" : "border-t border-border/70"}`}
                      >
                        {message.canSaveToExplanation && message.relatedQuestionId && (
                          <div className="mb-3 flex items-center justify-between gap-2">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                              AI 해설
                            </p>
                            <Button
                              type="button"
                              size="sm"
                              variant={
                                savedExplanationByMessageId[message.id]
                                  ? "secondary"
                                  : "outline"
                              }
                              className="h-8"
                              disabled={
                                savingExplanationMessageId === message.id ||
                                Boolean(savedExplanationByMessageId[message.id])
                              }
                              onClick={() => {
                                void handleSaveAiExplanation(message);
                              }}
                            >
                              {savingExplanationMessageId === message.id
                                ? "저장 중..."
                                : savedExplanationByMessageId[message.id]
                                  ? "저장됨"
                                  : "해설에 저장"}
                            </Button>
                          </div>
                        )}
                        {explanationSaveErrorByMessageId[message.id] && (
                          <p className="mb-3 text-xs text-danger">
                            {explanationSaveErrorByMessageId[message.id]}
                          </p>
                        )}
                        <ChatMarkdown
                          content={message.content}
                          className="space-y-3 text-[16px] leading-8 text-foreground"
                        />
                      </article>
                    )
                  )}
                  {chatLoading && (
                    <div className="border-t border-border/70 px-4 py-5">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        답변 생성 중...
                      </div>
                    </div>
                  )}
                </div>

                {chatError && (
                  <div className="border-t border-danger/30 bg-danger/10 px-4 py-2 text-xs text-danger">
                    {chatError}
                  </div>
                )}

                <form
                  className="space-y-2 border-t border-border/70 bg-card px-3 py-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void sendPracticeChat(chatInput);
                  }}
                >
                  <Textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    placeholder="질문을 입력하세요 (예: 왜 이 선택지가 정답인지 단계별로 설명해줘)"
                    className="min-h-[88px] resize-none bg-card"
                    disabled={chatLoading || !activeQuestionPayload}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void sendPracticeChat(chatInput);
                      }
                    }}
                  />
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] text-muted-foreground">
                      현재 문제 JSON이 함께 전송됩니다.
                    </p>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={
                        chatLoading ||
                        !activeQuestionPayload ||
                        chatInput.trim().length === 0
                      }
                    >
                      <SendHorizontal className="h-4 w-4" />
                      전송
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

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
