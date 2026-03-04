"use client";

import { useEffect, useState } from "react";
import { LectureGrid } from "@/components/lectures/LectureGrid";
import type {
    Block,
    LectureSort,
    LectureStudyMeta,
} from "@/components/lectures/types";
import { apiFetch } from "@/lib/http";
import { useLanguage } from "@/context/LanguageContext";

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const toTimestamp = (value: string | null): number => {
    if (!value) return 0;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

const toNumber = (value: unknown): number => {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string") {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) return parsed;
    }
    return 0;
};

const extractStudyMeta = (payload: unknown): Record<string, LectureStudyMeta> => {
    if (!isRecord(payload) || !Array.isArray(payload.sessions)) {
        return {};
    }

    const result: Record<string, LectureStudyMeta> = {};
    const inProgressTimestamps: Record<string, number> = {};

    for (const item of payload.sessions) {
        if (!isRecord(item)) continue;
        const lectureId = item.lectureId;
        if (typeof lectureId !== "string" && typeof lectureId !== "number") continue;

        const key = String(lectureId);
        const sessionId = item.sessionId;
        const sessionIdString =
            typeof sessionId === "string" || typeof sessionId === "number"
                ? String(sessionId)
                : null;
        const finishedAt = typeof item.finishedAt === "string" ? item.finishedAt : null;
        const createdAt = typeof item.createdAt === "string" ? item.createdAt : null;
        const studiedAt = finishedAt ?? createdAt;
        const studiedTimestamp = toTimestamp(studiedAt);
        const existing = result[key];
        const existingTimestamp = toTimestamp(existing?.lastStudiedAt ?? null);

        if (!existing) {
            result[key] = {
                lastStudiedAt: studiedAt,
                inProgressSessionId: null,
                answeredCount: 0,
                totalQuestions: 0,
            };
        } else if (studiedTimestamp > existingTimestamp) {
            result[key] = {
                ...existing,
                lastStudiedAt: studiedAt,
            };
        }

        if (!finishedAt && sessionIdString) {
            const inProgressTimestamp = toTimestamp(createdAt);
            const previousProgressTimestamp = inProgressTimestamps[key] ?? 0;
            if (inProgressTimestamp >= previousProgressTimestamp) {
                inProgressTimestamps[key] = inProgressTimestamp;
                result[key] = {
                    ...(result[key] ?? {
                        lastStudiedAt: studiedAt,
                        inProgressSessionId: null,
                        answeredCount: 0,
                        totalQuestions: 0,
                    }),
                    inProgressSessionId: sessionIdString,
                    answeredCount: toNumber(item.answeredCount),
                    totalQuestions: toNumber(item.totalQuestions),
                };
            }
        }
    }

    return result;
};

export default function PracticePage() {
    const { t } = useLanguage();
    const [blocks, setBlocks] = useState<Block[]>([]);
    const [studyMetaByLecture, setStudyMetaByLecture] = useState<
        Record<string, LectureStudyMeta>
    >({});
    const [query, setQuery] = useState("");
    const [sort, setSort] = useState<LectureSort>("manual");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPageData = async () => {
            try {
                const [lecturesResult, sessionsResult] = await Promise.allSettled([
                    apiFetch<unknown>("/api/practice/lectures"),
                    apiFetch<unknown>("/api/practice/sessions", { cache: "no-store" }),
                ]);

                if (lecturesResult.status === "fulfilled") {
                    const lecturePayload = lecturesResult.value;
                    if (isRecord(lecturePayload) && Array.isArray(lecturePayload.blocks)) {
                        setBlocks(lecturePayload.blocks as Block[]);
                    }
                } else {
                    console.error("Failed to fetch lectures", lecturesResult.reason);
                }

                if (sessionsResult.status === "fulfilled") {
                    setStudyMetaByLecture(extractStudyMeta(sessionsResult.value));
                } else {
                    setStudyMetaByLecture({});
                }
            } catch (error) {
                console.error("Failed to fetch lectures", error);
            } finally {
                setLoading(false);
            }
        };

        fetchPageData();
    }, []);

    if (loading) {
        return <div className="p-8 text-center text-muted-foreground">{t("learn.loadingLectures")}</div>;
        // We could use a skeleton here
    }

    return (
        <div className="container mx-auto py-5">
            <LectureGrid
                blocks={blocks}
                studyMetaByLecture={studyMetaByLecture}
                query={query}
                onQueryChange={setQuery}
                sort={sort}
                onSortChange={setSort}
            />
        </div>
    );
}
