/* eslint-disable @next/next/no-img-element */
import { useCallback, useEffect, useRef, useState } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import {
  getQuestionDetail,
  updateQuestion,
  type ManageChoice,
  type ManageQuestionDetail,
} from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ChoiceList } from "@/components/practice/ChoiceList";
import { mergeChoicesIntoStem } from "@/lib/question_edit";
import type {
  AnswerPayload,
  PracticeChoice,
  PracticeQuestion,
} from "@/components/practice/types";
import { resolveImageUrl } from "@/lib/image";

type QuestionViewProps = {
  question: PracticeQuestion;
  index: number;
  total: number;
  answer?: AnswerPayload;
  onAnswerChange: (payload: AnswerPayload | undefined) => void;
  bookmarked?: boolean;
  onToggleBookmark?: () => void;
  onQuestionUpdated?: (
    questionId: string,
    payload: {
      stem: string;
      choices: PracticeChoice[];
      isShortAnswer: boolean;
      isMultipleResponse: boolean;
    }
  ) => void;
  onEditModeChange?: (editing: boolean) => void;
};

type EditableQuestionType =
  | "multiple_choice"
  | "multiple_response"
  | "short_answer";

type EditableChoice = {
  number: number;
  content: string;
};

const getChoiceId = (choice: PracticeChoice, index: number) =>
  typeof choice.number === "number" ? choice.number : index + 1;

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

const toEditableChoicesFromPractice = (choices: PracticeChoice[] | undefined) =>
  (choices ?? []).map((choice, index) => ({
    number: getChoiceId(choice, index),
    content: choice.content ?? "",
  }));

const toEditableChoicesFromManage = (choices: ManageChoice[]) =>
  sortManageChoices(choices).map((choice, index) => ({
    number: getManageChoiceNumber(choice, index),
    content: choice.content ?? "",
  }));

const resolveQuestionType = (
  rawType: string | null | undefined,
  fallback: {
    isShortAnswer?: boolean | null;
    isMultipleResponse?: boolean | null;
  }
): EditableQuestionType => {
  if (rawType === "short_answer") return "short_answer";
  if (rawType === "multiple_response") return "multiple_response";
  if (rawType === "multiple_choice") return "multiple_choice";
  if (fallback.isShortAnswer) return "short_answer";
  if (fallback.isMultipleResponse) return "multiple_response";
  return "multiple_choice";
};

