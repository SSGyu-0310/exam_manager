/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

import { getExamDetail, getQuestionDetail, type ManageChoice } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { QuestionDetailHotkeys } from "@/components/exam/QuestionDetailHotkeys";
import { resolveImageUrl } from "@/lib/image";

type PageProps = {
  params: Promise<{ id: string }>;
};

type ContentSegment =
  | { kind: "text"; value: string }
  | { kind: "image"; alt: string; src: string };

const parseMarkdownWithImages = (value?: string | null): ContentSegment[] => {
  if (!value) return [];

  const segments: ContentSegment[] = [];
  let lastIndex = 0;
  const pattern = /!\[([^\]]*)\]\(([^)]+)\)/g;

  for (const match of value.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      segments.push({
        kind: "text",
        value: value.slice(lastIndex, index),
      });
    }

    const alt = (match[1] || "").trim();
    const src = resolveImageUrl((match[2] || "").trim());
    if (src) {
      segments.push({
        kind: "image",
        alt,
        src,
      });
    }
    lastIndex = index + match[0].length;
  }

  if (lastIndex < value.length) {
    segments.push({
      kind: "text",
      value: value.slice(lastIndex),
    });
  }

  return segments.length ? segments : [{ kind: "text", value }];
};

const typeLabel = (value: string) => {
  if (value === "multiple_choice") return "객관식";
  if (value === "multiple_response") return "복수정답";
  if (value === "short_answer") return "주관식";
  return value || "미지정";
};

const sortChoices = (choices: ManageChoice[]) => {
  return [...choices].sort((a, b) => {
    const aNumber = a.number ?? a.choiceNumber ?? 0;
    const bNumber = b.number ?? b.choiceNumber ?? 0;
    return aNumber - bNumber;
  });
};

const isCropImagePath = (value?: string | null) => {
  if (!value) return false;
  let normalized = value.trim().replace(/^\/+/, "");
  if (normalized.startsWith("static/")) {
    normalized = normalized.slice("static/".length);
  }
  if (normalized.startsWith("uploads/")) {
    normalized = normalized.slice("uploads/".length);
  }
  return normalized.startsWith("exam_crops/");
};

