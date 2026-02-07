"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useRef } from "react";
import { Folder, FolderOpen, Minus, Pencil, Plus, RefreshCw, X, Check } from "lucide-react";

import {
  createBlock,
  createLecture,
  deleteBlock,
  deleteLecture,
  getBlocks,
  getBlockWorkspace,
  updateBlock,
  updateLecture,
  type ManageBlock,
  type ManageBlockWorkspace,
  type ManageLecture,
} from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type LibraryExplorerProps = {
  showHeader?: boolean;
};

export function LibraryExplorer({ showHeader = true }: LibraryExplorerProps) {
  const router = useRouter();
  const [blocks, setBlocks] = useState<ManageBlock[]>([]);
  const [activeBlockId, setActiveBlockId] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<ManageBlockWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  // Block editing
  const [editingBlockId, setEditingBlockId] = useState<number | null>(null);
  const [editingBlockName, setEditingBlockName] = useState("");
  const [newBlockName, setNewBlockName] = useState("");
  const [showNewBlock, setShowNewBlock] = useState(false);
  const [blockBusy, setBlockBusy] = useState(false);
  const newBlockInputRef = useRef<HTMLInputElement>(null);
  const editBlockInputRef = useRef<HTMLInputElement>(null);

  // Subject adding (new)
  const [showNewSubject, setShowNewSubject] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState("");
  const [addingBlockToSubject, setAddingBlockToSubject] = useState<string | null>(null);
  const newSubjectInputRef = useRef<HTMLInputElement>(null);

  // Lecture
  const [lectureTitle, setLectureTitle] = useState("");
  const [lectureProfessor, setLectureProfessor] = useState("");
  const [lectureBusy, setLectureBusy] = useState(false);
  const [deletingLectureId, setDeletingLectureId] = useState<number | null>(null);

  // Lecture inline editing
  const [editingLectureId, setEditingLectureId] = useState<number | null>(null);
  const [editingLectureTitle, setEditingLectureTitle] = useState("");
  const [editingLectureProfessor, setEditingLectureProfessor] = useState("");
  const editLectureTitleRef = useRef<HTMLInputElement>(null);

  const refreshBlocks = () => {
    getBlocks().then((data) => {
      setBlocks(data);
      // If active block was deleted, select first
      if (activeBlockId && !data.find(b => b.id === activeBlockId)) {
        setActiveBlockId(data[0]?.id ?? null);
      }
    }).catch(() => { });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBlocks()
      .then((data) => {
        if (cancelled) return;
        setBlocks(data);
        setActiveBlockId((prev) => prev ?? data[0]?.id ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unable to load blocks.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeBlockId) {
      setWorkspace(null);
      return;
    }
    let cancelled = false;
    setWorkspaceLoading(true);
    setError(null);
    getBlockWorkspace(activeBlockId)
      .then((data) => {
        if (!cancelled) setWorkspace(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setWorkspace(null);
          setError(err instanceof Error ? err.message : "Unable to load workspace.");
        }
      })
      .finally(() => {
        if (!cancelled) setWorkspaceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeBlockId, refreshTick]);

  useEffect(() => {
    if (showNewBlock && newBlockInputRef.current) {
      newBlockInputRef.current.focus();
    }
  }, [showNewBlock]);

  useEffect(() => {
    if (editingBlockId && editBlockInputRef.current) {
      editBlockInputRef.current.focus();
    }
  }, [editingBlockId]);

  useEffect(() => {
    if (showNewSubject && newSubjectInputRef.current) {
      newSubjectInputRef.current.focus();
    }
  }, [showNewSubject]);

  useEffect(() => {
    if (addingBlockToSubject && newBlockInputRef.current) {
      newBlockInputRef.current.focus();
    }
  }, [addingBlockToSubject]);

  const activeBlock = useMemo(
    () => blocks.find((block) => block.id === activeBlockId) ?? null,
    [blocks, activeBlockId]
  );

  const blocksBySubject = useMemo(() => {
    const groups = new Map<string, ManageBlock[]>();
    blocks.forEach((block) => {
      const subject = block.subject ?? "Unassigned";
      const list = groups.get(subject) ?? [];
      list.push(block);
      groups.set(subject, list);
    });
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [blocks]);

  const lectures = workspace?.lectures ?? [];

  const nextOrder = useMemo(() => {
    if (!lectures.length) return 1;
    return (
      lectures.reduce((max: number, lecture: ManageLecture) => Math.max(max, lecture.order ?? 0), 0) + 1
    );
  }, [lectures]);

  const refreshWorkspace = () => setRefreshTick((tick) => tick + 1);

  // Subject handlers
  const handleAddSubject = async () => {
    if (!newSubjectName.trim()) return;
    setBlockBusy(true);
    setError(null);
    try {
      // Create a block with the subject name as both name and subject
      const created = await createBlock({
        name: newSubjectName.trim(),
        subject: newSubjectName.trim()
      });
      setNewSubjectName("");
      setShowNewSubject(false);
      refreshBlocks();
      setActiveBlockId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "과목을 생성할 수 없습니다.");
    } finally {
      setBlockBusy(false);
    }
  };

  const handleAddBlockToSubject = async (subject: string) => {
    if (!newBlockName.trim()) return;
    setBlockBusy(true);
    setError(null);
    try {
      const created = await createBlock({
        name: newBlockName.trim(),
        subject: subject
      });
      setNewBlockName("");
      setAddingBlockToSubject(null);
      refreshBlocks();
      setActiveBlockId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "블록을 생성할 수 없습니다.");
    } finally {
      setBlockBusy(false);
    }
  };

  // Block handlers
  const handleAddBlock = async () => {
    if (!newBlockName.trim()) return;
    setBlockBusy(true);
    setError(null);
    try {
      const created = await createBlock({ name: newBlockName.trim() });
      setNewBlockName("");
      setShowNewBlock(false);
      refreshBlocks();
      setActiveBlockId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create block.");
    } finally {
      setBlockBusy(false);
    }
  };

  const handleDeleteBlock = async (blockId: number) => {
    const block = blocks.find(b => b.id === blockId);
    const confirmed = window.confirm(`Delete "${block?.name}"? All lectures in it will also be deleted.`);
    if (!confirmed) return;
    setBlockBusy(true);
    setError(null);
    try {
      await deleteBlock(blockId);
      refreshBlocks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete block.");
    } finally {
      setBlockBusy(false);
    }
  };

  const handleStartEditBlock = (block: ManageBlock) => {
    setEditingBlockId(block.id);
    setEditingBlockName(block.name);
  };

  const handleSaveEditBlock = async () => {
    if (!editingBlockId || !editingBlockName.trim()) return;
    setBlockBusy(true);
    setError(null);
    try {
      await updateBlock(editingBlockId, { name: editingBlockName.trim() });
      setEditingBlockId(null);
      setEditingBlockName("");
      refreshBlocks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to rename block.");
    } finally {
      setBlockBusy(false);
    }
  };

  const handleCancelEditBlock = () => {
    setEditingBlockId(null);
    setEditingBlockName("");
  };

  // Lecture inline edit handlers
  const handleStartEditLecture = (lecture: ManageLecture) => {
    setEditingLectureId(lecture.id);
    setEditingLectureTitle(lecture.title);
    setEditingLectureProfessor(lecture.professor ?? "");
    setTimeout(() => editLectureTitleRef.current?.focus(), 0);
  };

  const handleSaveEditLecture = async () => {
    if (!editingLectureId || !editingLectureTitle.trim()) return;
    setLectureBusy(true);
    setError(null);
    try {
      await updateLecture(editingLectureId, {
        title: editingLectureTitle.trim(),
        professor: editingLectureProfessor.trim() || null,
      });
      setEditingLectureId(null);
      setEditingLectureTitle("");
      setEditingLectureProfessor("");
      refreshWorkspace();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update lecture.");
    } finally {
      setLectureBusy(false);
    }
  };

  const handleCancelEditLecture = () => {
    setEditingLectureId(null);
    setEditingLectureTitle("");
    setEditingLectureProfessor("");
  };

  // Lecture handlers
  const handleLectureCreate = async () => {
    if (!activeBlockId || !lectureTitle.trim()) return;
    setLectureBusy(true);
    setError(null);
    try {
      await createLecture(activeBlockId, {
        title: lectureTitle.trim(),
        professor: lectureProfessor.trim() || null,
        order: nextOrder,
      });
      setLectureTitle("");
      setLectureProfessor("");
      refreshWorkspace();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create lecture.");
    } finally {
      setLectureBusy(false);
    }
  };

  const handleDeleteLecture = async (lectureId: number) => {
    const confirmed = window.confirm("Delete this lecture? This cannot be undone.");
    if (!confirmed) return;
    setDeletingLectureId(lectureId);
    setError(null);
    try {
      await deleteLecture(lectureId);
      refreshWorkspace();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete lecture.");
    } finally {
      setDeletingLectureId(null);
    }
  };

  const handleLectureClick = (lectureId: number) => {
    router.push(`/manage/lectures/${lectureId}`);
  };

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground">Loading library...</div>;
  }

  return (
    <div className="space-y-6">
      {showHeader && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Library
          </p>
          <h2 className="text-2xl font-semibold text-foreground">
            {activeBlock?.name ?? "Workspace"}
          </h2>
        </div>
      )}

      {error && (
        <Card className="border border-danger/30 bg-danger/10">
          <CardContent className="space-y-2 p-4 text-sm text-danger">{error}</CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Left Panel: Block Tree */}
        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                과목 / 블록
              </span>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={refreshBlocks}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              {/* Subject Section Header */}
              <div className="flex items-center justify-between pt-2">
                <p className="text-sm font-medium text-muted-foreground px-1">과목</p>
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

              {/* New Subject Card - appears at top when + button is clicked */}
              {showNewSubject && (
                <div className="animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="rounded-lg border-2 border-dashed border-border bg-muted/50 p-3">
                    <div className="mb-2 text-xs font-semibold text-muted-foreground">
                      새 과목 추가
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        ref={newSubjectInputRef}
                        value={newSubjectName}
                        onChange={(e) => setNewSubjectName(e.target.value)}
                        placeholder="과목 이름 입력"
                        className="h-9 text-sm"
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && newSubjectName.trim()) handleAddSubject();
                          if (e.key === "Escape") {
                            setShowNewSubject(false);
                            setNewSubjectName("");
                          }
                        }}
                      />
                      <Button
                        size="sm"
                        variant="default"
                        className="h-9 px-3 shrink-0"
                        onClick={handleAddSubject}
                        disabled={blockBusy || !newSubjectName.trim()}
                      >
                        과목 추가
                        {/* <Check className="h-4 w-4" /> */}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {blocksBySubject.map(([subject, subjectBlocks]) => {
                const isAddingBlockToSubject = addingBlockToSubject === subject;

                return (
                  <div key={subject} className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
                    {/* Subject Header */}
                    <div className="flex items-center justify-between px-3 py-2 bg-muted/30">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        {subject}
                      </p>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 px-2 text-[10px] opacity-70 hover:opacity-100"
                        onClick={() => {
                          setAddingBlockToSubject(subject);
                          setNewBlockName("");
                        }}
                        disabled={isAddingBlockToSubject}
                      >
                        <Plus className="mr-1 h-3 w-3" />
                        블록
                      </Button>
                    </div>

                    {/* Blocks in this subject */}
                    <div className="divide-y divide-border/30">
                      {subjectBlocks.map((block) => {
                        const isActive = block.id === activeBlockId;
                        const isEditing = editingBlockId === block.id;

                        if (isEditing) {
                          return (
                            <div key={block.id} className="flex items-center gap-1 bg-muted/50 px-3 py-2">
                              <Input
                                ref={editBlockInputRef}
                                value={editingBlockName}
                                onChange={(e) => setEditingBlockName(e.target.value)}
                                className="h-7 text-sm"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleSaveEditBlock();
                                  if (e.key === "Escape") handleCancelEditBlock();
                                }}
                              />
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0"
                                onClick={handleSaveEditBlock}
                                disabled={blockBusy || !editingBlockName.trim()}
                              >
                                <Check className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0"
                                onClick={handleCancelEditBlock}
                              >
                                <X className="h-3 w-3" />
                              </Button>
                            </div>
                          );
                        }

                        return (
                          <div
                            key={block.id}
                            className={`group flex items-center gap-2 px-3 py-2 transition-colors ${isActive
                              ? "bg-primary/10 text-primary font-medium"
                              : "text-foreground hover:bg-muted/30"
                              }`}
                          >
                            <button
                              onClick={() => setActiveBlockId(block.id)}
                              className="flex flex-1 items-center gap-2 text-left"
                            >
                              {isActive ? (
                                <FolderOpen className="h-4 w-4 shrink-0" />
                              ) : (
                                <Folder className="h-4 w-4 shrink-0" />
                              )}
                              <span className="truncate text-sm">{block.name}</span>
                            </button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStartEditBlock(block);
                              }}
                            >
                              <Pencil className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 text-danger hover:text-danger"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteBlock(block.id);
                              }}
                              disabled={blockBusy}
                            >
                              <Minus className="h-3 w-3" />
                            </Button>
                            <Badge variant="neutral" className="text-[10px]">
                              {block.lectureCount ?? 0}
                            </Badge>
                          </div>
                        );
                      })}

                      {/* Add Block Inline Form - expands at bottom of subject card */}
                      {isAddingBlockToSubject && (
                        <div className="animate-in slide-in-from-top-1 fade-in duration-150 border-t border-dashed border-border/50 bg-muted/20 px-3 py-2">
                          <div className="flex items-center gap-2">
                            <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
                            <Input
                              ref={newBlockInputRef}
                              value={newBlockName}
                              onChange={(e) => setNewBlockName(e.target.value)}
                              placeholder="새 블록 이름"
                              className="h-7 flex-1 text-sm"
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && newBlockName.trim()) handleAddBlockToSubject(subject);
                                if (e.key === "Escape") {
                                  setAddingBlockToSubject(null);
                                  setNewBlockName("");
                                }
                              }}
                            />
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0"
                              onClick={() => handleAddBlockToSubject(subject)}
                              disabled={blockBusy || !newBlockName.trim()}
                            >
                              <Check className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0"
                              onClick={() => {
                                setAddingBlockToSubject(null);
                                setNewBlockName("");
                              }}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}



              {blocks.length === 0 && !showNewSubject && (
                <div className="py-6 text-center">
                  <div className="text-sm text-muted-foreground mb-2">아직 과목이 없습니다</div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowNewSubject(true);
                      setNewSubjectName("");
                    }}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    첫 과목 추가하기
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Right Panel: Lectures */}
        <Card className="border border-border/70 bg-card/85 shadow-soft">
          <CardContent className="space-y-4 p-5">
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-foreground">All lectures</h3>
                <Badge variant="neutral">{lectures.length} items</Badge>
              </div>
              <Button variant="outline" size="sm" onClick={refreshWorkspace}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>

            {/* Lecture List */}
            <div className="space-y-1">
              {!activeBlockId ? (
                <div className="py-8 text-center text-muted-foreground">
                  Select a block to view lectures
                </div>
              ) : workspaceLoading ? (
                <div className="py-8 text-center text-muted-foreground">Loading lectures...</div>
              ) : lectures.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  No lectures in this block.
                </div>
              ) : (
                lectures.map((lecture: ManageLecture) => {
                  const isEditing = editingLectureId === lecture.id;

                  if (isEditing) {
                    return (
                      <div
                        key={lecture.id}
                        className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2"
                      >
                        <div className="flex-1 space-y-1">
                          <Input
                            ref={editLectureTitleRef}
                            value={editingLectureTitle}
                            onChange={(e) => setEditingLectureTitle(e.target.value)}
                            placeholder="Lecture title"
                            className="h-8 text-sm"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveEditLecture();
                              if (e.key === "Escape") handleCancelEditLecture();
                            }}
                          />
                          <Input
                            value={editingLectureProfessor}
                            onChange={(e) => setEditingLectureProfessor(e.target.value)}
                            placeholder="Professor"
                            className="h-7 text-xs"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveEditLecture();
                              if (e.key === "Escape") handleCancelEditLecture();
                            }}
                          />
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={handleSaveEditLecture}
                          disabled={lectureBusy || !editingLectureTitle.trim()}
                        >
                          <Check className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={handleCancelEditLecture}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={lecture.id}
                      onClick={() => handleLectureClick(lecture.id)}
                      className="group flex cursor-pointer items-center justify-between rounded-md border border-transparent px-3 py-2 hover:border-border/50 hover:bg-muted/30"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-foreground truncate">
                          {lecture.title}
                        </div>
                        {lecture.professor && (
                          <div className="text-xs text-muted-foreground">{lecture.professor}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="neutral">{lecture.questionCount ?? 0} Q</Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartEditLecture(lecture);
                          }}
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 text-danger hover:text-danger"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteLecture(lecture.id);
                          }}
                          disabled={deletingLectureId === lecture.id}
                        >
                          <Minus className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Quick Add Lecture */}
            {activeBlockId && (
              <div className="space-y-3 rounded-lg border border-dashed border-border/70 bg-muted/30 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Add new lecture
                </div>
                <div className="grid gap-2 md:grid-cols-[2fr_1fr_auto]">
                  <Input
                    value={lectureTitle}
                    onChange={(event) => setLectureTitle(event.target.value)}
                    placeholder="Lecture title"
                  />
                  <Input
                    value={lectureProfessor}
                    onChange={(event) => setLectureProfessor(event.target.value)}
                    placeholder="Professor"
                  />
                  <Button onClick={handleLectureCreate} disabled={lectureBusy || !lectureTitle.trim()}>
                    {lectureBusy ? "Adding..." : "Add"}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