export function QuestionView({
  question,
  index,
  total,
  answer,
  onAnswerChange,
  bookmarked,
  onToggleBookmark,
  onQuestionUpdated,
  onEditModeChange,
}: QuestionViewProps) {
  const { t } = useLanguage();
  const isShortAnswer = Boolean(question.isShortAnswer);
  const isFallbackShortAnswer = Boolean(question.isShortAnswer);
  const isFallbackMultipleResponse = Boolean(question.isMultipleResponse);
  const selectedValues =
    answer && answer.type === "mcq" && Array.isArray(answer.value) ? answer.value : [];
  const shortAnswerValue = answer && answer.type === "short" ? answer.value : "";
  const image = resolveImageUrl(question.imageUrl ?? question.image);

  const [isEditMode, setIsEditMode] = useState(false);
  const [loadingEditor, setLoadingEditor] = useState(false);
  const [savingEditor, setSavingEditor] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccess, setEditSuccess] = useState<string | null>(null);
  const [questionDetail, setQuestionDetail] = useState<ManageQuestionDetail | null>(null);
  const [editedType, setEditedType] = useState<EditableQuestionType>(
    resolveQuestionType(undefined, {
      isShortAnswer: isFallbackShortAnswer,
      isMultipleResponse: isFallbackMultipleResponse,
    })
  );
  const [editedStem, setEditedStem] = useState(question.stem ?? "");
  const [editedChoices, setEditedChoices] = useState<EditableChoice[]>(
    toEditableChoicesFromPractice(question.choices)
  );
  const [editedCorrectAnswerText, setEditedCorrectAnswerText] = useState("");
  const latestQuestionIdRef = useRef(String(question.questionId));

  useEffect(() => {
    const questionId = String(question.questionId);
    latestQuestionIdRef.current = questionId;
    setIsEditMode(false);
    setLoadingEditor(false);
    setSavingEditor(false);
    setEditError(null);
    setEditSuccess(null);
    setQuestionDetail(null);
    setEditedType(
      resolveQuestionType(undefined, {
        isShortAnswer: isFallbackShortAnswer,
        isMultipleResponse: isFallbackMultipleResponse,
      })
    );
    setEditedStem(question.stem ?? "");
    setEditedChoices(toEditableChoicesFromPractice(question.choices));
    setEditedCorrectAnswerText("");
  }, [
    question.questionId,
    question.stem,
    question.choices,
    question.isShortAnswer,
    question.isMultipleResponse,
    isFallbackShortAnswer,
    isFallbackMultipleResponse,
  ]);

  useEffect(() => {
    onEditModeChange?.(isEditMode);
  }, [isEditMode, onEditModeChange]);

  const isShortAnswerEditor = editedType === "short_answer";

  const referenceImage = resolveImageUrl(
    questionDetail?.originalImageUrl ??
      question.originalImageUrl
  );

  const updateDraftChoice = useCallback((choiceNumber: number, value: string) => {
    setEditedChoices((prev) =>
      prev.map((choice) =>
        choice.number === choiceNumber ? { ...choice, content: value } : choice
      )
    );
  }, []);

  const handleEnterEditMode = useCallback(async () => {
    const targetQuestionId = String(question.questionId);
    setLoadingEditor(true);
    setEditError(null);
    setEditSuccess(null);

    try {
      const detail = await getQuestionDetail(targetQuestionId);
      if (latestQuestionIdRef.current !== targetQuestionId) {
        return;
      }
      setQuestionDetail(detail);
      setEditedType(
        resolveQuestionType(detail.type, {
          isShortAnswer: isFallbackShortAnswer,
          isMultipleResponse: isFallbackMultipleResponse,
        })
      );
      setEditedStem(detail.content ?? question.stem ?? "");
      setEditedChoices(toEditableChoicesFromManage(detail.choices));
      setEditedCorrectAnswerText(detail.correctAnswerText ?? detail.answer ?? "");
      setIsEditMode(true);
    } catch (err) {
      if (latestQuestionIdRef.current !== targetQuestionId) {
        return;
      }
      setEditError(
        err instanceof Error ? err.message : t("practiceSession.editLoadFailed")
      );
    } finally {
      if (latestQuestionIdRef.current === targetQuestionId) {
        setLoadingEditor(false);
      }
    }
  }, [
    isFallbackMultipleResponse,
    isFallbackShortAnswer,
    question.questionId,
    question.stem,
    t,
  ]);

  const handleCancelEdit = useCallback(() => {
    setIsEditMode(false);
    setEditError(null);
    if (questionDetail) {
      setEditedType(
        resolveQuestionType(questionDetail.type, {
          isShortAnswer: isFallbackShortAnswer,
          isMultipleResponse: isFallbackMultipleResponse,
        })
      );
      setEditedStem(questionDetail.content ?? question.stem ?? "");
      setEditedChoices(toEditableChoicesFromManage(questionDetail.choices));
      setEditedCorrectAnswerText(
        questionDetail.correctAnswerText ?? questionDetail.answer ?? ""
      );
      return;
    }
    setEditedType(
      resolveQuestionType(undefined, {
        isShortAnswer: isFallbackShortAnswer,
        isMultipleResponse: isFallbackMultipleResponse,
      })
    );
    setEditedStem(question.stem ?? "");
    setEditedChoices(toEditableChoicesFromPractice(question.choices));
    setEditedCorrectAnswerText("");
  }, [
    isFallbackMultipleResponse,
    isFallbackShortAnswer,
    question.stem,
    question.choices,
    questionDetail,
  ]);

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
      setEditError(t("practiceSession.editLoadFailed"));
      return;
    }

    const targetQuestionId = String(question.questionId);
    setSavingEditor(true);
    setEditError(null);
    setEditSuccess(null);

    try {
      const type = editedType;
      const choiceContentByNumber = new Map(
        editedChoices.map((choice) => [choice.number, choice.content])
      );
      const existingChoices = sortManageChoices(questionDetail.choices);
      const choicesPayload =
        type === "short_answer"
          ? []
          : existingChoices.map((choice, index) => {
              const number = getManageChoiceNumber(choice, index);
              return {
                id: choice.id,
                number,
                content: choiceContentByNumber.get(number) ?? choice.content ?? "",
                isCorrect: Boolean(choice.isCorrect),
                imagePath: choice.imagePath ?? null,
              };
            });

      const saved = await updateQuestion(questionDetail.id, {
        content: editedStem,
        explanation: questionDetail.explanation ?? "",
        type,
        lectureId: questionDetail.lectureId ?? null,
        correctAnswerText:
          type === "short_answer"
            ? editedCorrectAnswerText
            : null,
        choices: choicesPayload,
      });
      if (latestQuestionIdRef.current !== targetQuestionId) {
        return;
      }

      const nextChoices =
        type === "short_answer"
          ? []
          : sortManageChoices(saved.choices).map((choice, index) => ({
              number: getManageChoiceNumber(choice, index),
              content: choice.content ?? "",
              image: choice.imagePath ?? undefined,
            }));

      setQuestionDetail(saved);
      setEditedType(
        resolveQuestionType(saved.type, {
          isShortAnswer: isFallbackShortAnswer,
          isMultipleResponse: isFallbackMultipleResponse,
        })
      );
      setEditedStem(saved.content ?? editedStem);
      setEditedChoices(toEditableChoicesFromManage(saved.choices));
      setEditedCorrectAnswerText(
        saved.correctAnswerText ?? saved.answer ?? editedCorrectAnswerText
      );
      setIsEditMode(false);
      setEditSuccess(t("practiceSession.editSaveSuccess"));

      onQuestionUpdated?.(targetQuestionId, {
        stem: saved.content ?? editedStem,
        choices: nextChoices,
        isShortAnswer: type === "short_answer",
        isMultipleResponse: type === "multiple_response",
      });
    } catch (err) {
      if (latestQuestionIdRef.current !== targetQuestionId) {
        return;
      }
      setEditError(
        err instanceof Error ? err.message : t("practiceSession.editSaveFailed")
      );
    } finally {
      if (latestQuestionIdRef.current === targetQuestionId) {
        setSavingEditor(false);
      }
    }
  }, [
    editedChoices,
    editedCorrectAnswerText,
    editedStem,
    editedType,
    isFallbackMultipleResponse,
    isFallbackShortAnswer,
    onQuestionUpdated,
    question.questionId,
    questionDetail,
    t,
  ]);

  useEffect(() => {
    if (!isEditMode) return;

    const handleEditShortcut = (event: KeyboardEvent) => {
      if (event.isComposing) return;
      if (savingEditor) return;
      if (!(event.ctrlKey || event.metaKey) || event.key !== "Enter") return;
      event.preventDefault();
      void handleSaveEdit();
    };

    window.addEventListener("keydown", handleEditShortcut);
    return () => window.removeEventListener("keydown", handleEditShortcut);
  }, [handleSaveEdit, isEditMode, savingEditor]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {t("practiceSession.question")} {index + 1} {t("practiceSession.of")} {total}
          </p>
          <h2 className="text-xl font-semibold text-foreground">{t("practiceSession.solveQuestion")}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onToggleBookmark && !isEditMode && (
            <Button
              variant={bookmarked ? "secondary" : "outline"}
              size="sm"
              onClick={onToggleBookmark}
              className="rounded-full"
            >
              {bookmarked ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              {bookmarked ? t("practiceSession.bookmarked") : t("practiceSession.bookmark")}
            </Button>
          )}
          {!isEditMode ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void handleEnterEditMode();
              }}
              disabled={loadingEditor}
            >
              {loadingEditor
                ? t("practiceSession.editLoading")
                : t("practiceSession.edit")}
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelEdit}
                disabled={savingEditor}
              >
                {t("practiceSession.editCancel")}
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  void handleSaveEdit();
                }}
                disabled={savingEditor}
              >
                {savingEditor
                  ? t("practiceSession.submitDialog.submitting")
                  : t("practiceSession.editSave")}
              </Button>
            </>
          )}
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

      {isEditMode ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,1fr)] items-start">
          <Card className="border border-border/70 bg-card/90 shadow-soft">
            <CardContent className="space-y-5 p-6">
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {t("practiceSession.editMode")}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("practiceSession.editReferenceDesc")}
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
                  {t("practiceSession.editPrompt")}
                </label>
                <Textarea
                  value={editedStem}
                  onChange={(event) => setEditedStem(event.target.value)}
                  className="min-h-[180px]"
                />
              </div>
              {!isShortAnswerEditor && (
                <div className="space-y-3">
                  {editedChoices.map((choice) => (
                    <div key={`edit-choice-${choice.number}`} className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">
                        {t("practiceSession.editChoice")} {choice.number}
                      </label>
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
              {isShortAnswerEditor && (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground">
                    정답
                  </label>
                  <Input
                    value={editedCorrectAnswerText}
                    onChange={(event) => setEditedCorrectAnswerText(event.target.value)}
                    placeholder="정답 텍스트를 입력하세요"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t("practiceSession.editShortAnswerHint")}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
          <Card className="border border-border/70 bg-card/90 shadow-soft">
            <CardContent className="space-y-3 p-6">
              <p className="text-sm font-semibold text-foreground">
                {t("practiceSession.editReference")}
              </p>
              {typeof referenceImage === "string" && referenceImage.length > 0 ? (
                <img
                  src={referenceImage}
                  alt={t("practiceSession.editReference")}
                  className="max-h-[640px] w-full rounded-xl border border-border/60 object-contain"
                />
              ) : (
                <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-8 text-sm text-muted-foreground">
                  {t("practiceSession.editNoReference")}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2 items-start">
          <Card className="border border-border/70 bg-card/90 shadow-soft">
            <CardContent className="space-y-4 p-6">
              <p className="text-base leading-relaxed text-foreground whitespace-pre-wrap">
                {question.stem ?? t("practiceSession.noPrompt")}
              </p>
              {typeof image === "string" && image.length > 0 && (
                <img
                  src={image}
                  alt={t("practiceSession.questionVisual")}
                  className="max-h-80 w-auto rounded-xl border border-border/60 object-contain mx-auto"
                />
              )}
            </CardContent>
          </Card>
          <div className="space-y-4">
            {isShortAnswer ? (
              <div className="space-y-3">
                <p className="text-sm font-semibold text-foreground">{t("practiceSession.yourAnswer")}</p>
                <Input
                  value={shortAnswerValue}
                  onChange={(event) =>
                    onAnswerChange({
                      type: "short",
                      value: event.target.value,
                    })
                  }
                  placeholder={t("practiceSession.typeAnswer")}
                />
              </div>
            ) : (
              <ChoiceList
                choices={question.choices ?? []}
                multiple={Boolean(question.isMultipleResponse)}
                selected={selectedValues}
                onChange={(next) => {
                  onAnswerChange(
                    next.length > 0
                      ? {
                          type: "mcq",
                          value: next,
                        }
                      : undefined
                  );
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
