import { z } from "zod";

import { apiFetch } from "@/lib/http";

const examSchema = z.object({
  id: z.number(),
  title: z.string(),
  examDate: z.string().nullable().optional(),
  questionCount: z.number().optional(),
});

const lectureSchema = z.object({
  id: z.number(),
  title: z.string(),
});

const blockSchema = z.object({
  id: z.number(),
  name: z.string(),
  subject: z.string().nullable().optional(),
  lectures: z.array(lectureSchema).optional().default([]),
});

const questionSchema = z.object({
  id: z.number(),
  examId: z.number(),
  examTitle: z.string().nullable().optional(),
  questionNumber: z.number(),
  type: z.string().nullable().optional(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  blockId: z.number().nullable().optional(),
  blockName: z.string().nullable().optional(),
  isClassified: z.boolean(),
  snippet: z.string().optional(),
  hasImage: z.boolean().optional(),
});

const unclassifiedSchema = z.object({
  items: z.array(questionSchema),
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
  unclassifiedCount: z.number(),
  blocks: z.array(blockSchema),
  exams: z.array(examSchema),
});

const okResponse = <T extends z.ZodTypeAny>(schema: T) =>
  z.object({ ok: z.literal(true), data: schema });

export type UnclassifiedQueue = z.infer<typeof unclassifiedSchema>;
export type UnclassifiedQuestion = z.infer<typeof questionSchema>;
export type ExamSummary = z.infer<typeof examSchema>;
export type BlockSummary = z.infer<typeof blockSchema>;

export async function getUnclassifiedQueue(params?: {
  status?: "all" | "unclassified";
  examId?: string | number;
  query?: string;
  limit?: number;
  offset?: number;
}) {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.examId) search.set("examId", String(params.examId));
  if (params?.query) search.set("query", params.query);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const suffix = search.toString();
  const payload = await apiFetch<unknown>(
    `/api/exam/unclassified${suffix ? `?${suffix}` : ""}`,
    { cache: "no-store" }
  );
  return okResponse(unclassifiedSchema).parse(payload).data;
}
