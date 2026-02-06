"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  GripVertical,
  Minus,
  Pencil,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";

import {
  createBlock,
  createLecture,
  createSubject,
  deleteBlock,
  deleteLecture,
  getBlocks,
  getLectures,
  getLecture,
  getSubjects,
  updateSubject,
  updateBlock,
  updateLecture,
  type ManageBlock,
  type ManageLecture,
  type ManageSubject,
} from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useLanguage } from "@/context/LanguageContext";
import { cn } from "@/lib/utils";

type SubjectGroup = {
  name: string;
  id?: number;
  isUnassigned?: boolean;
  blocks: ManageBlock[];
};

export function CurriculumManager() {
  const { t } = useLanguage();
  const [blocks, setBlocks] = useState<ManageBlock[]>([]);
  const [lectures, setLectures] = useState<ManageLecture[]>([]);
  const [subjects, setSubjects] = useState<ManageSubject[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedBlocks, setExpandedBlocks] = useState<Set<number>>(new Set());

  const [newSubjectName, setNewSubjectName] = useState("");
  const [creatingSubject, setCreatingSubject] = useState(false);
  const [showNewSubject, setShowNewSubject] = useState(false);

  const [addingBlockSubject, setAddingBlockSubject] = useState<string | null>(null);
  const [newBlockName, setNewBlockName] = useState("");

  const [editingBlockId, setEditingBlockId] = useState<number | null>(null);
  const [editingBlockName, setEditingBlockName] = useState("");
  const [editingBlockSubject, setEditingBlockSubject] = useState("");
  const [editingBlockSubjectCustom, setEditingBlockSubjectCustom] = useState("");

  const [addingLectureBlockId, setAddingLectureBlockId] = useState<number | null>(null);
  const [newLectureTitle, setNewLectureTitle] = useState("");
  const [newLectureProfessor, setNewLectureProfessor] = useState("");

  const [activeLectureId, setActiveLectureId] = useState<number | null>(null);
  const [lectureDetail, setLectureDetail] = useState<ManageLecture | null>(null);
  const [lectureLoading, setLectureLoading] = useState(false);
  const [lectureSaving, setLectureSaving] = useState(false);
  const [lectureError, setLectureError] = useState<string | null>(null);

  const [dragSubjectId, setDragSubjectId] = useState<number | null>(null);
  const [dragBlockId, setDragBlockId] = useState<number | null>(null);
  const [dragLectureId, setDragLectureId] = useState<number | null>(null);
  const [dragOverSubjectId, setDragOverSubjectId] = useState<number | null>(null);
  const [dragOverBlockId, setDragOverBlockId] = useState<number | null>(null);
  const [dragOverLectureId, setDragOverLectureId] = useState<number | null>(null);

  const isDragging = Boolean(dragSubjectId || dragBlockId || dragLectureId);

  const unassignedSubjectLabel = t("manage.unassignedSubject");

  const refreshData = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const [blocksData, lecturesData, subjectsData] = await Promise.all([
        getBlocks(),
        getLectures(),
        getSubjects(),
      ]);
      setBlocks(blocksData);
      setLectures(lecturesData);
      setSubjects(subjectsData);
      if (activeLectureId && !lecturesData.find((l) => l.id === activeLectureId)) {
        setActiveLectureId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.curriculumLoadError"));
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const [blocksData, lecturesData, subjectsData] = await Promise.all([
          getBlocks(),
          getLectures(),
          getSubjects(),
        ]);
        if (cancelled) return;
        setBlocks(blocksData);
        setLectures(lecturesData);
        setSubjects(subjectsData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("manage.curriculumLoadError"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [t, unassignedSubjectLabel]);

  useEffect(() => {
    if (!activeLectureId) {
      setLectureDetail(null);
      setLectureError(null);
      return;
    }
    let cancelled = false;
    setLectureLoading(true);
    setLectureError(null);
    getLecture(activeLectureId)
      .then((data) => {
        if (!cancelled) setLectureDetail(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setLectureDetail(null);
          setLectureError(err instanceof Error ? err.message : t("manage.lectureLoadError"));
        }
      })
      .finally(() => {
        if (!cancelled) setLectureLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeLectureId, t]);

  const lecturesByBlock = useMemo(() => {
    const map = new Map<number, ManageLecture[]>();
    lectures.forEach((lecture) => {
      const list = map.get(lecture.blockId) ?? [];
      list.push(lecture);
      map.set(lecture.blockId, list);
    });
    map.forEach((list) => {
      list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || a.title.localeCompare(b.title));
    });
    return map;
  }, [lectures]);

  const subjectsGrouped = useMemo<SubjectGroup[]>(() => {
    const map = new Map<string, ManageBlock[]>();
    blocks.forEach((block) => {
      const subjectName = (block.subject ?? unassignedSubjectLabel).trim();
      const list = map.get(subjectName) ?? [];
      list.push(block);
      map.set(subjectName, list);
    });
    const subjectMap = new Map<string, ManageSubject>();
    subjects.forEach((subject) => {
      const name = subject.name.trim();
      if (!name) return;
      subjectMap.set(name, subject);
      if (!map.has(name)) {
        map.set(name, []);
      }
    });

    const subjectOrder = new Map(
      subjects.map((subject) => [subject.name.trim(), subject.order ?? 0])
    );

    const groups = Array.from(map.entries()).map(([name, list]) => {
      const subject = subjectMap.get(name);
      return {
        name,
        id: subject?.id,
        isUnassigned: name === unassignedSubjectLabel,
        blocks: list.sort(
          (a, b) => (a.order ?? 0) - (b.order ?? 0) || a.name.localeCompare(b.name)
        ),
      };
    });

    return groups.sort((a, b) => {
      if (a.isUnassigned) return 1;
      if (b.isUnassigned) return -1;
      const orderA = subjectOrder.get(a.name);
      const orderB = subjectOrder.get(b.name);
      if (orderA != null && orderB != null && orderA !== orderB) {
        return orderA - orderB;
      }
      if (orderA != null && orderB == null) return -1;
      if (orderA == null && orderB != null) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [blocks, subjects, unassignedSubjectLabel]);

  const subjectOptions = useMemo(() => subjects.map((s) => s.name), [subjects]);
  const resolvedEditBlockSubject =
    editingBlockSubject === "__custom"
      ? editingBlockSubjectCustom.trim()
      : editingBlockSubject;

  const handleStartAddBlock = (subjectName: string) => {
    setAddingBlockSubject((prev) => (prev === subjectName ? null : subjectName));
    setNewBlockName("");
  };

  const resetDragState = () => {
    setDragSubjectId(null);
    setDragBlockId(null);
    setDragLectureId(null);
    setDragOverSubjectId(null);
    setDragOverBlockId(null);
    setDragOverLectureId(null);
  };

  const handleCreateSubject = async () => {
    if (!newSubjectName.trim()) return;
    setError(null);
    setCreatingSubject(true);
    try {
      await createSubject({ name: newSubjectName.trim() });
      setNewSubjectName("");
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.subjectCreateError"));
    } finally {
      setCreatingSubject(false);
    }
  };

  const handleCreateBlock = async () => {
    if (!newBlockName.trim() || !addingBlockSubject) return;
    setError(null);
    const subjectValue =
      addingBlockSubject === unassignedSubjectLabel ? null : addingBlockSubject;
    try {
      await createBlock({
        name: newBlockName.trim(),
        subject: subjectValue,
      });
      setAddingBlockSubject(null);
      setNewBlockName("");
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.blockCreateError"));
    }
  };

  const handleDeleteBlock = async (block: ManageBlock) => {
    const confirmed = window.confirm(t("manage.blockDeleteConfirm"));
    if (!confirmed) return;
    setError(null);
    try {
      await deleteBlock(block.id);
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.blockDeleteError"));
    }
  };

  const handleStartEditBlock = (block: ManageBlock) => {
    setEditingBlockId(block.id);
    setEditingBlockName(block.name);
    if (block.subject) {
      if (subjectOptions.includes(block.subject)) {
        setEditingBlockSubject(block.subject);
        setEditingBlockSubjectCustom("");
      } else {
        setEditingBlockSubject("__custom");
        setEditingBlockSubjectCustom(block.subject);
      }
    } else {
      setEditingBlockSubject("");
      setEditingBlockSubjectCustom("");
    }
  };

  const handleSaveEditBlock = async () => {
    if (!editingBlockId || !editingBlockName.trim()) return;
    setError(null);
    try {
      await updateBlock(editingBlockId, {
        name: editingBlockName.trim(),
        subject: resolvedEditBlockSubject || null,
      });
      setEditingBlockId(null);
      setEditingBlockName("");
      setEditingBlockSubject("");
      setEditingBlockSubjectCustom("");
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.blockUpdateError"));
    }
  };

  const handleCreateLecture = async (blockId: number) => {
    if (!newLectureTitle.trim()) return;
    setError(null);
    try {
      const nextOrder =
        Math.max(
          0,
          ...(lecturesByBlock.get(blockId) ?? []).map((l) => l.order ?? 0)
        ) + 1;
      await createLecture(blockId, {
        title: newLectureTitle.trim(),
        professor: newLectureProfessor.trim() || null,
        order: nextOrder,
      });
      setAddingLectureBlockId(null);
      setNewLectureTitle("");
      setNewLectureProfessor("");
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.lectureCreateError"));
    }
  };

  const handleDeleteLecture = async (lectureId: number) => {
    const confirmed = window.confirm(t("manage.lectureDeleteConfirm"));
    if (!confirmed) return;
    setLectureError(null);
    try {
      await deleteLecture(lectureId);
      if (activeLectureId === lectureId) {
        setActiveLectureId(null);
      }
      await refreshData();
    } catch (err) {
      setLectureError(err instanceof Error ? err.message : t("manage.lectureDeleteError"));
    }
  };

  const handleSaveLecture = async () => {
    if (!lectureDetail) return;
    if (!lectureDetail.title.trim()) {
      setLectureError(t("manage.lectureTitleRequired"));
      return;
    }
    setLectureSaving(true);
    setLectureError(null);
    try {
      await updateLecture(lectureDetail.id, {
        title: lectureDetail.title.trim(),
        professor: lectureDetail.professor?.trim() || null,
        description: lectureDetail.description?.trim() || null,
      });
      await refreshData();
    } catch (err) {
      setLectureError(err instanceof Error ? err.message : t("manage.lectureUpdateError"));
    } finally {
      setLectureSaving(false);
    }
  };

  const moveItem = <T,>(list: T[], fromIndex: number, toIndex: number) => {
    const next = [...list];
    const [item] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, item);
    return next;
  };

  const handleSubjectDrop = async (targetId: number) => {
    if (!dragSubjectId || dragSubjectId === targetId) return;
    try {
      const orderedSubjects = [...subjects].sort((a, b) => {
        const orderA = a.order ?? 0;
        const orderB = b.order ?? 0;
        if (orderA !== orderB) return orderA - orderB;
        return a.name.localeCompare(b.name);
      });
      const originalOrder = new Map(
        orderedSubjects.map((subject) => [subject.id, subject.order ?? 0])
      );
      const fromIndex = orderedSubjects.findIndex((item) => item.id === dragSubjectId);
      const toIndex = orderedSubjects.findIndex((item) => item.id === targetId);
      if (fromIndex === -1 || toIndex === -1) return;
      const reordered = moveItem(orderedSubjects, fromIndex, toIndex).map(
        (subject, index) => ({ ...subject, order: index + 1 })
      );
      setSubjects(reordered);
      const updates = reordered.filter(
        (subject) => originalOrder.get(subject.id) !== (subject.order ?? 0)
      );
      if (updates.length) {
        await Promise.all(
          updates.map((subject) => updateSubject(subject.id, { order: subject.order }))
        );
        await refreshData();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.subjectUpdateError"));
    } finally {
      resetDragState();
    }
  };

  const handleBlockDrop = async (targetBlockId: number, subjectName: string) => {
    if (!dragBlockId || dragBlockId === targetBlockId) return;
    try {
      const groupBlocks = blocks
        .filter(
          (block) =>
            (block.subject ?? unassignedSubjectLabel).trim() === subjectName
        )
        .sort(
          (a, b) => (a.order ?? 0) - (b.order ?? 0) || a.name.localeCompare(b.name)
        );
      const fromIndex = groupBlocks.findIndex((block) => block.id === dragBlockId);
      const toIndex = groupBlocks.findIndex((block) => block.id === targetBlockId);
      if (fromIndex === -1 || toIndex === -1) return;
      const reordered = moveItem(groupBlocks, fromIndex, toIndex).map(
        (block, index) => ({ ...block, order: index + 1 })
      );
      setBlocks((prev) =>
        prev.map((block) => {
          const updated = reordered.find((item) => item.id === block.id);
          return updated ? { ...block, order: updated.order } : block;
        })
      );
      await Promise.all(
        reordered.map((block) => updateBlock(block.id, { order: block.order ?? 0 }))
      );
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("manage.blockUpdateError"));
    } finally {
      resetDragState();
    }
  };

  const handleLectureDrop = async (targetLectureId: number, blockId: number) => {
    if (!dragLectureId || dragLectureId === targetLectureId) return;
    try {
      const lectureList = (lecturesByBlock.get(blockId) ?? []).slice();
      const fromIndex = lectureList.findIndex((lecture) => lecture.id === dragLectureId);
      const toIndex = lectureList.findIndex((lecture) => lecture.id === targetLectureId);
      if (fromIndex === -1 || toIndex === -1) return;
      const reordered = moveItem(lectureList, fromIndex, toIndex).map(
        (lecture, index) => ({ ...lecture, order: index + 1 })
      );
      setLectures((prev) =>
        prev.map((lecture) => {
          const updated = reordered.find((item) => item.id === lecture.id);
          return updated ? { ...lecture, order: updated.order } : lecture;
        })
      );
      await Promise.all(
        reordered.map((lecture) =>
          updateLecture(lecture.id, { order: lecture.order ?? 0 })
        )
      );
      await refreshData();
    } catch (err) {
      setLectureError(err instanceof Error ? err.message : t("manage.lectureUpdateError"));
    } finally {
      resetDragState();
    }
  };

  const toggleBlock = (blockId: number) => {
    setExpandedBlocks((prev) => {
      const next = new Set(prev);
      if (next.has(blockId)) next.delete(blockId);
      else next.add(blockId);
      return next;
    });
  };

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {t("manage.curriculumLabel")}
          </p>
          <h2 className="text-2xl font-semibold text-foreground">{t("manage.curriculum")}</h2>
        </div>
        <Button variant="outline" size="sm" onClick={refreshData} disabled={refreshing}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {refreshing ? t("common.refreshing") : t("common.refresh")}
        </Button>
      </div>

      {error && (
        <Card className="border border-danger/40 bg-danger/10">
          <CardContent className="p-4 text-sm text-danger">{error}</CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {t("manage.subjects")}
              </span>
              <div className="flex items-center gap-2">
                {isDragging && (
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {t("manage.dragHint")}
                  </span>
                )}
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-6 w-6"
                  onClick={() => {
                    setShowNewSubject(!showNewSubject);
                    if (!showNewSubject) setNewSubjectName("");
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {showNewSubject && (
              <div className="animate-in slide-in-from-top-2 fade-in duration-200 rounded-lg border-2 border-dashed border-border/60 bg-muted/30 p-4 mb-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {t("manage.addSubjectLabel")}
                    </p>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6"
                    onClick={() => setShowNewSubject(false)}
                  >
                    <X className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Input
                    value={newSubjectName}
                    onChange={(event) => setNewSubjectName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        handleCreateSubject();
                      }
                      if (event.key === "Escape") {
                        setShowNewSubject(false);
                      }
                    }}
                    placeholder={t("manage.addSubjectPlaceholder")}
                    className="min-w-[180px] flex-1"
                    autoFocus
                  />
                  <Button
                    size="sm"
                    onClick={handleCreateSubject}
                    disabled={!newSubjectName.trim() || creatingSubject}
                  >
                    {creatingSubject ? t("manage.subjectCreating") : t("manage.addSubjectAction")}
                  </Button>
                </div>
              </div>
            )}

            <div className="space-y-4">
              {subjectsGrouped.map((group) => {
                const isSubjectDragging = dragSubjectId === group.id;
                const isSubjectDragTarget =
                  dragOverSubjectId === group.id &&
                  dragSubjectId !== null &&
                  dragSubjectId !== group.id;
                return (
                  <div
                    key={group.name}
                    className={cn(
                      "space-y-3 rounded-lg border border-border/60 bg-muted/20 p-3 transition",
                      isSubjectDragging && "opacity-70",
                      isSubjectDragTarget && "ring-2 ring-primary/40 bg-primary/5"
                    )}
                    onDragEnter={(event) => {
                      if (group.id && !group.isUnassigned) {
                        event.preventDefault();
                        setDragOverSubjectId(group.id);
                      }
                    }}
                    onDragOver={(event) => {
                      if (group.id && !group.isUnassigned) {
                        event.preventDefault();
                        event.dataTransfer.dropEffect = "move";
                        setDragOverSubjectId(group.id);
                      }
                    }}
                    onDragLeave={(event) => {
                      const related = event.relatedTarget as Node | null;
                      if (related && event.currentTarget.contains(related)) return;
                      setDragOverSubjectId(null);
                    }}
                    onDrop={() => {
                      if (group.id && !group.isUnassigned) {
                        handleSubjectDrop(group.id);
                      }
                      setDragOverSubjectId(null);
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {group.id && !group.isUnassigned && (
                          <span
                            className="cursor-grab text-muted-foreground/60 hover:text-muted-foreground active:cursor-grabbing"
                            draggable
                            onDragStart={(event) => {
                              event.dataTransfer.effectAllowed = "move";
                              event.dataTransfer.setData("text/plain", String(group.id));
                              setDragOverSubjectId(null);
                              setDragOverBlockId(null);
                              setDragOverLectureId(null);
                              setDragSubjectId(group.id!);
                            }}
                            onDragEnd={resetDragState}
                          >
                            <GripVertical className="h-4 w-4" />
                          </span>
                        )}
                        <span className="text-sm font-semibold text-foreground">{group.name}</span>
                        <Badge variant="neutral">{group.blocks.length}</Badge>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => handleStartAddBlock(group.name)}
                      >
                        <Plus className="mr-1 h-3 w-3" />
                        {t("manage.addBlock")}
                      </Button>
                    </div>

                    {isSubjectDragTarget && (
                      <div className="rounded-md border border-dashed border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                        {t("manage.dropHere")}
                      </div>
                    )}

                    {addingBlockSubject === group.name && (
                      <div className="animate-in slide-in-from-top-1 fade-in duration-150 rounded-lg border border-dashed border-border/60 bg-muted/30 p-3">
                        <div className="flex items-center gap-2">
                          <Input
                            value={newBlockName}
                            onChange={(event) => setNewBlockName(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                handleCreateBlock();
                              }
                              if (event.key === "Escape") {
                                setAddingBlockSubject(null);
                              }
                            }}
                            placeholder={t("manage.blockNamePlaceholder")}
                            className="flex-1"
                            autoFocus
                          />
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-9 w-9 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={handleCreateBlock}
                            disabled={!newBlockName.trim()}
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-9 w-9 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => setAddingBlockSubject(null)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      {group.blocks.length === 0 && (
                        <p className="text-xs text-muted-foreground">{t("manage.noBlocks")}</p>
                      )}
                      {group.blocks.map((block) => {
                        const isBlockOpen = expandedBlocks.has(block.id);
                        const isEditing = editingBlockId === block.id;
                        const lectureList = lecturesByBlock.get(block.id) ?? [];

                        const isBlockDragging = dragBlockId === block.id;
                        const isBlockDragTarget =
                          dragOverBlockId === block.id &&
                          dragBlockId !== null &&
                          dragBlockId !== block.id;

                        return (
                          <div
                            key={block.id}
                            className={cn(
                              "space-y-2 rounded-lg border border-border/70 bg-card/80 p-3 transition",
                              isBlockDragging && "opacity-70",
                              isBlockDragTarget && "ring-2 ring-primary/40 bg-primary/5"
                            )}
                            onDragEnter={(event) => {
                              event.preventDefault();
                              setDragOverBlockId(block.id);
                            }}
                            onDragOver={(event) => {
                              event.preventDefault();
                              event.dataTransfer.dropEffect = "move";
                              setDragOverBlockId(block.id);
                            }}
                            onDragLeave={(event) => {
                              const related = event.relatedTarget as Node | null;
                              if (related && event.currentTarget.contains(related)) return;
                              setDragOverBlockId(null);
                            }}
                            onDrop={() => {
                              handleBlockDrop(block.id, group.name);
                              setDragOverBlockId(null);
                            }}
                          >
                            {isEditing ? (
                              <div className="space-y-2">
                                <Input
                                  value={editingBlockName}
                                  onChange={(event) => setEditingBlockName(event.target.value)}
                                />
                                <Select
                                  value={editingBlockSubject}
                                  onChange={(event) => setEditingBlockSubject(event.target.value)}
                                >
                                  <option value="">{t("manage.subjectSelect")}</option>
                                  {subjectOptions.map((item) => (
                                    <option key={item} value={item}>
                                      {item}
                                    </option>
                                  ))}
                                  <option value="__custom">{t("manage.custom")}</option>
                                </Select>
                                {editingBlockSubject === "__custom" && (
                                  <Input
                                    value={editingBlockSubjectCustom}
                                    onChange={(event) =>
                                      setEditingBlockSubjectCustom(event.target.value)
                                    }
                                    placeholder={t("manage.subjectCustomPlaceholder")}
                                  />
                                )}
                                <div className="flex justify-end gap-2">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setEditingBlockId(null)}
                                  >
                                    {t("common.cancel")}
                                  </Button>
                                  <Button
                                    size="sm"
                                    onClick={handleSaveEditBlock}
                                    disabled={!editingBlockName.trim()}
                                  >
                                    {t("common.save")}
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <div className="group flex items-center justify-between gap-2">
                                <div className="flex flex-1 items-center gap-2">
                                  <span
                                    className="cursor-grab text-muted-foreground/60 hover:text-muted-foreground active:cursor-grabbing"
                                    draggable
                                    onDragStart={(event) => {
                                      event.dataTransfer.effectAllowed = "move";
                                      event.dataTransfer.setData("text/plain", String(block.id));
                                      setDragOverSubjectId(null);
                                      setDragOverBlockId(null);
                                      setDragOverLectureId(null);
                                      setDragBlockId(block.id);
                                    }}
                                    onDragEnd={resetDragState}
                                  >
                                    <GripVertical className="h-4 w-4" />
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => toggleBlock(block.id)}
                                    className="flex flex-1 items-center gap-2 text-left"
                                  >
                                    {isBlockOpen ? (
                                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                    )}
                                    <span className="font-semibold text-foreground">
                                      {block.name}
                                    </span>
                                  </button>
                                </div>
                                <Badge variant="neutral">{lectureList.length}</Badge>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 w-6 p-0"
                                  onClick={() => handleStartEditBlock(block)}
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 w-6 p-0 text-danger opacity-0 pointer-events-none transition-opacity group-hover:opacity-100 group-hover:pointer-events-auto hover:text-danger"
                                  onClick={() => handleDeleteBlock(block)}
                                >
                                  <Minus className="h-3 w-3" />
                                </Button>
                              </div>
                            )}

                            {isBlockDragTarget && (
                              <div className="rounded-md border border-dashed border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                                {t("manage.dropHere")}
                              </div>
                            )}

                            {isBlockOpen && !isEditing && (
                              <div className="space-y-2 border-l border-border/60 pl-4">
                                {lectureList.length === 0 ? (
                                  <p className="text-xs text-muted-foreground">
                                    {t("manage.noLectures")}
                                  </p>
                                ) : (
                                  lectureList.map((lecture) => {
                                    const isLectureDragging = dragLectureId === lecture.id;
                                    const isLectureDragTarget =
                                      dragOverLectureId === lecture.id &&
                                      dragLectureId !== null &&
                                      dragLectureId !== lecture.id;
                                    return (
                                      <div
                                        key={lecture.id}
                                        className={cn(
                                          "flex items-center gap-2 rounded-md transition",
                                          isLectureDragging && "opacity-70",
                                          isLectureDragTarget && "ring-2 ring-primary/40 bg-primary/5"
                                        )}
                                        onDragEnter={(event) => {
                                          event.preventDefault();
                                          setDragOverLectureId(lecture.id);
                                        }}
                                        onDragOver={(event) => {
                                          event.preventDefault();
                                          event.dataTransfer.dropEffect = "move";
                                          setDragOverLectureId(lecture.id);
                                        }}
                                        onDragLeave={(event) => {
                                          const related = event.relatedTarget as Node | null;
                                          if (related && event.currentTarget.contains(related)) return;
                                          setDragOverLectureId(null);
                                        }}
                                        onDrop={() => {
                                          handleLectureDrop(lecture.id, block.id);
                                          setDragOverLectureId(null);
                                        }}
                                      >
                                        <span
                                          className="cursor-grab text-muted-foreground/60 hover:text-muted-foreground active:cursor-grabbing"
                                          draggable
                                          onDragStart={(event) => {
                                            event.dataTransfer.effectAllowed = "move";
                                            event.dataTransfer.setData(
                                              "text/plain",
                                              String(lecture.id)
                                            );
                                            setDragOverSubjectId(null);
                                            setDragOverBlockId(null);
                                            setDragOverLectureId(null);
                                            setDragLectureId(lecture.id);
                                          }}
                                          onDragEnd={resetDragState}
                                        >
                                          <GripVertical className="h-3 w-3" />
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() => setActiveLectureId(lecture.id)}
                                          className={`flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm transition ${activeLectureId === lecture.id
                                            ? "bg-primary/10 text-primary"
                                            : "hover:bg-muted/40"
                                            }`}
                                        >
                                          <div className="min-w-0 flex-1">
                                            <div className="truncate font-medium">{lecture.title}</div>
                                            {lecture.professor && (
                                              <div className="text-xs text-muted-foreground">
                                                {lecture.professor}
                                              </div>
                                            )}
                                          </div>
                                          <div className="flex items-center gap-2">
                                            {isLectureDragTarget && (
                                              <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                                                {t("manage.dropHere")}
                                              </span>
                                            )}
                                            <Badge variant="neutral">
                                              {lecture.questionCount ?? 0}
                                            </Badge>
                                          </div>
                                        </button>
                                      </div>
                                    );
                                  })
                                )}

                                {addingLectureBlockId === block.id ? (
                                  <div className="space-y-2 rounded-md border border-border/70 bg-muted/40 p-2">
                                    <Input
                                      value={newLectureTitle}
                                      onChange={(event) => setNewLectureTitle(event.target.value)}
                                      placeholder={t("manage.lectureTitlePlaceholder")}
                                    />
                                    <Input
                                      value={newLectureProfessor}
                                      onChange={(event) =>
                                        setNewLectureProfessor(event.target.value)
                                      }
                                      placeholder={t("manage.lectureProfessorPlaceholder")}
                                    />
                                    <div className="flex justify-end gap-2">
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => setAddingLectureBlockId(null)}
                                      >
                                        {t("common.cancel")}
                                      </Button>
                                      <Button
                                        size="sm"
                                        onClick={() => handleCreateLecture(block.id)}
                                        disabled={!newLectureTitle.trim()}
                                      >
                                        {t("manage.addLecture")}
                                      </Button>
                                    </div>
                                  </div>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="w-full justify-start text-xs"
                                    onClick={() => setAddingLectureBlockId(block.id)}
                                  >
                                    <Plus className="mr-2 h-4 w-4" />
                                    {t("manage.addLecture")}
                                  </Button>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              {subjectsGrouped.length === 0 && !addingBlockSubject && (
                <div className="rounded-md border border-dashed border-border/70 p-4 text-center text-sm text-muted-foreground">
                  {t("manage.noBlocks")}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-5 p-6">
            {!activeLectureId && (
              <div className="space-y-2 text-sm text-muted-foreground">
                <p className="text-lg font-semibold text-foreground">
                  {t("manage.lectureDetailTitle")}
                </p>
                <p>{t("manage.lectureSelectHint")}</p>
              </div>
            )}

            {activeLectureId && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {t("manage.lectureDetailTitle")}
                    </p>
                    <h3 className="text-xl font-semibold text-foreground">
                      {lectureDetail?.title ?? t("common.loading")}
                    </h3>
                    {lectureDetail?.blockName && (
                      <p className="text-sm text-muted-foreground">
                        {lectureDetail.blockName}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/manage/lectures/${activeLectureId}`}>
                        {t("manage.openLectureDetail")}
                      </Link>
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeleteLecture(activeLectureId)}
                    >
                      {t("manage.deleteLecture")}
                    </Button>
                  </div>
                </div>

                {lectureLoading ? (
                  <div className="space-y-2">
                    <div className="h-4 rounded bg-muted animate-pulse" />
                    <div className="h-4 rounded bg-muted animate-pulse" />
                    <div className="h-4 rounded bg-muted animate-pulse" />
                  </div>
                ) : lectureDetail ? (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                          {t("manage.lectureTitle")}
                        </label>
                        <Input
                          value={lectureDetail.title}
                          onChange={(event) =>
                            setLectureDetail({ ...lectureDetail, title: event.target.value })
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                          {t("manage.lectureProfessor")}
                        </label>
                        <Input
                          value={lectureDetail.professor ?? ""}
                          onChange={(event) =>
                            setLectureDetail({
                              ...lectureDetail,
                              professor: event.target.value,
                            })
                          }
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        {t("manage.lectureDescription")}
                      </label>
                      <Textarea
                        value={lectureDetail.description ?? ""}
                        onChange={(event) =>
                          setLectureDetail({
                            ...lectureDetail,
                            description: event.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge variant="neutral">
                        {t("manage.questions")}: {lectureDetail.questionCount ?? 0}
                      </Badge>
                      <Button onClick={handleSaveLecture} disabled={lectureSaving}>
                        {lectureSaving ? t("manage.lectureSaving") : t("manage.lectureSave")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">{t("manage.lectureLoadError")}</p>
                )}

                {lectureError && (
                  <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
                    {lectureError}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
