"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { X, Search, Sparkles } from "lucide-react";
import {
    bulkClassifyQuestions,
    getBlocks,
    getBlockWorkspace,
    getExams,
    getUnclassifiedQuestions,
    type ManageBlock,
    type ManageLecture,
    type ManageExam,
    type ManageQuestion,
} from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

type BlockWithLectures = ManageBlock & { lectures: ManageLecture[] };

export default function UnclassifiedPage() {
    const [questions, setQuestions] = useState<ManageQuestion[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [blocks, setBlocks] = useState<BlockWithLectures[]>([]);
    const [exams, setExams] = useState<ManageExam[]>([]);
    const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
    const [searchQuery, setSearchQuery] = useState("");

    const [selectedLectureId, setSelectedLectureId] = useState<number | null>(null);

    // 선택된 문제들
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [classifying, setClassifying] = useState(false);
    const [selectAllLoading, setSelectAllLoading] = useState(false);
    const [selectAllTotal, setSelectAllTotal] = useState<number | null>(null);
    const selectAllRef = useRef<HTMLInputElement>(null);

    const examLookup = useMemo(() => {
        const map = new Map<number, ManageExam>();
        exams.forEach((exam) => {
            map.set(exam.id, exam);
        });
        return map;
    }, [exams]);

    const resolveExamLabel = (question: ManageQuestion) => {
        if (question.examTitle) return question.examTitle;
        if (typeof question.examId === "number") {
            const exam = examLookup.get(question.examId);
            return exam?.title ?? `Exam #${question.examId}`;
        }
        return "Unknown exam";
    };

    const refreshQuestions = async (examId?: number | null) => {
        const data = await getUnclassifiedQuestions({
            status: "unclassified",
            limit: 100,
            examId: examId ?? selectedExamId ?? undefined,
        });
        setQuestions(data.items);
        setTotal(data.total);
        setSelectedIds(new Set());
        setSelectAllTotal(null);
    };

    useEffect(() => {
        let cancelled = false;
        setLoading(true);

        Promise.all([
            getBlocks(),
            getExams(),
            getUnclassifiedQuestions({ status: "unclassified", limit: 100 }),
        ])
            .then(async ([blocksData, examsData, unclassified]) => {
                if (cancelled) return;
                setExams(examsData);
                setQuestions(unclassified.items);
                setTotal(unclassified.total);

                // 각 블록의 강의 목록 가져오기
                const blocksWithLectures: BlockWithLectures[] = [];
                for (const block of blocksData) {
                    try {
                        const ws = await getBlockWorkspace(block.id);
                        blocksWithLectures.push({ ...block, lectures: ws.lectures });
                    } catch {
                        blocksWithLectures.push({ ...block, lectures: [] });
                    }
                }
                if (!cancelled) setBlocks(blocksWithLectures);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "Failed to load data.");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => { cancelled = true; };
    }, []);

    // 필터링된 문제들
    const filteredQuestions = questions.filter((q) => {
        if (selectedExamId && q.examId !== selectedExamId) return false;
        if (searchQuery && !q.content?.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    const selectionScopeTotal = selectAllTotal ?? total;
    const allSelected = selectionScopeTotal > 0 && selectedIds.size === selectionScopeTotal;
    const someSelected = selectedIds.size > 0 && !allSelected;

    useEffect(() => {
        if (selectAllRef.current) {
            selectAllRef.current.indeterminate = someSelected;
        }
    }, [someSelected]);

    useEffect(() => {
        setSelectAllTotal(null);
    }, [selectedExamId, searchQuery]);

    const toggleQuestion = (id: number) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const fetchAllUnclassifiedIds = async () => {
        const ids: number[] = [];
        const limit = 200;
        let offset = 0;
        let totalCount = 0;
        const trimmedQuery = searchQuery.trim();

        do {
            const data = await getUnclassifiedQuestions({
                status: "unclassified",
                limit,
                offset,
                examId: selectedExamId ?? undefined,
                query: trimmedQuery ? trimmedQuery : undefined,
            });
            totalCount = data.total;
            data.items.forEach((item) => ids.push(item.id));
            offset += limit;
        } while (offset < totalCount);

        return { ids, totalCount };
    };

    const toggleSelectAll = async () => {
        if (selectAllLoading) return;
        if (allSelected) {
            setSelectedIds(new Set());
            setSelectAllTotal(null);
        } else {
            setSelectAllLoading(true);
            try {
                const { ids, totalCount } = await fetchAllUnclassifiedIds();
                setSelectedIds(new Set(ids));
                setSelectAllTotal(totalCount);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to select all questions.");
            } finally {
                setSelectAllLoading(false);
            }
        }
    };

    const handleBulkClassify = async () => {
        if (!selectedLectureId || selectedIds.size === 0) return;
        setClassifying(true);
        try {
            await bulkClassifyQuestions(Array.from(selectedIds), selectedLectureId);
            await refreshQuestions();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Classification failed.");
        } finally {
            setClassifying(false);
        }
    };

    const clearSelection = () => {
        setSelectedIds(new Set());
    };

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
                Loading...
            </div>
        );
    }

    if (error) {
        return (
            <Card className="border border-danger/30 bg-danger/10">
                <CardContent className="p-6">
                    <p className="text-danger">{error}</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                        Classification Queue
                    </p>
                    <h2 className="text-2xl font-semibold text-foreground">
                        Unclassified Questions
                    </h2>
                </div>
                <Badge variant="danger" className="text-base px-4 py-2">
                    {total} unclassified
                </Badge>
            </div>

            <div className="space-y-4">
                {/* 필터 바 */}
                <Card className="border border-border/70 bg-card/85">
                    <CardContent className="flex flex-wrap items-center gap-4 p-4">
                        <div className="relative flex-1 min-w-[200px]">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Search questions..."
                                className="pl-9"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Exam:</span>
                            <Select
                                value={selectedExamId ? String(selectedExamId) : ""}
                                onChange={(e) => {
                                    const val = e.target.value ? Number(e.target.value) : null;
                                    setSelectedExamId(val);
                                }}
                                className="min-w-[150px]"
                            >
                                <option value="">All Exams</option>
                                {exams.map((exam) => (
                                    <option key={exam.id} value={exam.id}>
                                        {exam.title}
                                    </option>
                                ))}
                            </Select>
                        </div>
                    </CardContent>
                </Card>

                {/* 전체 선택 바 */}
                <Card className="border border-primary/20 bg-primary/5">
                    <CardContent className="flex items-center gap-4 p-3">
                        <label className="flex items-center gap-2 cursor-pointer text-sm">
                            <input
                                ref={selectAllRef}
                                type="checkbox"
                                checked={allSelected}
                                onChange={toggleSelectAll}
                                disabled={selectAllLoading}
                                className="h-4 w-4 accent-primary"
                            />
                            {selectAllLoading ? "Selecting..." : "Select All"}
                        </label>
                        {selectedIds.size > 0 && (
                            <span className="text-sm text-primary font-medium">
                                {selectedIds.size} selected
                            </span>
                        )}
                        <div className="ml-auto flex items-center gap-2">
                            <Button variant="outline" size="sm" disabled>
                                <Sparkles className="h-4 w-4 mr-1" />
                                AI Classify (Coming Soon)
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* 문제 카드 그리드 */}
                {filteredQuestions.length === 0 ? (
                    <Card className="border border-border/70 bg-card/85">
                        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                            <div className="text-5xl mb-4">🎉</div>
                            <p className="text-lg font-medium text-foreground">All questions classified!</p>
                            <p className="text-sm text-muted-foreground">No unclassified questions remaining.</p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {filteredQuestions.map((q) => {
                            const isSelected = selectedIds.has(q.id);
                            const exam = typeof q.examId === "number" ? examLookup.get(q.examId) : undefined;
                            const examLabel = resolveExamLabel(q);
                            const examMetaParts = [
                                exam?.year ? String(exam.year) : null,
                                exam?.term ?? null,
                                exam?.subject ?? null,
                            ].filter(Boolean);
                            const examMeta = examMetaParts.join(" · ");
                            return (
                                <Card
                                    key={q.id}
                                    className={`border transition-all cursor-pointer ${isSelected
                                        ? "border-primary bg-primary/10"
                                        : "border-border/70 bg-card/85 hover:border-border"
                                        }`}
                                    onClick={() => toggleQuestion(q.id)}
                                >
                                    <div className="flex items-center gap-3 px-4 py-2 bg-muted/30 border-b border-border/50">
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => toggleQuestion(q.id)}
                                            onClick={(e) => e.stopPropagation()}
                                            className="h-4 w-4 accent-primary"
                                        />
                                        <Badge variant="neutral">Q{q.questionNumber}</Badge>
                                        <div className="flex items-center gap-2 min-w-0">
                                            <Badge variant="outline" className="text-[10px] px-2 py-0.5">
                                                Exam
                                            </Badge>
                                            <span className="text-xs text-muted-foreground truncate">
                                                {examLabel}
                                            </span>
                                            {examMeta && (
                                                <span className="text-[10px] text-muted-foreground/70 truncate">
                                                    {examMeta}
                                                </span>
                                            )}
                                        </div>
                                        <div className="ml-auto flex items-center gap-2">
                                            {q.hasImage && (
                                                <Badge variant="outline" className="text-[10px] px-2 py-0.5">
                                                    Image
                                                </Badge>
                                            )}
                                            {q.lectureTitle && (
                                                <Badge variant="success" className="text-xs">
                                                    {q.lectureTitle}
                                                </Badge>
                                            )}
                                            <Link
                                                href={`/manage/questions/${q.id}`}
                                                onClick={(e) => e.stopPropagation()}
                                                className="text-xs text-muted-foreground hover:text-foreground"
                                            >
                                                ✏️
                                            </Link>
                                        </div>
                                    </div>
                                    <CardContent className="p-4">
                                        <p className="text-sm leading-relaxed line-clamp-4">
                                            {q.content?.slice(0, 200) || "(Image question)"}
                                            {(q.content?.length ?? 0) > 200 && "..."}
                                        </p>
                                        {q.choices && q.choices.length > 0 && (
                                            <div className="mt-3 space-y-1">
                                                {q.choices.slice(0, 4).map((c, i) => {
                                                    const number = c.choiceNumber ?? c.number ?? i + 1;
                                                    return (
                                                        <div
                                                            key={c.id ?? i}
                                                            className={`text-xs px-2 py-1 rounded ${c.isCorrect
                                                                ? "bg-success/20 text-success"
                                                                : "bg-muted/30 text-muted-foreground"
                                                                }`}
                                                        >
                                                            <span className="font-medium mr-2">{number}.</span>
                                                            {c.content?.slice(0, 50) ?? ""}
                                                            {(c.content?.length ?? 0) > 50 && "..."}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* 하단 고정 일괄 분류 바 */}
            <div
                className={`fixed bottom-0 left-0 right-0 bg-card border-t border-border shadow-lg transition-transform z-50 ${selectedIds.size > 0 ? "translate-y-0" : "translate-y-full"
                    }`}
            >
                <div className="max-w-7xl mx-auto flex items-center justify-center gap-6 px-6 py-4">
                    <span className="text-primary font-semibold">
                        {selectedIds.size} questions selected
                    </span>
                    <Select
                        value={selectedLectureId ? String(selectedLectureId) : ""}
                        onChange={(e) => setSelectedLectureId(e.target.value ? Number(e.target.value) : null)}
                        className="min-w-[300px]"
                    >
                        <option value="">Select lecture to classify...</option>
                        {blocks.map((block) => (
                            <optgroup
                                key={block.id}
                                label={`${block.subject ?? "Unassigned"} · ${block.name}`}
                            >
                                {block.lectures.map((lecture) => (
                                    <option key={lecture.id} value={lecture.id}>
                                        {lecture.order}. {lecture.title}
                                    </option>
                                ))}
                            </optgroup>
                        ))}
                    </Select>
                    <Button
                        onClick={handleBulkClassify}
                        disabled={classifying || !selectedLectureId}
                    >
                        {classifying ? "Classifying..." : "Bulk Classify"}
                    </Button>
                    <Button variant="ghost" onClick={clearSelection}>
                        <X className="h-4 w-4 mr-1" />
                        Cancel
                    </Button>
                </div>
            </div>
        </div>
    );
}
