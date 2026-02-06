"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, FileText, Hash, User, BookOpen, Pencil, Check, X } from "lucide-react";

import {
  getLectureDetail,
  updateLecture,
  type ManageLectureDetail,
  type ManageLectureQuestion,
} from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export default function LectureDetailPage() {
  const params = useParams();
  const router = useRouter();
  const lectureId = params?.id as string;

  const [data, setData] = useState<ManageLectureDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline editing
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editProfessor, setEditProfessor] = useState("");
  const [saving, setSaving] = useState(false);

  // Question expansion
  const [expandedQ, setExpandedQ] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!lectureId) return;
    setLoading(true);
    getLectureDetail(lectureId)
      .then((result) => {
        setData(result);
        setEditTitle(result.lecture.title);
        setEditProfessor(result.lecture.professor ?? "");
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Unable to load lecture")
      )
      .finally(() => setLoading(false));
  }, [lectureId]);

  const handleSave = async () => {
    if (!data || !editTitle.trim()) return;
    setSaving(true);
    try {
      await updateLecture(data.lecture.id, {
        title: editTitle.trim(),
        professor: editProfessor.trim() || null,
      });
      setData({
        ...data,
        lecture: {
          ...data.lecture,
          title: editTitle.trim(),
          professor: editProfessor.trim() || null,
        },
      });
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save");
    } finally {
      setSaving(false);
    }
  };

  const toggleQuestion = (qId: number) => {
    setExpandedQ((prev) => {
      const next = new Set(prev);
      if (next.has(qId)) next.delete(qId);
      else next.add(qId);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center text-muted-foreground">
        Loading lecture details...
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">
            Lecture unavailable
          </p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const { lecture, block, questions, materials } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {block?.name ?? "Lecture"}
          </p>
          {editing ? (
            <div className="flex items-center gap-2 mt-1">
              <Input
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="h-8 text-xl font-semibold"
                placeholder="Lecture title"
              />
              <Input
                value={editProfessor}
                onChange={(e) => setEditProfessor(e.target.value)}
                className="h-8 w-40"
                placeholder="Professor"
              />
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <Check className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-semibold text-foreground">
                {lecture.title}
              </h2>
              {lecture.professor && (
                <span className="text-sm text-muted-foreground">
                  — {lecture.professor}
                </span>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0"
                onClick={() => setEditing(true)}
              >
                <Pencil className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <Hash className="h-6 w-6 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{questions.length}</p>
              <p className="text-xs text-muted-foreground">Classified Questions</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <FileText className="h-6 w-6 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{materials.length}</p>
              <p className="text-xs text-muted-foreground">PDF Materials</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <BookOpen className="h-6 w-6 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">
                {materials.reduce((acc, m) => acc + (m.chunks ?? 0), 0)}
              </p>
              <p className="text-xs text-muted-foreground">Indexed Chunks</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Materials */}
      {materials.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileText className="h-5 w-5" />
              Lecture Materials
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {materials.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between rounded border border-border/50 px-3 py-2"
              >
                <span className="text-sm truncate">
                  {m.originalFilename ?? "PDF"}
                </span>
                <div className="flex items-center gap-2">
                  <Badge variant={m.status === "indexed" ? "success" : "neutral"}>
                    {m.status ?? "unknown"}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {m.chunks ?? 0} chunks
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Questions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Hash className="h-5 w-5" />
            Classified Questions ({questions.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {questions.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No questions classified to this lecture yet.
            </p>
          ) : (
            questions.map((q: ManageLectureQuestion) => (
              <Collapsible
                key={q.id}
                open={expandedQ.has(q.id)}
                onOpenChange={() => toggleQuestion(q.id)}
              >
                <CollapsibleTrigger asChild>
                  <button className="flex w-full items-center justify-between rounded border border-border/50 px-3 py-2 text-left hover:bg-muted/30">
                    <div className="flex items-center gap-2">
                      <Badge variant="neutral">Q{q.questionNumber}</Badge>
                      <span className="text-sm font-medium truncate max-w-md">
                        {q.content?.slice(0, 60) ??
                          `Question ${q.questionNumber}`}
                        {(q.content?.length ?? 0) > 60 ? "…" : ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {q.examTitle && (
                        <span className="text-xs text-muted-foreground">
                          {q.examTitle}
                        </span>
                      )}
                      <Badge variant="neutral">{q.type ?? "MC"}</Badge>
                    </div>
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="rounded-b border border-t-0 border-border/50 bg-muted/20 px-3 py-3">
                  <div className="space-y-2 text-sm">
                    <p className="whitespace-pre-wrap">{q.content}</p>
                    {q.choices && q.choices.length > 0 && (
                      <ul className="list-inside list-decimal space-y-1 pl-2">
                        {q.choices.map((c, i) => (
                          <li
                            key={c.id ?? i}
                            className={c.isCorrect ? "font-semibold text-success" : ""}
                          >
                            {c.content}
                          </li>
                        ))}
                      </ul>
                    )}
                    {q.answer && (
                      <p className="text-xs text-muted-foreground">
                        <span className="font-semibold">Answer:</span> {q.answer}
                      </p>
                    )}
                    {q.explanation && (
                      <p className="text-xs text-muted-foreground">
                        <span className="font-semibold">Explanation:</span>{" "}
                        {q.explanation}
                      </p>
                    )}
                    <div className="pt-2">
                      <Link
                        href={`/manage/questions/${q.id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        Edit question →
                      </Link>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