export default async function ManageQuestionDetailPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const question = await getQuestionDetail(id);
    const examData = await getExamDetail(question.examId);

    const orderedQuestions = [...examData.questions].sort(
      (a, b) => a.questionNumber - b.questionNumber
    );
    const currentIndex = orderedQuestions.findIndex((item) => item.id === question.id);
    const prevQuestion = currentIndex > 0 ? orderedQuestions[currentIndex - 1] : null;
    const nextQuestion =
      currentIndex >= 0 && currentIndex < orderedQuestions.length - 1
        ? orderedQuestions[currentIndex + 1]
        : null;

    const isShortAnswer = question.type === "short_answer";
    const contentSegments = parseMarkdownWithImages(question.content);
    const explanationSegments = parseMarkdownWithImages(question.explanation);
    const parsedImageCandidates: string[] = [];
    const dbParsedImageUrl = !isCropImagePath(question.imagePath)
      ? resolveImageUrl(question.imagePath)
      : null;
    if (dbParsedImageUrl) {
      parsedImageCandidates.push(dbParsedImageUrl);
    }
    contentSegments.forEach((segment) => {
      if (segment.kind === "image") {
        parsedImageCandidates.push(segment.src);
      }
    });
    const parsedImageUrls = Array.from(new Set(parsedImageCandidates));
    const originalImageUrl = resolveImageUrl(question.originalImageUrl);
    const answerText = (question.correctAnswerText || question.answer || "").trim();
    const prevHref = prevQuestion ? `/manage/questions/${prevQuestion.id}` : null;
    const nextHref = nextQuestion ? `/manage/questions/${nextQuestion.id}` : null;

    return (
      <div className="space-y-6">
        <QuestionDetailHotkeys prevHref={prevHref} nextHref={nextHref} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              문제 상세 확인
            </p>
            <h2 className="text-2xl font-semibold text-foreground">
              Q{question.questionNumber} · {question.examTitle ?? examData.exam.title}
            </h2>
            <p className="text-sm text-muted-foreground">
              {question.lectureTitle ? `분류 강의: ${question.lectureTitle}` : "미분류 문항"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/manage/exams/${question.examId}`}>시험지로</Link>
            </Button>
            <Button asChild size="sm">
              <Link href={`/manage/questions/${question.id}/edit`}>문제 수정</Link>
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="neutral">유형: {typeLabel(question.type)}</Badge>
          <Badge variant={question.lectureTitle ? "success" : "danger"}>
            {question.lectureTitle ? "분류됨" : "미분류"}
          </Badge>
          {question.examiner && <Badge variant="outline">출제자: {question.examiner}</Badge>}
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <div className="space-y-6">
            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-6">
                <h3 className="text-lg font-semibold text-foreground">파싱된 문제 이미지</h3>
                {parsedImageUrls.length ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {parsedImageUrls.map((src, index) => (
                      <img
                        key={`${question.id}-parsed-${index}`}
                        src={src}
                        alt={`Q${question.questionNumber} 파싱 이미지 ${index + 1}`}
                        className="max-h-[460px] w-full rounded-xl border border-border/60 object-contain"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
                    파싱 결과로 저장된 문제 이미지가 없습니다.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-6">
                <h3 className="text-lg font-semibold text-foreground">지문</h3>
                {contentSegments.length ? (
                  <div className="space-y-4">
                    {contentSegments.map((segment, index) =>
                      segment.kind === "text" ? (
                        segment.value.trim() ? (
                          <p
                            key={`content-${index}`}
                            className="whitespace-pre-wrap text-sm leading-7 text-foreground/90"
                          >
                            {segment.value}
                          </p>
                        ) : null
                      ) : (
                        <img
                          key={`content-image-${index}`}
                          src={segment.src}
                          alt={segment.alt || `지문 이미지 ${index + 1}`}
                          className="max-h-[460px] w-full rounded-xl border border-border/60 object-contain"
                        />
                      )
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">(이미지로만 출제된 문항)</p>
                )}
              </CardContent>
            </Card>

            {isShortAnswer ? (
              <Card className="border border-border/70 bg-card/85 shadow-soft">
                <CardContent className="space-y-3 p-6">
                  <h3 className="text-lg font-semibold text-foreground">정답</h3>
                  <div className="rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
                    {answerText || "정답 정보가 없습니다."}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="border border-border/70 bg-card/85 shadow-soft">
                <CardContent className="space-y-4 p-6">
                  <h3 className="text-lg font-semibold text-foreground">선지</h3>
                  {question.choices.length ? (
                    <div className="space-y-3">
                      {sortChoices(question.choices).map((choice, index) => {
                        const number = choice.number ?? choice.choiceNumber ?? index + 1;
                        const choiceImageUrl = resolveImageUrl(choice.imagePath);
                        return (
                          <div
                            key={`${question.id}-choice-${number}-${choice.id ?? index}`}
                            className={[
                              "space-y-3 rounded-xl border px-4 py-3 text-sm",
                              choice.isCorrect
                                ? "border-success/40 bg-success/10"
                                : "border-border/70 bg-muted/20",
                            ].join(" ")}
                          >
                            <div className="flex items-start gap-3">
                              <span className="min-w-6 font-semibold text-foreground">
                                {number}.
                              </span>
                              <div className="flex-1 whitespace-pre-wrap text-foreground/90">
                                {choice.content || "(내용 없음)"}
                              </div>
                              {choice.isCorrect && (
                                <Badge variant="success" className="shrink-0">
                                  정답
                                </Badge>
                              )}
                            </div>
                            {choiceImageUrl && (
                              <img
                                src={choiceImageUrl}
                                alt={`선지 ${number} 이미지`}
                                className="max-h-64 w-full rounded-lg border border-border/60 object-contain"
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">선지 정보가 없습니다.</p>
                  )}
                </CardContent>
              </Card>
            )}

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-6">
                <h3 className="text-lg font-semibold text-foreground">해설</h3>
                {question.explanation ? (
                  <div className="space-y-4">
                    {explanationSegments.map((segment, index) =>
                      segment.kind === "text" ? (
                        segment.value.trim() ? (
                          <p
                            key={`explanation-${index}`}
                            className="whitespace-pre-wrap text-sm leading-7 text-foreground/90"
                          >
                            {segment.value}
                          </p>
                        ) : null
                      ) : (
                        <img
                          key={`explanation-image-${index}`}
                          src={segment.src}
                          alt={segment.alt || `해설 이미지 ${index + 1}`}
                          className="max-h-[460px] w-full rounded-xl border border-border/60 object-contain"
                        />
                      )
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">등록된 해설이 없습니다.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <aside className="space-y-6">
            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-4 p-6">
                <h3 className="text-lg font-semibold text-foreground">크롭 원본 이미지</h3>
                {originalImageUrl ? (
                  <>
                    <img
                      src={originalImageUrl}
                      alt={`Q${question.questionNumber} 크롭 원본`}
                      className="max-h-[540px] w-full rounded-xl border border-border/60 object-contain"
                    />
                    <p className="text-xs text-muted-foreground">
                      파싱 결과와 원본 레이아웃을 비교해 지문/선지 분리가 올바른지 확인하세요.
                    </p>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
                    크롭된 원본 이미지가 없습니다.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border border-border/70 bg-card/85 shadow-soft">
              <CardContent className="space-y-3 p-6">
                <h3 className="text-lg font-semibold text-foreground">문항 이동</h3>
                <div className="grid gap-2">
                  {prevQuestion ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={prevHref!}>
                        ← 이전 문제 (Q{prevQuestion.questionNumber})
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      ← 이전 문제 없음
                    </Button>
                  )}
                  {nextQuestion ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={nextHref!}>
                        다음 문제 (Q{nextQuestion.questionNumber}) →
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      다음 문제 없음 →
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "문항을 불러오지 못했습니다.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">문항 정보를 불러올 수 없습니다</p>
          <p className="text-sm text-muted-foreground">{message}</p>
          <Button asChild size="sm" variant="outline">
            <Link href="/manage/exams">시험지 목록으로</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }
}
