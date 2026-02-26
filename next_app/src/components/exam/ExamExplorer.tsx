"use client";

import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import type { ExamSummary, BlockSummary } from "@/lib/api/exam";
import { cn } from "@/lib/utils";

interface ExamExplorerProps {
    exams: ExamSummary[];
    blocks: BlockSummary[];
    examFilter: string;
    setExamFilter: (val: string) => void;
    superBlockFilter: string;
    setSuperBlockFilter: (val: string) => void;
}

function getYear(exam: ExamSummary): number | null {
    if (exam.year) return exam.year;
    if (exam.examDate) {
        const d = new Date(exam.examDate);
        if (!isNaN(d.getTime())) return d.getFullYear();
    }
    return null;
}

function getTermLabel(exam: ExamSummary): string {
    if (exam.term) return exam.term;
    // Try to extract from title, e.g. "병원체학-2025-3차" -> "3차"
    const match = exam.title.match(/(\d+차)/);
    if (match) return match[1];
    return exam.title;
}

/* ────────────── Column item component ────────────── */

function ColumnItem({
    label,
    selected,
    hasChildren,
    onClick,
}: {
    label: string;
    selected: boolean;
    hasChildren?: boolean;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "flex w-full items-center justify-between gap-1.5 rounded-md px-2.5 py-1 text-left text-xs transition-colors",
                selected
                    ? "bg-primary text-primary-foreground font-medium"
                    : "hover:bg-muted/80 text-foreground/80"
            )}
        >
            <span className="truncate leading-snug">{label}</span>
            {hasChildren && (
                <ChevronRight className={cn("h-3 w-3 shrink-0", selected ? "text-primary-foreground/70" : "opacity-40")} />
            )}
        </button>
    );
}

/* ────────────── Year group header ────────────── */

function YearGroup({
    year,
    exams,
    examFilter,
    onExamClick,
}: {
    year: string;
    exams: ExamSummary[];
    examFilter: string;
    onExamClick: (id: string) => void;
}) {
    return (
        <div className="mb-1">
            <div className="px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                {year}
            </div>
            <div className="space-y-0.5">
                {exams.map((exam) => (
                    <ColumnItem
                        key={exam.id}
                        label={getTermLabel(exam)}
                        selected={examFilter === String(exam.id)}
                        onClick={() => onExamClick(String(exam.id))}
                    />
                ))}
            </div>
        </div>
    );
}

/* ────────────── Scrollable column wrapper ────────────── */

function Column({
    title,
    children,
    show,
}: {
    title: string;
    children: React.ReactNode;
    show: boolean;
}) {
    if (!show) return null;
    return (
        <div className="flex h-full min-w-[140px] max-w-[180px] flex-col border-r border-border/50 last:border-r-0">
            <div className="shrink-0 border-b border-border/40 bg-muted/20 px-2.5 py-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                    {title}
                </span>
            </div>
            <div className="flex-1 overflow-y-auto p-1 space-y-0.5">
                {children}
            </div>
        </div>
    );
}

/* ────────────── Main component ────────────── */

export function ExamExplorer({
    exams,
    blocks,
    examFilter,
    setExamFilter,
    superBlockFilter,
    setSuperBlockFilter,
}: ExamExplorerProps) {
    const { t } = useLanguage();
    const [selectedSubject, setSelectedSubject] = useState<string | null>(null);

    /* ── Derive subject list from exams + blocks ── */
    const subjects = useMemo(() => {
        const set = new Set<string>();
        exams.forEach((e) => {
            if (e.subject) set.add(e.subject);
        });
        blocks.forEach((b) => {
            if (b.subject) set.add(b.subject);
        });
        return Array.from(set).sort();
    }, [exams, blocks]);

    /* ── Exams for selected subject, grouped by year ── */
    const examsByYear = useMemo(() => {
        if (!selectedSubject) return [];
        const filtered = exams.filter((e) => e.subject === selectedSubject);

        // Group by year
        const yearMap = new Map<string, ExamSummary[]>();
        filtered.forEach((exam) => {
            const y = getYear(exam);
            const key = y ? `${y}년` : "연도 미상";
            if (!yearMap.has(key)) yearMap.set(key, []);
            yearMap.get(key)!.push(exam);
        });

        // Sort years descending, sort exams within each year
        const entries = Array.from(yearMap.entries()).sort((a, b) => b[0].localeCompare(a[0]));
        entries.forEach(([, exs]) => {
            exs.sort((a, b) => {
                const ta = a.term ?? "";
                const tb = b.term ?? "";
                return ta.localeCompare(tb, undefined, { numeric: true });
            });
        });
        return entries;
    }, [exams, selectedSubject]);

    /* ── Blocks for selected subject ── */
    const subjectBlocks = useMemo(() => {
        if (!selectedSubject) return [];
        return blocks.filter((b) => b.subject === selectedSubject);
    }, [blocks, selectedSubject]);

    /* ── Handlers ── */
    const handleSubjectClick = (subject: string) => {
        setSelectedSubject(subject);
        setExamFilter("");
        setSuperBlockFilter("");
    };

    const handleExamClick = (examId: string) => {
        setExamFilter(examFilter === examId ? "" : examId);
    };

    const handleBlockClick = (blockId: string) => {
        setSuperBlockFilter(superBlockFilter === blockId ? "" : blockId);
    };

    return (
        <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border/70 bg-card/85 shadow-soft">
            {/* Header */}
            <div className="shrink-0 border-b border-border/50 bg-muted/30 px-3 py-2">
                <h3 className="text-xs font-semibold">{t("classifications.tableExam")} 탐색기</h3>
            </div>

            {/* Multi-column body */}
            <div className="flex flex-1 overflow-x-auto overflow-y-hidden">
                {/* Column 1: Subjects */}
                <Column title="과목" show={true}>
                    <ColumnItem
                        label={t("classifications.allExams")}
                        selected={!selectedSubject}
                        onClick={() => {
                            setSelectedSubject(null);
                            setExamFilter("");
                            setSuperBlockFilter("");
                        }}
                    />
                    {subjects.map((subject) => (
                        <ColumnItem
                            key={subject}
                            label={subject}
                            selected={selectedSubject === subject}
                            hasChildren
                            onClick={() => handleSubjectClick(subject)}
                        />
                    ))}
                    {subjects.length === 0 && (
                        <p className="px-2 py-4 text-center text-[10px] text-muted-foreground">
                            과목이 없습니다.
                        </p>
                    )}
                </Column>

                {/* Column 2: Exams grouped by year */}
                <Column title="시험지" show={!!selectedSubject}>
                    {examsByYear.map(([year, yearExams]) => (
                        <YearGroup
                            key={year}
                            year={year}
                            exams={yearExams}
                            examFilter={examFilter}
                            onExamClick={handleExamClick}
                        />
                    ))}
                    {examsByYear.length === 0 && selectedSubject && (
                        <p className="px-2 py-4 text-center text-[10px] text-muted-foreground">
                            시험지가 없습니다.
                        </p>
                    )}
                </Column>

                {/* Column 3: Blocks */}
                <Column title="블럭" show={!!selectedSubject}>
                    {subjectBlocks.map((block) => (
                        <ColumnItem
                            key={block.id}
                            label={block.name}
                            selected={superBlockFilter === String(block.id)}
                            onClick={() => handleBlockClick(String(block.id))}
                        />
                    ))}
                    {subjectBlocks.length === 0 && selectedSubject && (
                        <p className="px-2 py-4 text-center text-[10px] text-muted-foreground">
                            블럭이 없습니다.
                        </p>
                    )}
                </Column>
            </div>
        </div>
    );
}
