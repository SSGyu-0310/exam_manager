"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/http";

type Lecture = {
  lectureId?: number;
  title?: string;
  order?: number;
  questionCount?: number;
};

type Block = {
  blockId?: number;
  title?: string;
  lectures?: Lecture[];
};

type LecturesResponse = {
  blocks?: Block[];
  ok?: boolean;
  data?: Block[];
};

export default function LecturesPage() {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    apiFetch<LecturesResponse>("/api/practice/lectures")
      .then((response) => {
        if (!active) return;
        if (Array.isArray(response.data)) {
          setBlocks(response.data);
          return;
        }
        if (Array.isArray(response.blocks)) {
          setBlocks(response.blocks);
          return;
        }
        setBlocks([]);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load lectures.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <main style={{ padding: "2rem" }}>
      <h1>Lectures</h1>
      {loading && <p>Loading...</p>}
      {!loading && error && <p>{error}</p>}
      {!loading && !error && blocks.length === 0 && <p>No lectures found.</p>}
      {!loading &&
        !error &&
        blocks.map((block) => (
          <section key={block.blockId ?? block.title} style={{ marginTop: "1.5rem" }}>
            <h2>{block.title ?? "Untitled Block"}</h2>
            <ul>
              {(block.lectures ?? []).map((lecture) => (
                <li key={lecture.lectureId ?? lecture.title}>
                  <strong>{lecture.title ?? "Untitled Lecture"}</strong> (ID: {lecture.lectureId ?? "-"})
                  {typeof lecture.questionCount === "number" && (
                    <> | Questions: {lecture.questionCount}</>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
    </main>
  );
}
