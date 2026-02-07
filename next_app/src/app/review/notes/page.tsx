"use client";

import { useEffect, useState } from "react";
import { FileText, ChevronRight, Bookmark } from "lucide-react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";

import { apiFetch } from "@/lib/http";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ReviewNote {
    id: number;
    questionNumber: number;
    content: string;
    examTitle: string;
    lectureTitle: string | null;
    hasNote: boolean;
    isWrong: boolean;
}

export default function ReviewNotesPage() {
    const { t } = useLanguage();
    const [notes, setNotes] = useState<ReviewNote[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchNotes = async () => {
            try {
                const res = await apiFetch<any>("/api/review/notes");
                if (res.ok) {
                    setNotes(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch review notes", error);
            } finally {
                setLoading(false);
            }
        };
        fetchNotes();
    }, []);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("review.notes")}</h1>
                <p className="text-muted-foreground">{t("review.notesDesc")}</p>
            </div>

            <div className="grid gap-4">
                {loading ? (
                    [1, 2, 3].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-xl" />)
                ) : notes.length === 0 ? (
                    <Card className="border-border bg-card">
                        <CardContent className="flex flex-col items-center justify-center py-12">
                            <Bookmark className="h-12 w-12 text-muted-foreground/30 mb-4" />
                            <p className="text-lg font-medium text-foreground">{t("review.noItems")}</p>
                            <p className="text-sm text-muted-foreground">{t("review.noItemsDesc")}</p>
                        </CardContent>
                    </Card>
                ) : (
                    notes.map((note) => (
                        <Card key={note.id} className="group overflow-hidden border-border bg-card hover:border-primary/50 transition-colors">
                            <CardContent className="p-0">
                                <Link href={`/practice/session/0?questionId=${note.id}`} className="flex items-center p-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-secondary text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                                        <FileText className="h-6 w-6" />
                                    </div>
                                    <div className="ml-4 flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-foreground">{t("review.question")} {note.questionNumber}</span>
                                            <span className="text-xs text-muted-foreground">• {note.examTitle}</span>
                                        </div>
                                        <p className="text-sm text-muted-foreground line-clamp-1">{note.content}</p>
                                        <div className="flex gap-2 mt-1">
                                            {note.isWrong && <Badge variant="danger" className="text-[10px] px-1.5 py-0">{t("review.wrong")}</Badge>}
                                            {note.hasNote && <Badge variant="neutral" className="text-[10px] px-1.5 py-0">{t("review.note")}</Badge>}
                                            {note.lectureTitle && <span className="text-[10px] text-muted-foreground ml-auto">{note.lectureTitle}</span>}
                                        </div>
                                    </div>
                                    <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-all opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0" />
                                </Link>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>
        </div>
    );
}

