import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import type {
  Block,
  LectureSort,
  LectureStudyMeta,
  NormalizedLecture,
} from "@/components/lectures/types";
import { normalizeLecture } from "@/components/lectures/types";
import { LectureCard } from "@/components/lectures/LectureCard";
import { LectureEmptyState } from "@/components/lectures/LectureEmptyState";
import { LectureHeader } from "@/components/lectures/LectureHeader";
import { useLectureQuestionCounts } from "@/components/lectures/useLectureQuestionCounts";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

type LectureGridProps = {
  blocks: Block[];
  studyMetaByLecture: Record<string, LectureStudyMeta>;
  query: string;
  onQueryChange: (value: string) => void;
  sort: LectureSort;
  onSortChange: (value: LectureSort) => void;
};

type NormalizedBlock = {
  blockId?: number | string;
  title?: string;
  lectures: NormalizedLecture[];
};

export function LectureGrid({
  blocks,
  studyMetaByLecture,
  query,
  onQueryChange,
  sort,
  onSortChange,
}: LectureGridProps) {
  const { t } = useLanguage();
  const [openBlocks, setOpenBlocks] = useState<Record<string, boolean>>({});
  const normalizedBlocks = useMemo<NormalizedBlock[]>(
    () =>
      (blocks ?? []).map((block) => ({
        blockId: block.blockId as number | string | undefined,
        title:
          typeof block.title === "string"
            ? block.title
            : typeof block.title === "number"
              ? String(block.title)
              : undefined,
        lectures: (block.lectures ?? []).map((lecture) => normalizeLecture(lecture)),
      })),
    [blocks]
  );

  const allLectures = useMemo(
    () => normalizedBlocks.flatMap((block) => block.lectures),
    [normalizedBlocks]
  );

  const counts = useLectureQuestionCounts(allLectures);

  const filteredBlocks = useMemo<NormalizedBlock[]>(() => {
    const term = query.trim().toLowerCase();
    if (!term) return normalizedBlocks;

    return normalizedBlocks
      .map((block) => {
        const blockTitle = block.title ?? "";
        const blockMatch = blockTitle.toLowerCase().includes(term);
        const lectures = block.lectures.filter((lecture) =>
          (lecture.title ?? "").toLowerCase().includes(term)
        );

        if (blockMatch) {
          return { ...block, lectures: block.lectures };
        }

        if (lectures.length > 0) {
          return { ...block, lectures };
        }

        return null;
      })
      .filter((block): block is NormalizedBlock => Boolean(block));
  }, [normalizedBlocks, query]);

  const getLectureCount = useCallback(
    (lecture: NormalizedLecture) => {
      if (lecture.id === null || lecture.id === undefined) {
        return typeof lecture.questionCount === "number" ? lecture.questionCount : null;
      }
      const cached = counts[String(lecture.id)];
      if (typeof cached === "number") return cached;
      return typeof lecture.questionCount === "number" ? lecture.questionCount : null;
    },
    [counts]
  );

  const getLectureStudyMeta = useCallback(
    (lecture: NormalizedLecture): LectureStudyMeta | null => {
      if (lecture.id === null || lecture.id === undefined) return null;
      return studyMetaByLecture[String(lecture.id)] ?? null;
    },
    [studyMetaByLecture]
  );

  const sortedBlocks = useMemo<NormalizedBlock[]>(() => {
    return filteredBlocks.map((block) => {
      const lectures = [...block.lectures];
      const originalOrder = new Map(
        lectures.map((lecture, index) => [lecture, index] as const)
      );
      if (sort === "questions") {
        lectures.sort((a, b) => {
          const countA = getLectureCount(a);
          const countB = getLectureCount(b);
          const valueA = typeof countA === "number" ? countA : -1;
          const valueB = typeof countB === "number" ? countB : -1;
          if (valueA !== valueB) return valueB - valueA;
          return (a.title ?? "").localeCompare(b.title ?? "", undefined, {
            sensitivity: "base",
          });
        });
      } else if (sort === "recent") {
        lectures.sort((a, b) => {
          const recentA = getLectureStudyMeta(a)?.lastStudiedAt;
          const recentB = getLectureStudyMeta(b)?.lastStudiedAt;
          const parsedA = recentA ? Date.parse(recentA) : 0;
          const parsedB = recentB ? Date.parse(recentB) : 0;
          const timeA = Number.isFinite(parsedA) ? parsedA : 0;
          const timeB = Number.isFinite(parsedB) ? parsedB : 0;
          if (timeA !== timeB) return timeB - timeA;
          return (a.title ?? "").localeCompare(b.title ?? "", undefined, {
            sensitivity: "base",
          });
        });
      } else if (sort === "manual") {
        lectures.sort((a, b) => {
          const orderA = typeof a.order === "number" ? a.order : Number.POSITIVE_INFINITY;
          const orderB = typeof b.order === "number" ? b.order : Number.POSITIVE_INFINITY;
          if (orderA !== orderB) return orderA - orderB;

          const indexA = originalOrder.get(a) ?? 0;
          const indexB = originalOrder.get(b) ?? 0;
          return indexA - indexB;
        });
      } else {
        lectures.sort((a, b) =>
          (a.title ?? "").localeCompare(b.title ?? "", undefined, { sensitivity: "base" })
        );
      }
      return { ...block, lectures };
    });
  }, [filteredBlocks, sort, getLectureCount, getLectureStudyMeta]);

  const visibleBlocks = useMemo(
    () => sortedBlocks.filter((block) => block.lectures.length > 0),
    [sortedBlocks]
  );

  useEffect(() => {
    if (!visibleBlocks.length) {
      setOpenBlocks({});
      return;
    }

    setOpenBlocks((prev) => {
      const next: Record<string, boolean> = {};
      visibleBlocks.forEach((block, blockIndex) => {
        const blockKey = String(block.blockId ?? block.title ?? `block-${blockIndex}`);
        next[blockKey] = prev[blockKey] ?? true;
      });
      return next;
    });
  }, [visibleBlocks]);

  const totalCount = useMemo(() => {
    return normalizedBlocks.reduce((sum, block) => sum + block.lectures.length, 0);
  }, [normalizedBlocks]);

  const filteredCount = useMemo(() => {
    return filteredBlocks.reduce((sum, block) => sum + block.lectures.length, 0);
  }, [filteredBlocks]);

  const hasLectures = visibleBlocks.length > 0;

  const toggleBlock = useCallback((blockKey: string) => {
    setOpenBlocks((prev) => ({ ...prev, [blockKey]: !prev[blockKey] }));
  }, []);

  const quickStartAction = (() => {
    let firstStartHref: string | null = null;
    for (const block of visibleBlocks) {
      for (const lecture of block.lectures) {
        if (lecture.id === null || lecture.id === undefined) continue;
        const lectureId = encodeURIComponent(String(lecture.id));
        const studyMeta = getLectureStudyMeta(lecture);
        if (studyMeta?.inProgressSessionId) {
          return {
            href: `/practice/session/${encodeURIComponent(studyMeta.inProgressSessionId)}`,
            label: t("learn.quickResumeFirst"),
          };
        }
        if (!firstStartHref) {
          firstStartHref = `/practice/start?lectureId=${lectureId}`;
        }
      }
    }
    if (!firstStartHref) return { href: null, label: null };
    return { href: firstStartHref, label: t("learn.quickStartFirst") };
  })();

  return (
    <div className="space-y-5">
      <LectureHeader
        query={query}
        onQueryChange={onQueryChange}
        sort={sort}
        onSortChange={onSortChange}
        totalCount={totalCount}
        filteredCount={filteredCount}
        quickStartHref={quickStartAction.href}
        quickStartLabel={quickStartAction.label}
      />

      {!hasLectures ? (
        <LectureEmptyState />
      ) : (
        <div className="space-y-4">
          {visibleBlocks.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {visibleBlocks.map((block, blockIndex) => {
                const blockTitle = block.title?.trim() ?? t("learn.untitledBlock");
                return (
                  <a
                    key={`chip-${block.blockId ?? blockTitle ?? blockIndex}`}
                    href={`#lecture-block-${blockIndex}`}
                    className="rounded-full border border-border/70 bg-card px-3 py-1 text-xs font-medium text-muted-foreground transition hover:border-primary/40 hover:text-foreground"
                  >
                    {blockTitle} · {block.lectures.length}
                  </a>
                );
              })}
            </div>
          )}
          {visibleBlocks.map((block, blockIndex) => {
            const blockKey = String(block.blockId ?? block.title ?? `block-${blockIndex}`);
            const blockTitle = block.title?.trim();
            const showHeader = Boolean(blockTitle) || visibleBlocks.length > 1;
            const isOpen = openBlocks[blockKey] ?? true;
            return (
              <Collapsible
                key={blockKey}
                open={isOpen}
                onOpenChange={() => toggleBlock(blockKey)}
              >
                <section id={`lecture-block-${blockIndex}`} className="space-y-3">
                  {showHeader && (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <CollapsibleTrigger asChild>
                        <button
                          type="button"
                          className="group flex min-w-0 flex-1 items-center gap-3 rounded-xl px-1 py-1 text-left transition hover:bg-muted/40"
                        >
                          <span className="mt-5 text-muted-foreground">
                            {isOpen ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                              {t("learn.block")}
                            </p>
                            <h2 className="truncate text-xl font-semibold text-foreground">
                              {blockTitle ?? t("learn.untitledBlock")}
                            </h2>
                          </div>
                        </button>
                      </CollapsibleTrigger>
                      <span
                        className={cn(
                          "rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground",
                          !isOpen && "bg-secondary/70"
                        )}
                      >
                        {block.lectures.length} {t("learn.lecturesCount")}
                      </span>
                    </div>
                  )}
                  <CollapsibleContent className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {block.lectures.map((lecture, lectureIndex) => (
                        <LectureCard
                          key={lecture.id ?? lecture.title ?? `${blockKey}-${lectureIndex}`}
                          lecture={lecture}
                          questionCount={getLectureCount(lecture)}
                          studyMeta={getLectureStudyMeta(lecture)}
                        />
                      ))}
                    </div>
                  </CollapsibleContent>
                </section>
              </Collapsible>
            );
          })}
        </div>
      )}
    </div>
  );
}
