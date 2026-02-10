import { z } from "zod";

import { apiFetch } from "@/lib/http";

const blockSchema = z.object({
  id: z.number(),
  name: z.string(),
  subject: z.string().nullable().optional(),
  subjectId: z.number().nullable().optional(),
  description: z.string().nullable().optional(),
  order: z.number().optional(),
  lectureCount: z.number().optional(),
  questionCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const lectureSchema = z.object({
  id: z.number(),
  blockId: z.number(),
  blockName: z.string().nullable().optional(),
  blockSubject: z.string().nullable().optional(),
  title: z.string(),
  professor: z.string().nullable().optional(),
  order: z.number().optional(),
  description: z.string().nullable().optional(),
  questionCount: z.number().optional(),
  classifiedCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const examSchema = z.object({
  id: z.number(),
  title: z.string(),
  examDate: z.string().nullable().optional(),
  subject: z.string().nullable().optional(),
  year: z.number().nullable().optional(),
  term: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  questionCount: z.number().optional(),
  classifiedCount: z.number().optional(),
  unclassifiedCount: z.number().optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

const choiceSchema = z.object({
  id: z.number().optional(),
  choiceNumber: z.number().optional(),
  number: z.number().optional(),
  content: z.string().nullable().optional(),
  imagePath: z.string().nullable().optional(),
  isCorrect: z.boolean().optional(),
});

const questionSchema = z.object({
  id: z.number(),
  questionNumber: z.number(),
  type: z.string().optional(),
  content: z.string().nullable().optional(),
  examId: z.number().optional(),
  examTitle: z.string().nullable().optional(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  isClassified: z.boolean(),
  classificationStatus: z.string().nullable().optional(),
  hasImage: z.boolean().optional(),
  choices: z.array(choiceSchema).optional(),
});


const questionDetailSchema = z.object({
  id: z.number(),
  examId: z.number(),
  examTitle: z.string().nullable().optional(),
  questionNumber: z.number(),
  examiner: z.string().nullable().optional(),
  type: z.string(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  content: z.string().nullable().optional(),
  explanation: z.string().nullable().optional(),
  imagePath: z.string().nullable().optional(),
  originalImageUrl: z.string().nullable().optional(),
  answer: z.string().nullable().optional(),
  correctAnswerText: z.string().nullable().optional(),
  choices: z.array(choiceSchema),
});

const summarySchema = z.object({
  counts: z.object({
    blocks: z.number(),
    lectures: z.number(),
    exams: z.number(),
    questions: z.number(),
    unclassified: z.number(),
  }),
  recentExams: z.array(examSchema),
});

const blocksSchema = z.array(blockSchema);
const lecturesSchema = z.array(lectureSchema);
const examsSchema = z.array(examSchema);
const subjectsSchema = z.array(
  z.object({
    id: z.number(),
    name: z.string(),
    order: z.number().optional(),
    description: z.string().nullable().optional(),
    ownerId: z.number().nullable().optional(),
    isPublic: z.boolean().optional(),
    createdAt: z.string().nullable().optional(),
    updatedAt: z.string().nullable().optional(),
  })
);

const blockLecturesSchema = z.object({
  block: blockSchema,
  lectures: lecturesSchema,
});

const blockWorkspaceSchema = z.object({
  block: blockSchema,
  lectures: lecturesSchema,
  exams: examsSchema,
});


const examDetailSchema = z.object({
  exam: examSchema,
  questions: z.array(questionSchema),
});

const materialSchema = z.object({
  id: z.number(),
  originalFilename: z.string().nullable().optional(),
  filePath: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  uploadedAt: z.string().nullable().optional(),
  indexedAt: z.string().nullable().optional(),
  chunks: z.number().optional(),
});

const lectureQuestionSchema = z.object({
  id: z.number(),
  questionNumber: z.number(),
  type: z.string().optional(),
  lectureId: z.number().nullable().optional(),
  lectureTitle: z.string().nullable().optional(),
  isClassified: z.boolean(),
  classificationStatus: z.string().nullable().optional(),
  hasImage: z.boolean().optional(),
  content: z.string().nullable().optional(),
  answer: z.string().nullable().optional(),
  explanation: z.string().nullable().optional(),
  examTitle: z.string().nullable().optional(),
  choices: z.array(choiceSchema).optional(),
});

const lectureDetailSchema = z.object({
  lecture: lectureSchema,
  block: blockSchema.nullable().optional(),
  questions: z.array(lectureQuestionSchema),
  materials: z.array(materialSchema),
});


const uploadPdfSchema = z.object({
  examId: z.number(),
  questionCount: z.number(),
  choiceCount: z.number(),
});

const uploadLectureMaterialSchema = z.object({
  materialId: z.number(),
  originalFilename: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  chunks: z.number().optional(),
  pages: z.number().optional(),
  uploadedAt: z.string().nullable().optional(),
  indexedAt: z.string().nullable().optional(),
});

const okResponse = <T extends z.ZodTypeAny>(schema: T) =>
  z.object({ ok: z.literal(true), data: schema });

export type ManageSummary = z.infer<typeof summarySchema>;
export type ManageBlock = z.infer<typeof blockSchema>;
export type ManageLecture = z.infer<typeof lectureSchema>;
export type ManageExam = z.infer<typeof examSchema>;
export type ManageQuestion = z.infer<typeof questionSchema>;
export type ManageChoice = z.infer<typeof choiceSchema>;
export type ManageQuestionDetail = z.infer<typeof questionDetailSchema>;
export type UploadPdfResult = z.infer<typeof uploadPdfSchema>;
export type UploadLectureMaterialResult = z.infer<typeof uploadLectureMaterialSchema>;
export type ManageBlockWorkspace = z.infer<typeof blockWorkspaceSchema>;
export type ManageLectureDetail = z.infer<typeof lectureDetailSchema>;
export type ManageMaterial = z.infer<typeof materialSchema>;
export type ManageLectureQuestion = z.infer<typeof lectureQuestionSchema>;
export type ManageSubject = z.infer<typeof subjectsSchema.element>;
export type ManageBlockInput = {
  name: string;
  subject?: string | null;
  subjectId?: number | null;
  description?: string | null;
  order?: number | null;
};
export type ManageSubjectInput = {
  name: string;
  description?: string | null;
  order?: number | null;
  isPublic?: boolean;
};
export type ManageLectureInput = {
  title: string;
  professor?: string | null;
  order?: number | null;
  description?: string | null;
};
export type ManageExamInput = {
  title?: string | null;
  examDate?: string | null;
  subject?: string | null;
  year?: number | null;
  term?: string | null;
  description?: string | null;
};

export async function getManageSummary() {
  const payload = await apiFetch<unknown>("/api/manage/summary", { cache: "no-store" });
  return okResponse(summarySchema).parse(payload).data;
}

export async function getBlocks() {
  const payload = await apiFetch<unknown>("/api/manage/blocks", { cache: "no-store" });
  return okResponse(blocksSchema).parse(payload).data;
}

export async function getSubjects() {
  const payload = await apiFetch<unknown>("/api/manage/subjects", { cache: "no-store" });
  return okResponse(subjectsSchema).parse(payload).data;
}

export async function createSubject(input: ManageSubjectInput) {
  const payload = await apiFetch<unknown>("/api/manage/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return okResponse(subjectsSchema.element).parse(payload).data;
}

export async function updateSubject(
  subjectId: string | number,
  input: Partial<ManageSubjectInput>
) {
  const payload = await apiFetch<unknown>(
    `/api/manage/subjects/${encodeURIComponent(String(subjectId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(subjectsSchema.element).parse(payload).data;
}

export async function getBlock(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    { cache: "no-store" }
  );
  return okResponse(blockSchema).parse(payload).data;
}

export async function getBlockLectures(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}/lectures`,
    { cache: "no-store" }
  );
  return okResponse(blockLecturesSchema).parse(payload).data;
}

export async function getBlockWorkspace(
  blockId: string | number,
  params: { subject?: string } = {}
) {
  const query = new URLSearchParams();
  if (params.subject) {
    query.set("subject", params.subject);
  }
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}/workspace?${query.toString()}`,
    { cache: "no-store" }
  );
  return okResponse(blockWorkspaceSchema).parse(payload).data;
}

export async function getLectures() {
  const payload = await apiFetch<unknown>("/api/manage/lectures", { cache: "no-store" });
  return okResponse(lecturesSchema).parse(payload).data;
}

export async function createBlock(input: ManageBlockInput) {
  const payload = await apiFetch<unknown>("/api/manage/blocks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return okResponse(blockSchema).parse(payload).data;
}

export async function updateBlock(blockId: string | number, input: Partial<ManageBlockInput>) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(blockSchema).parse(payload).data;
}

export async function deleteBlock(blockId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}

export async function getLecture(lectureId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    { cache: "no-store" }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function getLectureDetail(lectureId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}/detail`,
    { cache: "no-store" }
  );
  return okResponse(lectureDetailSchema).parse(payload).data;
}

export async function createLecture(blockId: string | number, input: ManageLectureInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/blocks/${encodeURIComponent(String(blockId))}/lectures`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function updateLecture(
  lectureId: string | number,
  input: Partial<ManageLectureInput>
) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(lectureSchema).parse(payload).data;
}

export async function deleteLecture(lectureId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}

export async function getQuestionDetail(questionId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/questions/${encodeURIComponent(String(questionId))}`,
    { cache: "no-store" }
  );
  return okResponse(questionDetailSchema).parse(payload).data;
}

export type ManageQuestionUpdate = {
  content?: string | null;
  explanation?: string | null;
  type?: string | null;
  lectureId?: number | null;
  correctAnswerText?: string | null;
  uploadedImage?: string | null;
  removeImage?: boolean;
  choices?: ManageChoice[];
};

export async function updateQuestion(
  questionId: string | number,
  input: ManageQuestionUpdate
) {
  const payload = await apiFetch<unknown>(
    `/api/manage/questions/${encodeURIComponent(String(questionId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(questionDetailSchema).parse(payload).data;
}

export async function uploadPdf(formData: FormData) {
  const payload = await apiFetch<unknown>("/api/manage/upload-pdf", {
    method: "POST",
    body: formData,
  });
  return okResponse(uploadPdfSchema).parse(payload).data;
}

export async function uploadLectureMaterial(
  lectureId: string | number,
  formData: FormData
) {
  const payload = await apiFetch<unknown>(
    `/api/manage/lectures/${encodeURIComponent(String(lectureId))}/materials`,
    {
      method: "POST",
      body: formData,
    }
  );
  return okResponse(uploadLectureMaterialSchema).parse(payload).data;
}

export async function getExams() {
  const payload = await apiFetch<unknown>("/api/manage/exams", { cache: "no-store" });
  return okResponse(examsSchema).parse(payload).data;
}

export async function getExamDetail(examId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    { cache: "no-store" }
  );
  return okResponse(examDetailSchema).parse(payload).data;
}

export async function updateExam(examId: string | number, input: ManageExamInput) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }
  );
  return okResponse(examSchema).parse(payload).data;
}

export async function deleteExam(examId: string | number) {
  const payload = await apiFetch<unknown>(
    `/api/manage/exams/${encodeURIComponent(String(examId))}`,
    { method: "DELETE" }
  );
  return okResponse(z.object({ id: z.number() })).parse(payload).data;
}

const unclassifiedResultSchema = z.object({
  items: z.array(questionSchema),
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
  unclassifiedCount: z.number(),
  blocks: blocksSchema.optional(),
  exams: examsSchema.optional(),
  scope: z
    .object({
      blockId: z.number().nullable().optional(),
      includeDescendants: z.boolean().optional(),
      filterScope: z.boolean().optional(),
      lectureIds: z.array(z.number()).nullable().optional(),
    })
    .optional(),
  candidateLectures: lecturesSchema.optional().nullable(),
});

export async function getUnclassifiedQuestions(
  params: {
    offset?: number;
    limit?: number;
    status?: string;
    blockId?: number | null;
    filterScope?: boolean;
    query?: string;
    examId?: number | null;
  } = {}
) {
  const query = new URLSearchParams();
  if (params.offset) query.set("offset", String(params.offset));
  if (params.limit) query.set("limit", String(params.limit));
  if (params.status) query.set("status", params.status);
  if (params.blockId !== undefined && params.blockId !== null) {
    query.set("blockId", String(params.blockId));
  }
  if (params.filterScope !== undefined) {
    query.set("filterScope", String(params.filterScope));
  }
  if (params.query) {
    query.set("query", params.query);
  }
  if (params.examId !== undefined && params.examId !== null) {
    query.set("examId", String(params.examId));
  }

  const payload = await apiFetch<unknown>(
    `/api/exam/unclassified?${query.toString()}`,
    { cache: "no-store" }
  );
  return okResponse(unclassifiedResultSchema).parse(payload).data;
}


const bulkClassifySchema = z.object({
  success: z.boolean(),
  updated_count: z.number().optional(),
  lecture_name: z.string().optional(),
  error: z.string().optional(),
});

export async function bulkClassifyQuestions(
  questionIds: number[],
  lectureId: number
) {
  const payload = await apiFetch<unknown>("/exam/questions/bulk-classify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_ids: questionIds,
      lecture_id: lectureId,
    }),
  });
  return bulkClassifySchema.parse(payload);
}
