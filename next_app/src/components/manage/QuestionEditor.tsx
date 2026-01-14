"use client";

import { useMemo, useState } from "react";

import type {
  ManageChoice,
  ManageLecture,
  ManageQuestionDetail,
} from "@/lib/api/manage";
import { updateQuestion } from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type QuestionEditorProps = {
  question: ManageQuestionDetail;
  lectures: ManageLecture[];
};

type ChoiceState = ManageChoice & { tempId: string };

const buildChoices = (choices: ManageChoice[], fallbackCount = 5) => {
  if (choices.length) {
    return choices.map((choice) => ({
      ...choice,
      content: choice.content ?? "",
      isCorrect: Boolean(choice.isCorrect),
      tempId: `choice-${choice.number}-${choice.id ?? "new"}`,
    }));
  }
  return Array.from({ length: fallbackCount }, (_, index) => ({
    number: index + 1,
    content: "",
    isCorrect: false,
    tempId: `choice-new-${index + 1}`,
  }));
};

export function QuestionEditor({ question, lectures }: QuestionEditorProps) {
  const [type, setType] = useState(question.type);
  const [lectureId, setLectureId] = useState<number | "">(
    question.lectureId ?? ""
  );
  const [content, setContent] = useState(question.content ?? "");
  const [explanation, setExplanation] = useState(question.explanation ?? "");
  const [correctAnswerText, setCorrectAnswerText] = useState(
    question.correctAnswerText ?? question.answer ?? ""
  );
  const [choices, setChoices] = useState<ChoiceState[]>(
    buildChoices(question.choices)
  );
  const [imageUrl, setImageUrl] = useState<string | null>(
    question.imagePath ? `/static/uploads/${question.imagePath}` : null
  );
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const groupedLectures = useMemo(() => {
    const groups = new Map<string, ManageLecture[]>();
    lectures.forEach((lecture) => {
      const key = lecture.blockName ?? "Other";
      const list = groups.get(key) ?? [];
      list.push(lecture);
      groups.set(key, list);
    });
    return Array.from(groups.entries());
  }, [lectures]);

  const handleChoiceChange = (index: number, value: string) => {
    setChoices((prev) =>
      prev.map((choice, idx) => (idx === index ? { ...choice, content: value } : choice))
    );
  };

  const toggleChoiceCorrect = (index: number) => {
    setChoices((prev) =>
      prev.map((choice, idx) => {
        if (idx !== index) {
          if (type === "multiple_choice") {
            return { ...choice, isCorrect: false };
          }
          return choice;
        }
        return { ...choice, isCorrect: !choice.isCorrect };
      })
    );
  };

  const addChoice = () => {
    setChoices((prev) => [
      ...prev,
      {
        number: prev.length + 1,
        content: "",
        isCorrect: false,
        tempId: `choice-new-${prev.length + 1}`,
      },
    ]);
  };

  const removeChoice = (index: number) => {
    setChoices((prev) => {
      const next = prev.filter((_, idx) => idx !== index);
      return next.map((choice, idx) => ({ ...choice, number: idx + 1 }));
    });
  };

  const handleImageUpload = async (file: File) => {
    const formData = new FormData();
    formData.append("image", file, file.name || "image.png");
    const response = await fetch("/api/proxy/manage/upload-image", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error("Image upload failed.");
    }
    const data = (await response.json()) as { success?: boolean; url?: string; filename?: string; error?: string };
    if (!data.success) {
      throw new Error(data.error || "Image upload failed.");
    }
    setImageUrl(data.url ?? null);
    setUploadedImage(data.filename ?? null);
    setRemoveImage(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await updateQuestion(question.id, {
        content,
        explanation,
        type,
        lectureId: lectureId === "" ? null : Number(lectureId),
        correctAnswerText: type === "short_answer" ? correctAnswerText : null,
        uploadedImage,
        removeImage,
        choices:
          type === "short_answer"
            ? []
            : choices.map((choice, index) => ({
                id: choice.id,
                number: index + 1,
                content: choice.content ?? "",
                isCorrect: Boolean(choice.isCorrect),
                imagePath: choice.imagePath ?? null,
              })),
      });
      setSuccess("Question updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update question.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Question type
          </label>
          <div className="flex flex-wrap gap-2">
            {[
              { value: "multiple_choice", label: "Multiple choice" },
              { value: "multiple_response", label: "Multiple response" },
              { value: "short_answer", label: "Short answer" },
            ].map((option) => (
              <Button
                key={option.value}
                type="button"
                variant={type === option.value ? "primary" : "outline"}
                size="sm"
                onClick={() => setType(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Lecture
          </label>
          <Select
            value={lectureId === "" ? "" : String(lectureId)}
            onChange={(event) =>
              setLectureId(event.target.value ? Number(event.target.value) : "")
            }
          >
            <option value="">Unclassified</option>
            {groupedLectures.map(([blockName, blockLectures]) => (
              <optgroup key={blockName} label={blockName}>
                {blockLectures.map((lecture) => (
                  <option key={lecture.id} value={lecture.id}>
                    {lecture.title}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Content
          </label>
          <Textarea value={content} onChange={(event) => setContent(event.target.value)} />
        </div>

        {imageUrl && (
          <div className="space-y-3">
            <img
              src={imageUrl}
              alt="Question"
              className="max-h-64 rounded-xl border border-border/60 object-contain"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setImageUrl(null);
                setUploadedImage(null);
                setRemoveImage(true);
              }}
            >
              Remove image
            </Button>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Upload image
          </label>
          <Input
            type="file"
            accept="image/*"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                handleImageUpload(file).catch((err: unknown) =>
                  setError(err instanceof Error ? err.message : "Image upload failed.")
                );
              }
            }}
          />
        </div>

        {type === "short_answer" ? (
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Correct answer
            </label>
            <Input
              value={correctAnswerText}
              onChange={(event) => setCorrectAnswerText(event.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Choices
              </label>
              <Button variant="outline" size="sm" onClick={addChoice}>
                Add choice
              </Button>
            </div>
            <div className="space-y-2">
              {choices.map((choice, index) => (
                <div
                  key={choice.tempId}
                  className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/70 bg-card p-3"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    {index + 1}
                  </div>
                  <Input
                    value={choice.content ?? ""}
                    onChange={(event) => handleChoiceChange(index, event.target.value)}
                    className="flex-1"
                  />
                  <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={Boolean(choice.isCorrect)}
                      onChange={() => toggleChoiceCorrect(index)}
                    />
                    Correct
                  </label>
                  <Button variant="ghost" size="sm" onClick={() => removeChoice(index)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Explanation
          </label>
          <Textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
          />
        </div>

        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
            {success}
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
