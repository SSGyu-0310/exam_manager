"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckSquare,
  ChevronDown,
  ChevronRight,
  ChevronsDown,
  ChevronsUp,
  FileText,
  ListChecks,
  Square,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getExams, type ManageExam } from "@/lib/api/manage";
import { composeExamTitle } from "@/lib/examTitle";
import { useLanguage } from "@/context/LanguageContext";
import { apiFetch } from "@/lib/http";
import { cn } from "@/lib/utils";

type BlockGroup = {
  blockKey: string;
  blockName: string;
  blockId?: number;
  examCount: number;
  questionCount: number;
  exams: ManageExam[];
};

type SubjectGroup = {
  subjectKey: string;
  subjectName: string;
  examCount: number;
  questionCount: number;
  blocks: BlockGroup[];
};

const UNCATEGORIZED_SUBJECT = "미분류 과목";
const UNASSIGNED_BLOCK = "미지정 블록";

export default function ExamsPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [exams, setExams] = useState<ManageExam[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExamIds, setSelectedExamIds] = useState<number[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openSubjects, setOpenSubjects] = useState<Record<string, boolean>>({});
  const [openBlocks, setOpenBlocks] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const fetchExams = async () => {
      try {
        const data = await getExams();
        setExams(data);
      } catch (requestError) {
        console.error("Failed to fetch exams", requestError);
        setError("시험지 목록을 불러오지 못했습니다.");
      } finally {
        setLoading(false);
      }
    };
    void fetchExams();
  }, []);

  const groupedSubjects = useMemo<SubjectGroup[]>(() => {
    const subjectMap = new Map<
      string,
      {
        subjectName: string;
        blocks: Map<
          string,
          {
            blockName: string;
            blockId?: number;
            exams: ManageExam[];
            questionCount: number;
          }
        >;
      }
    >();

    for (const exam of exams) {
      const subjectName =
        exam.subject?.trim() || exam.primaryBlockSubject?.trim() || UNCATEGORIZED_SUBJECT;
      const subjectKey = subjectName.toLowerCase();

      const fallbackBlock = exam.blocks?.[0];
      const blockId = exam.primaryBlockId ?? fallbackBlock?.blockId;
      const blockName =
        exam.primaryBlockName?.trim() || fallbackBlock?.blockName || UNASSIGNED_BLOCK;
      const blockKey =
        blockId !== null && blockId !== undefined
          ? `block-${blockId}`
          : `subject-${subjectKey}-unassigned`;

      if (!subjectMap.has(subjectKey)) {
        subjectMap.set(subjectKey, {
          subjectName,
          blocks: new Map(),
        });
      }

      const subjectEntry = subjectMap.get(subjectKey)!;
      if (!subjectEntry.blocks.has(blockKey)) {
        subjectEntry.blocks.set(blockKey, {
          blockName,
          blockId: blockId ?? undefined,
          exams: [],
          questionCount: 0,
        });
      }

      const blockEntry = subjectEntry.blocks.get(blockKey)!;
      blockEntry.exams.push(exam);
      blockEntry.questionCount += exam.questionCount ?? 0;
    }

    const subjects = Array.from(subjectMap.entries()).map(([subjectKey, subjectEntry]) => {
      const blocks = Array.from(subjectEntry.blocks.entries())
        .map(([blockKey, blockEntry]) => ({
          blockKey,
          blockName: blockEntry.blockName,
          blockId: blockEntry.blockId,
          examCount: blockEntry.exams.length,
          questionCount: blockEntry.questionCount,
          exams: [...blockEntry.exams],
        }))
        .sort((a, b) => {
          if (a.blockName === UNASSIGNED_BLOCK && b.blockName !== UNASSIGNED_BLOCK) {
            return 1;
          }
          if (b.blockName === UNASSIGNED_BLOCK && a.blockName !== UNASSIGNED_BLOCK) {
            return -1;
          }
          return a.blockName.localeCompare(b.blockName, "ko");
        });

      const examCount = blocks.reduce((sum, block) => sum + block.examCount, 0);
      const questionCount = blocks.reduce((sum, block) => sum + block.questionCount, 0);

      return {
        subjectKey,
        subjectName: subjectEntry.subjectName,
        examCount,
        questionCount,
        blocks,
      };
    });

    subjects.sort((a, b) => {
      if (a.subjectName === UNCATEGORIZED_SUBJECT && b.subjectName !== UNCATEGORIZED_SUBJECT) {
        return 1;
      }
      if (b.subjectName === UNCATEGORIZED_SUBJECT && a.subjectName !== UNCATEGORIZED_SUBJECT) {
        return -1;
      }
      return a.subjectName.localeCompare(b.subjectName, "ko");
    });

    return subjects;
  }, [exams]);

  useEffect(() => {
    if (!groupedSubjects.length) {
      setOpenSubjects({});
      setOpenBlocks({});
      return;
    }

    setOpenSubjects((prev) => {
      const next: Record<string, boolean> = {};
      groupedSubjects.forEach((subject, index) => {
        next[subject.subjectKey] = prev[subject.subjectKey] ?? index === 0;
      });
      return next;
    });

    setOpenBlocks((prev) => {
      const next: Record<string, boolean> = {};
      groupedSubjects.forEach((subject, subjectIndex) => {
        subject.blocks.forEach((block, blockIndex) => {
          next[block.blockKey] = prev[block.blockKey] ?? (subjectIndex === 0 && blockIndex === 0);
        });
      });
      return next;
    });
  }, [groupedSubjects]);

  const selectedExams = exams.filter((exam) => selectedExamIds.includes(exam.id));
  const selectedQuestionCount = selectedExams.reduce(
    (sum, exam) => sum + (exam.questionCount ?? 0),
    0
  );

  const setExamSelection = (ids: number[], shouldSelect: boolean) => {
    setSelectedExamIds((prev) => {
      const base = new Set(prev);
      ids.forEach((id) => {
        if (shouldSelect) {
          base.add(id);
        } else {
          base.delete(id);
        }
      });
      return Array.from(base);
    });
  };

  const toggleExamSelection = (examId: number) => {
    setExamSelection([examId], !selectedExamIds.includes(examId));
  };

  const toggleSubject = (subjectKey: string) => {
    setOpenSubjects((prev) => ({ ...prev, [subjectKey]: !prev[subjectKey] }));
  };

  const toggleBlock = (blockKey: string) => {
    setOpenBlocks((prev) => ({ ...prev, [blockKey]: !prev[blockKey] }));
  };

  const expandAll = () => {
    const nextSubjects: Record<string, boolean> = {};
    const nextBlocks: Record<string, boolean> = {};
    groupedSubjects.forEach((subject) => {
      nextSubjects[subject.subjectKey] = true;
      subject.blocks.forEach((block) => {
        nextBlocks[block.blockKey] = true;
      });
    });
    setOpenSubjects(nextSubjects);
    setOpenBlocks(nextBlocks);
  };

  const collapseAll = () => {
    const nextSubjects: Record<string, boolean> = {};
    const nextBlocks: Record<string, boolean> = {};
    groupedSubjects.forEach((subject) => {
      nextSubjects[subject.subjectKey] = false;
      subject.blocks.forEach((block) => {
        nextBlocks[block.blockKey] = false;
      });
    });
    setOpenSubjects(nextSubjects);
    setOpenBlocks(nextBlocks);
  };

  const nonEmptyExamIds = useMemo(
    () => exams.filter((exam) => (exam.questionCount ?? 0) > 0).map((exam) => exam.id),
    [exams]
  );

  const selectAll = () => {
    setSelectedExamIds(nonEmptyExamIds);
  };

  const clearSelection = () => {
    setSelectedExamIds([]);
  };

  const handleStart = async () => {
    if (selectedExamIds.length === 0) {
      setError("최소 한 개의 시험지를 선택해야 합니다.");
      return;
    }

    setStarting(true);
    setError(null);

    try {
      let resolvedSessionId: string | number | null = null;
      const firstExam = selectedExams[0] ?? exams[0];
      let resolvedTitle =
        selectedExams.length === 1 && selectedExams[0]
          ? composeExamTitle(selectedExams[0]) || selectedExams[0].title
          : `${(firstExam ? composeExamTitle(firstExam) || firstExam.title : "Selected exams")} +${Math.max(selectedExams.length - 1, 0)}`;

      try {
        const result = await apiFetch<unknown>("/api/practice/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ examIds: selectedExamIds, mode: "exam_practice" }),
        });
        if (result && typeof result === "object") {
          const record = result as Record<string, unknown>;
          const sessionId = record.sessionId;
          if (typeof sessionId === "string" || typeof sessionId === "number") {
            resolvedSessionId = sessionId;
          }
          const examTitle = record.examTitle;
          if (typeof examTitle === "string" && examTitle.trim()) {
            resolvedTitle = examTitle;
          }
        }
      } catch (requestError) {
        console.error("Failed to create exam session", requestError);
      }

      const sessionId =
        resolvedSessionId ?? `examset-${encodeURIComponent(selectedExamIds.join(","))}`;

      const sessionPayload = {
        examIds: selectedExamIds,
        examTitle: resolvedTitle,
        mode: "exam_practice",
        fallback: resolvedSessionId === null,
        createdAt: Date.now(),
        source: resolvedSessionId === null ? "examset-fallback" : "/api/practice/sessions",
      };
      if (typeof window !== "undefined") {
        sessionStorage.setItem(
          `practice:session:${sessionId}`,
          JSON.stringify(sessionPayload)
        );
      }
      router.push(`/practice/session/${sessionId}`);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {t("learn.mockExams")}
        </h1>
        <p className="text-muted-foreground">{t("learn.mockExamsDesc")}</p>
      </div>

      <Card className="border-border bg-card/60">
        <CardContent className="flex items-center justify-between gap-3 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-primary/10 p-2 text-primary">
              <ListChecks className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                과목/블록을 접어서 원하는 시험지만 선택하세요
              </p>
              <p className="text-xs text-muted-foreground">
                선택한 시험지 전체를 하나의 통합 세션으로 풀 수 있습니다.
              </p>
            </div>
          </div>
          <Badge variant="neutral">{selectedExamIds.length} selected</Badge>
        </CardContent>
      </Card>

      <Card className="border-border bg-card/70">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="text-sm text-muted-foreground">
            선택 시험지 <span className="font-semibold text-foreground">{selectedExamIds.length}</span>개,
            예상 문항 <span className="font-semibold text-foreground">{selectedQuestionCount}</span>개
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={selectAll}>
              전체 선택
            </Button>
            <Button variant="outline" size="sm" onClick={clearSelection}>
              선택 해제
            </Button>
            <Button
              onClick={() => void handleStart()}
              disabled={starting || selectedExamIds.length === 0}
            >
              {starting ? "세션 생성 중..." : t("learn.examBasedStart")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card/70">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm text-muted-foreground">
          <span>
            과목 {groupedSubjects.length}개 / 블록 {groupedSubjects.reduce((sum, subject) => sum + subject.blocks.length, 0)}개
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={expandAll}>
              <ChevronsDown className="h-4 w-4" />
              모두 펼치기
            </Button>
            <Button variant="ghost" size="sm" onClick={collapseAll}>
              <ChevronsUp className="h-4 w-4" />
              모두 접기
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-danger/40 bg-danger/10">
          <CardContent className="py-3 text-sm text-danger">{error}</CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <Card key={item} className="h-32 animate-pulse border-border bg-muted" />
          ))}
        </div>
      ) : exams.length === 0 ? (
        <Card className="border-border bg-card/70">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <div className="space-y-1">
              <p className="text-base font-semibold text-foreground">
                {t("learn.examBasedEmpty")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("learn.examBasedEmptyDesc")}
              </p>
            </div>
            <Link href="/manage/exams">
              <Button variant="outline">{t("learn.examBasedManage")}</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {groupedSubjects.map((subject) => {
            const subjectExamIds = subject.blocks.flatMap((block) =>
              block.exams.map((exam) => exam.id)
            );
            const subjectSelectedCount = subjectExamIds.filter((id) =>
              selectedExamIds.includes(id)
            ).length;
            const isSubjectOpen = openSubjects[subject.subjectKey] ?? false;

            return (
              <Collapsible
                key={subject.subjectKey}
                open={isSubjectOpen}
                onOpenChange={() => toggleSubject(subject.subjectKey)}
              >
                <CollapsibleTrigger asChild>
                  <button className="flex w-full items-center justify-between rounded-xl border border-border bg-card/80 px-4 py-3 text-left shadow-soft">
                    <div className="flex items-center gap-3">
                      {isSubjectOpen ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                      <div>
                        <p className="text-base font-semibold text-foreground">
                          {subject.subjectName}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {subject.blocks.length} blocks · {subject.examCount} exams · {subject.questionCount} questions
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="neutral">
                        {subjectSelectedCount}/{subject.examCount} selected
                      </Badge>
                      <span
                        role="button"
                        tabIndex={0}
                        className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground cursor-pointer"
                        onClick={(event) => {
                          event.stopPropagation();
                          event.preventDefault();
                          const shouldSelect = subjectSelectedCount !== subjectExamIds.length;
                          setExamSelection(subjectExamIds, shouldSelect);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.stopPropagation();
                            event.preventDefault();
                            const shouldSelect = subjectSelectedCount !== subjectExamIds.length;
                            setExamSelection(subjectExamIds, shouldSelect);
                          }
                        }}
                      >
                        {subjectSelectedCount === subjectExamIds.length
                          ? "과목 선택 해제"
                          : "과목 전체 선택"}
                      </span>
                    </div>
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-3 rounded-b-xl border border-t-0 border-border bg-muted/20 p-3">
                  {subject.blocks.map((block) => {
                    const blockExamIds = block.exams.map((exam) => exam.id);
                    const blockSelectedCount = blockExamIds.filter((id) =>
                      selectedExamIds.includes(id)
                    ).length;
                    const isBlockOpen = openBlocks[block.blockKey] ?? false;

                    return (
                      <Collapsible
                        key={block.blockKey}
                        open={isBlockOpen}
                        onOpenChange={() => toggleBlock(block.blockKey)}
                      >
                        <CollapsibleTrigger asChild>
                          <button className="flex w-full items-center justify-between rounded-lg border border-border/70 bg-card px-3 py-2 text-left">
                            <div className="flex items-center gap-2">
                              {isBlockOpen ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )}
                              <div>
                                <p className="text-sm font-semibold text-foreground">
                                  {block.blockName}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {block.examCount} exams · {block.questionCount} questions
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant="neutral">
                                {blockSelectedCount}/{block.examCount} selected
                              </Badge>
                              <span
                                role="button"
                                tabIndex={0}
                                className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground cursor-pointer"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  event.preventDefault();
                                  const shouldSelect = blockSelectedCount !== blockExamIds.length;
                                  setExamSelection(blockExamIds, shouldSelect);
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === 'Enter' || event.key === ' ') {
                                    event.stopPropagation();
                                    event.preventDefault();
                                    const shouldSelect = blockSelectedCount !== blockExamIds.length;
                                    setExamSelection(blockExamIds, shouldSelect);
                                  }
                                }}
                              >
                                {blockSelectedCount === blockExamIds.length ? "해제" : "전체"}
                              </span>
                            </div>
                          </button>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 rounded-lg border border-border/60 bg-card/80 p-3">
                          {block.exams.map((exam) => {
                            const questionCount = exam.questionCount ?? 0;
                            const isSelected = selectedExamIds.includes(exam.id);

                            return (
                              <button
                                key={exam.id}
                                type="button"
                                onClick={() => toggleExamSelection(exam.id)}
                                disabled={questionCount === 0}
                                className={cn(
                                  "group flex flex-col text-left gap-3 rounded-xl border p-4 shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                                  questionCount === 0
                                    ? "opacity-60 cursor-not-allowed border-border/50 bg-muted/30"
                                    : "hover:shadow-md",
                                  isSelected && questionCount > 0
                                    ? "border-primary bg-primary/5 shadow-primary/10"
                                    : !isSelected && questionCount > 0
                                      ? "border-border/60 bg-card hover:border-primary/40"
                                      : ""
                                )}
                                aria-label={`Toggle exam ${exam.title}`}
                              >
                                <div className="flex w-full items-start justify-between gap-3">
                                  <div className="flex-1 min-w-0">
                                    <p className="line-clamp-2 text-sm font-semibold text-foreground leading-snug">
                                      {composeExamTitle(exam) || exam.title}
                                    </p>
                                  </div>
                                  <div className="shrink-0 pt-0.5">
                                    {isSelected ? (
                                      <CheckSquare className="h-5 w-5 text-primary" />
                                    ) : (
                                      <Square className="h-5 w-5 text-muted-foreground/30 transition-colors group-hover:text-primary/50" />
                                    )}
                                  </div>
                                </div>
                                <div className="mt-auto w-full pt-3 flex items-center justify-between border-t border-border/40 text-xs text-muted-foreground">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span>{exam.examDate ?? "날짜 미지정"}</span>
                                    {exam.blocks && exam.blocks.length > 1 && (
                                      <>
                                        <span>·</span>
                                        <span>{exam.blocks.length} blocks mix</span>
                                      </>
                                    )}
                                  </div>
                                  <Badge
                                    variant={isSelected ? "ai" : "neutral"}
                                    className="px-1.5 py-0 rounded-md text-[10px]"
                                  >
                                    {questionCount} {t("learn.questions")}
                                  </Badge>
                                </div>
                              </button>
                            );
                          })}
                        </CollapsibleContent>
                      </Collapsible>
                    );
                  })}
                </CollapsibleContent>
              </Collapsible>
            );
          })}
        </div>
      )}
    </div>
  );
}
