"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  FileText,
  Hash,
  BookOpen,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";

import {
  deleteLectureMaterial,
  getLectureDetail,
  getLectures,
  uploadLectureMaterial,
  updateLecture,
  type ManageLecture,
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
  const [lectureList, setLectureList] = useState<ManageLecture[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingMaterialId, setDeletingMaterialId] = useState<number | null>(null);

  // Inline editing
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editProfessor, setEditProfessor] = useState("");
  const [saving, setSaving] = useState(false);

  // Question expansion
  const [expandedQ, setExpandedQ] = useState<Set<number>>(new Set());

  const loadLectureDetail = useCallback(async () => {
    if (!lectureId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [detailResult, lecturesResult] = await Promise.all([
        getLectureDetail(lectureId),
        getLectures(),
      ]);
      setData(detailResult);
      setLectureList(lecturesResult);
      setEditTitle(detailResult.lecture.title);
      setEditProfessor(detailResult.lecture.professor ?? "");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Unable to load lecture");
    } finally {
      setLoading(false);
    }
  }, [lectureId]);

  const lectureIdNumber = useMemo(() => Number(lectureId), [lectureId]);

  const orderedLectures = useMemo(
    () =>
      [...lectureList].sort((a, b) => {
        const subjectCmp = (a.blockSubject ?? "").localeCompare(
          b.blockSubject ?? "",
          "ko"
        );
        if (subjectCmp !== 0) return subjectCmp;
        const blockNameCmp = (a.blockName ?? "").localeCompare(
          b.blockName ?? "",
          "ko"
        );
        if (blockNameCmp !== 0) return blockNameCmp;
        const blockIdCmp = (a.blockId ?? 0) - (b.blockId ?? 0);
        if (blockIdCmp !== 0) return blockIdCmp;
        const orderCmp = (a.order ?? 0) - (b.order ?? 0);
        if (orderCmp !== 0) return orderCmp;
        return a.title.localeCompare(b.title, "ko");
      }),
    [lectureList]
  );

  const currentLectureIndex = useMemo(
    () => orderedLectures.findIndex((lecture) => lecture.id === lectureIdNumber),
    [orderedLectures, lectureIdNumber]
  );

  const previousLecture = useMemo(() => {
    if (currentLectureIndex <= 0) return null;
    return orderedLectures[currentLectureIndex - 1] ?? null;
  }, [orderedLectures, currentLectureIndex]);

  const nextLecture = useMemo(() => {
    if (currentLectureIndex < 0 || currentLectureIndex >= orderedLectures.length - 1) {
      return null;
    }
    return orderedLectures[currentLectureIndex + 1] ?? null;
  }, [orderedLectures, currentLectureIndex]);

  const moveToLecture = useCallback(
    (targetLectureId: number | null | undefined) => {
      if (!targetLectureId || targetLectureId === lectureIdNumber) return;
      router.push(`/manage/lectures/${targetLectureId}`);
    },
    [router, lectureIdNumber]
  );

  useEffect(() => {
    void loadLectureDetail();
  }, [loadLectureDetail]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;

      const target = event.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName.toLowerCase();
        if (
          tagName === "input" ||
          tagName === "textarea" ||
          target.isContentEditable
        ) {
          return;
        }
      }

      if (event.key === "ArrowLeft" && previousLecture) {
        event.preventDefault();
        moveToLecture(previousLecture.id);
      } else if (event.key === "ArrowRight" && nextLecture) {
        event.preventDefault();
        moveToLecture(nextLecture.id);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [moveToLecture, previousLecture, nextLecture]);

  const handleSave = async () => {
    if (!data || !editTitle.trim()) return;
    setActionError(null);
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
      setActionError(err instanceof Error ? err.message : "Unable to save");
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

  const handleMaterialUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;

    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setActionError("Only PDF files are allowed.");
      input.value = "";
      return;
    }

    setActionError(null);
    setUploadMessage(null);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("pdf_file", file);
      const result = await uploadLectureMaterial(lectureId, formData);
      const indexedChunks = result.chunks ?? 0;
      setUploadMessage(`Uploaded and indexed "${file.name}" (${indexedChunks} chunks).`);
      await loadLectureDetail();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to upload lecture PDF");
    } finally {
      setUploading(false);
      input.value = "";
    }
  };

  const handleDeleteMaterial = async (
    materialId: number,
    originalFilename?: string | null
  ) => {
    const displayName = originalFilename ?? "PDF";
    const confirmed = window.confirm(
      `Delete "${displayName}" and all indexed chunks from this lecture?`
    );
    if (!confirmed) return;

    setActionError(null);
    setUploadMessage(null);
    setDeletingMaterialId(materialId);
    try {
      await deleteLectureMaterial(lectureId, materialId);
      setUploadMessage(`Deleted "${displayName}" and removed indexed chunks.`);
      await loadLectureDetail();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to delete lecture PDF");
    } finally {
      setDeletingMaterialId((prev) => (prev === materialId ? null : prev));
    }
  };

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center text-muted-foreground">
        Loading lecture details...
      </div>
    );
  }

  if (loadError || !data) {
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">
            Lecture unavailable
          </p>
          <p className="text-sm text-muted-foreground">{loadError}</p>
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
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => moveToLecture(previousLecture?.id)}
            disabled={!previousLecture}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => moveToLecture(nextLecture?.id)}
            disabled={!nextLecture}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Use ← / → to move to previous or next lecture.
      </p>

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
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <FileText className="h-5 w-5" />
            Lecture Materials
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Upload PDF for indexing
            </label>
            <Input
              type="file"
              accept="application/pdf"
              onChange={handleMaterialUpload}
              disabled={uploading}
            />
            <p className="text-xs text-muted-foreground">
              {uploading ? "Uploading and indexing..." : "New uploads are indexed immediately for AI classification."}
            </p>
          </div>

          {uploadMessage && (
            <div className="rounded border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
              {uploadMessage}
            </div>
          )}
          {actionError && (
            <div className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              {actionError}
            </div>
          )}

          {materials.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No materials uploaded yet.
            </p>
          ) : (
            materials.map((m) => (
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
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 px-2 text-danger hover:bg-danger/10 hover:text-danger"
                    onClick={() => handleDeleteMaterial(m.id, m.originalFilename)}
                    disabled={deletingMaterialId === m.id || uploading}
                  >
                    <Trash2 className="mr-1 h-3.5 w-3.5" />
                    Delete
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

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
