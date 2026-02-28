import { z } from "zod";

export const choiceSchema = z
  .object({
    number: z.number().nullable().optional(),
    content: z.string().nullable().optional(),
    image: z.string().nullable().optional(),
    imageUrl: z.string().nullable().optional(),
  })
  .passthrough();

export type PracticeChoice = z.infer<typeof choiceSchema>;

export const examOptionSchema = z
  .object({
    id: z.number(),
    title: z.string(),
  })
  .passthrough();

export const questionSchema = z
  .object({
    questionId: z.union([z.number(), z.string()]),
    questionNumber: z.number().nullable().optional(),
    stem: z.string().nullable().optional(),
    choices: z.array(choiceSchema).optional(),
    isShortAnswer: z.boolean().optional(),
    isMultipleResponse: z.boolean().optional(),
    examId: z.number().nullable().optional(),
    examTitle: z.string().nullable().optional(),
    image: z.string().nullable().optional(),
    imageUrl: z.string().nullable().optional(),
    originalImageUrl: z.string().nullable().optional(),
  })
  .passthrough();

export type PracticeQuestion = z.infer<typeof questionSchema> & {
  questionId: number | string;
};

export const lectureDetailSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).nullable().optional(),
    title: z.string().nullable().optional(),
    questions: z.array(questionSchema).optional(),
    totalCount: z.number().optional(),
    objectiveCount: z.number().optional(),
    subjectiveCount: z.number().optional(),
    multipleResponseCount: z.number().optional(),
    examOptions: z.array(examOptionSchema).optional(),
    selectedExamIds: z.array(z.number()).nullable().optional(),
    filterActive: z.boolean().nullable().optional(),
  })
  .passthrough();

export const lectureQuestionsResponseSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).nullable().optional(),
    title: z.string().nullable().optional(),
    examIds: z.array(z.number()).nullable().optional(),
    total: z.number().optional(),
    offset: z.number().optional(),
    limit: z.number().optional(),
    questions: z.array(questionSchema).optional(),
  })
  .passthrough();

export const lectureResultSchema = z
  .object({
    lectureId: z.union([z.number(), z.string()]).nullable().optional(),
    examIds: z.array(z.number()).nullable().optional(),
    title: z.string().nullable().optional(),
    total: z.number().optional(),
    offset: z.number().optional(),
    limit: z.number().optional(),
    questions: z
      .array(
        questionSchema.extend({
          explanation: z.string().nullable().optional(),
          correctChoiceNumbers: z.array(z.number()).optional(),
          correctAnswerText: z.string().nullable().optional(),
        })
      )
      .optional(),
  })
  .passthrough();

export const sessionDetailSchema = z
  .object({
    sessionId: z.union([z.number(), z.string()]).optional(),
    lectureId: z.union([z.number(), z.string()]).nullable().optional(),
    lectureTitle: z.string().nullable().optional(),
    examIds: z.array(z.number()).nullable().optional(),
    examTitle: z.string().nullable().optional(),
    mode: z.string().nullable().optional(),
    questionOrder: z.array(z.number()).nullable().optional(),
    totalQuestions: z.number().optional(),
    currentQuestionIndex: z.number().nullable().optional(),
    finishedAt: z.string().nullable().optional(),
    items: z
      .array(
        z
          .object({
            questionId: z.number(),
            answer: z.any().nullable().optional(),
            isAnswered: z.boolean().optional(),
          })
          .passthrough()
      )
      .nullable()
      .optional(),
  })
  .passthrough();

export type AnswerPayload =
  | {
    type: "mcq";
    value: number[];
  }
  | {
    type: "short";
    value: string;
  };

export const submitResponseSchema = z
  .object({
    sessionId: z.union([z.number(), z.string()]).optional(),
    lectureId: z.union([z.number(), z.string()]).nullable().optional(),
    examIds: z.array(z.number()).nullable().optional(),
    examTitle: z.string().nullable().optional(),
    submittedAt: z.string().nullable().optional(),
    summary: z
      .object({
        all: z
          .object({
            total: z.number().optional(),
            answered: z.number().optional(),
            correct: z.number().optional(),
          })
          .partial()
          .optional(),
      })
      .partial()
      .optional(),
    items: z.array(z.any()).optional(),
  })
  .passthrough();
