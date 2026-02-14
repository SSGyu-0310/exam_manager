"use client";

import { useEffect, useState } from "react";
import { Star, ArrowRight } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/http";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";

interface Bookmark {
    id: number;
    title: string;
    lectureId: number;
}

export function Bookmarks() {
    const { t } = useLanguage();
    const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchBookmarks = async () => {
            try {
                const res = await apiFetch<any>("/api/dashboard/bookmarks");
                if (res.ok) {
                    setBookmarks(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch bookmarks", error);
            } finally {
                setLoading(false);
            }
        };
        fetchBookmarks();
    }, []);

    if (loading) {
        return <Card className="shadow-sm border-border animate-pulse h-48" />;
    }

    return (
        <Card className="shadow-sm border-border">
            <CardHeader className="pb-3 border-b border-border/50">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold text-foreground">{t("dashboard.bookmarksTitle")}</CardTitle>
                    <Star className="h-4 w-4 text-muted-foreground" />
                </div>
            </CardHeader>
            <CardContent className="pt-4">
                <div className="space-y-2">
                    {bookmarks.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-2 text-center">{t("dashboard.bookmarksEmpty")}</p>
                    ) : (
                        bookmarks.map((bookmark) => (
                            <Link key={bookmark.id} href={`/practice/session/0?questionId=${bookmark.id}`}>
                                <div className="group flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-muted transition-colors cursor-pointer">
                                    <span className="truncate text-foreground/80 group-hover:text-primary transition-colors">{bookmark.title}</span>
                                    <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                                </div>
                            </Link>
                        ))
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
