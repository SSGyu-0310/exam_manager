"use client";

import { useEffect, useState } from "react";
import { LectureGrid } from "@/components/lectures/LectureGrid";
import type { Block, LectureSort } from "@/components/lectures/types";
import { apiFetch } from "@/lib/http";
import { useLanguage } from "@/context/LanguageContext";

export default function PracticePage() {
    const { t } = useLanguage();
    const [blocks, setBlocks] = useState<Block[]>([]);
    const [query, setQuery] = useState("");
    const [sort, setSort] = useState<LectureSort>("title");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchLectures = async () => {
            try {
                const data = await apiFetch<any>("/api/practice/lectures");
                if (data.blocks) {
                    setBlocks(data.blocks);
                }
            } catch (error) {
                console.error("Failed to fetch lectures", error);
            } finally {
                setLoading(false);
            }
        };

        fetchLectures();
    }, []);

    if (loading) {
        return <div className="p-8 text-center text-muted-foreground">{t("learn.loadingLectures")}</div>;
        // We could use a skeleton here
    }

    return (
        <div className="container mx-auto py-8 space-y-8">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">{t("learn.practiceMode")}</h1>
                <p className="text-muted-foreground">{t("learn.selectLecture")}</p>
            </div>

            <LectureGrid
                blocks={blocks}
                query={query}
                onQueryChange={setQuery}
                sort={sort}
                onSortChange={setSort}
            />
        </div>
    );
}
