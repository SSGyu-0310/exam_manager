# Architecture Map - Feature to Code Mapping

Exam Manager의 기능을 Next.js 페이지, Flask 라우트/API, 서비스/모델로 매핑한 문서입니다.

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | 구현됨 |
| ❌ | 미구현 |
| 🔄 | 파트적으로 구현됨 |

## Overview

| Frontend | Backend Routes | JSON API | Services/Models |
|-----------|----------------|------------|-----------------|
| Next.js (App Router) | Flask (Blueprint) | REST/JSON | Business Logic |

## Feature Mapping

### 1. Block Management (과목/주제 블록 CRUD)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| Block 목록 | `/manage/blocks` | `/manage` | `GET /api/manage/blocks` | - | `Block` |
| Block 생성 | `/manage/blocks/new` | `/manage` | `POST /api/manage/blocks` | - | `Block` |
| Block 수정 | `/manage/blocks/[id]/edit` | `/manage` | `PUT /api/manage/blocks/<id>` | - | `Block` |

**Files:**
- Next.js: `next_app/src/app/manage/blocks/page.tsx`, `blocks/new/page.tsx`, `blocks/[id]/edit/page.tsx`
- Components: `next_app/src/components/manage/BlocksTable.tsx`, `BlockForm.tsx`
- API: `app/routes/api_manage.py`
- Model: `app/models.py` (Block class)

---

### 2. Lecture Management (강의 관리)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 강의 목록 (블록별) | `/manage/blocks/[id]/lectures` | `/manage` | `GET /api/manage/blocks/<id>/lectures` | - | `Lecture` |
| 강의 생성 | `/manage/blocks/[id]/lectures/new` | `/manage` | `POST /api/manage/lectures` | - | `Lecture` |
| 강의 수정 | `/manage/lectures/[id]` | `/manage/lecture/<id>` | `PUT /api/manage/lectures/<id>` | - | `Lecture` |
| 강의 상세 | `/manage/lectures/[id]` | `/manage/lecture/<id>` | `GET /api/manage/lectures/<id>` | `lecture_indexer` | `Lecture`, `LectureMaterial`, `LectureChunk` |

**Files:**
- Next.js: `next_app/src/app/manage/blocks/[id]/lectures/page.tsx`, `lectures/new/page.tsx`, `manage/lectures/[id]/page.tsx`
- Components: `next_app/src/components/manage/LectureForm.tsx`
- API: `app/routes/api_manage.py`
- Services: `app/services/lecture_indexer.py` (FTS)
- Model: `app/models.py` (Lecture, LectureMaterial, LectureChunk)

---

### 3. Exam Management (기출 시험 CRUD)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 시험 목록 | `/manage/exams` | `/manage` | `GET /api/manage/exams` | - | `PreviousExam` |
| 시험 생성 | `/manage/exams/new` | `/manage` | `POST /api/manage/exams` | - | `PreviousExam` |
| 시험 수정 | `/manage/exams/[id]/edit` | - | `PUT /api/manage/exams/<id>` | - | `PreviousExam` |
| 시험 상세 | `/manage/exams/[id]` | - | `GET /api/manage/exams/<id>` | - | `PreviousExam` |

**Files:**
- Next.js: `next_app/src/app/manage/exams/page.tsx`, `exams/new/page.tsx`, `exams/[id]/edit/page.tsx`, `exams/[id]/page.tsx`
- Components: `next_app/src/components/manage/ExamsTable.tsx`, `ExamForm.tsx`
- API: `app/routes/api_manage.py`
- Model: `app/models.py` (PreviousExam)

---

### 4. PDF Upload & Parsing

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| PDF 업로드 → 문제 생성 | `/manage/upload-pdf` | - | `POST /api/manage/upload-pdf` | `pdf_parser`, `pdf_cropper`, `markdown_images` | `PreviousExam`, `Question`, `Choice` |

**Files:**
- Next.js: `next_app/src/app/manage/upload-pdf/page.tsx`
- Components: `next_app/src/components/manage/UploadPdfForm.tsx`
- API: `app/routes/api_manage.py`
- Services: `app/services/pdf_parser.py`, `app/services/pdf_cropper.py`, `app/services/markdown_images.py`
- Model: `app/models.py` (PreviousExam, Question, Choice)

---

### 5. Question Management (문제 편집)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 문제 수정 (이미지 포함) | `/manage/questions/[id]/edit` | `/manage/question/<id>/edit` | `PUT /api/manage/questions/<id>` | `markdown_images` | `Question`, `Choice` |
| 대량 분류 (move) | - | `/exam/unclassified` | `POST /manage/questions/move` | - | `Question` |
| 대량 초기화 (reset) | - | `/exam/unclassified` | `POST /manage/questions/reset` | - | `Question` |

**Files:**
- Next.js: `next_app/src/app/manage/questions/[id]/edit/page.tsx`
- Components: `next_app/src/components/manage/QuestionEditor.tsx`
- API: `app/routes/api_manage.py`, `app/routes/manage.py` (bulk)
- Service: `app/services/markdown_images.py`
- Model: `app/models.py` (Question, Choice)

---

### 6. Unclassified Queue (미분류 큐)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 미분류 문제 목록 | `/exam/unclassified` | `/exam/unclassified` | `GET /api/exam/unclassified` | - | `Question` |
| 문제 분류 (단건) | `/exam/unclassified` | `/exam/unclassified` | `POST /api/manage/questions/<id>` | - | `Question` |
| 일괄 분류/이동 | `/exam/unclassified` | `/exam/unclassified` | `POST /manage/questions/move` | - | `Question` |
| 일괄 초기화 | `/exam/unclassified` | `/exam/unclassified` | `POST /manage/questions/reset` | - | `Question` |

**Files:**
- Next.js: `next_app/src/app/exam/unclassified/page.tsx`
- Components: `next_app/src/components/exam/UnclassifiedQueue.tsx`
- Flask: `app/routes/exam.py`, `app/routes/manage.py`
- API: `app/routes/api_manage.py`, `app/routes/api_exam.py`
- Model: `app/models.py` (Question)

---

### 7. AI Classification (AI 분류)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| AI 분류 시작 | - | `/exam/unclassified` | `POST /ai/classify/start` | `ai_classifier`, `retrieval`, `context_expander` | `Question` |
| AI 분류 상태 | - | - | `GET /ai/classify/status/<id>` | - | `Question` |
| AI 분류 결과 | - | `/ai/classify/preview/<id>` | `GET /ai/classify/result/<id>` | - | `Question` |
| AI 결과 적용 | `/exam/unclassified` | - | `POST /ai/classify/apply` | - | `Question` |
| 최근 분류 작업 | - | - | `GET /ai/classify/recent` | - | `Question` |

**Files:**
- Next.js: `next_app/src/app/exam/unclassified/page.tsx`
- Flask: `app/routes/ai.py`
- API: `app/routes/ai.py`
- Services: `app/services/ai_classifier.py`, `app/services/retrieval.py`, `app/services/context_expander.py`
- Model: `app/models.py` (Question)

---

### 8. Practice Mode (연습 모드)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 연습 시작 (강의 선택) | `/practice/start` | `/practice` | `GET /api/practice/lectures` | - | `Lecture`, `Question` |
| 연습 세션 시작 | `/practice/start` | `/practice/lecture/<id>` | - | `practice_filters` | `PracticeSession`, `PracticeAnswer` |
| 연습 문제 목록 | - | `/practice/lecture/<id>` | `GET /api/practice/lecture/<id>/questions` | `practice_filters` | `Lecture`, `Question` |
| 연습 제출 | `/practice/session/[sessionId]` | `/practice/lecture/<id>` | `POST /api/practice/lecture/<id>/submit` | - | `PracticeSession`, `PracticeAnswer` |
| 연습 결과 | `/practice/session/[sessionId]/result` | `/practice/lecture/<id>` | `GET /api/practice/lecture/<id>/result` | - | `PracticeSession`, `PracticeAnswer` |
| 연습 세션 목록 | - | `/practice/sessions` | `GET /api/practice/sessions` | - | `PracticeSession` |
| 특정 세션 | - | `/practice/sessions` | `GET /api/practice/sessions/<id>` | - | `PracticeSession` |

**Files:**
- Next.js: `next_app/src/app/practice/start/page.tsx`, `practice/session/[sessionId]/page.tsx`, `practice/session/[sessionId]/result/page.tsx`, `lectures/page.tsx`
- Components: `next_app/src/components/practice/*` (StartCard, QuestionView, ResultSummary, etc.)
- Flask: `app/routes/practice.py`
- API: `app/routes/api_practice.py`
- Service: `app/services/practice_filters.py`
- Model: `app/models.py` (PracticeSession, PracticeAnswer)

---

### 9. Lecture Note Indexing (강의 노트 FTS)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 노트 업로드/인덱싱 | - | `/manage/lecture/<id>` | - | `lecture_indexer` | `LectureMaterial`, `LectureChunk` |
| FTS 검색 (내부) | - | - | - | `retrieval` | `LectureChunk` |

**Files:**
- Flask: `app/routes/manage.py` (lecture detail)
- API: N/A (internal service use)
- Services: `app/services/lecture_indexer.py`, `app/services/retrieval.py`
- Model: `app/models.py` (LectureMaterial, LectureChunk)

---

### 10. AI Text Correction (AI 텍스트 교정)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 텍스트 교정 | - | - | `POST /ai/correct-text` | `ai_classifier` | - |

**Files:**
- API: `app/routes/ai.py`
- Service: `app/services/ai_classifier.py`

---

### 11. Dashboard (대시보드)

| Description | Next.js | Flask UI | API | Service | Model |
|-------------|-----------|-----------|------|---------|--------|
| 통계/요약 | `/manage` | `/manage` | `GET /api/manage/*` (통계) | - | `Block`, `Lecture`, `PreviousExam`, `Question` |

**Files:**
- Next.js: `next_app/src/app/manage/page.tsx`
- Components: `next_app/src/components/manage/StatCard.tsx`
- Flask: `app/routes/manage.py`
- API: `app/routes/api_manage.py`
- Model: `app/models.py`

---

## File Structure Summary

### Frontend (Next.js)
```
next_app/src/
├── app/
│   ├── manage/           # 관리 화면
│   ├── exam/             # 시험/미분류 화면
│   ├── lectures/         # 연습 시작 화면
│   ├── practice/         # 연습 세션 화면
│   └── layout.tsx
└── components/
    ├── manage/           # 관리 컴포넌트
    ├── exam/             # 시험 컴포넌트
    ├── practice/         # 연습 컴포넌트
    ├── lectures/         # 연습 강의 카드
    └── ui/               # 기본 UI 컴포넌트
```

### Backend (Flask)
```
app/
├── routes/
│   ├── manage.py              # Legacy UI + bulk operations
│   ├── api_manage.py         # CRUD API (blocks/lectures/exams/questions)
│   ├── api_questions.py      # Question-specific operations
│   ├── api_exam.py          # Exam-related API
│   ├── api_practice.py      # Practice API
│   ├── exam.py              # Exam/Legacy UI
│   ├── ai.py               # AI classification
│   ├── practice.py          # Practice/Legacy UI
│   ├── parse_pdf_questions.py # CLI utility
│   └── crop.py             # PDF cropping
├── services/
│   ├── pdf_parser.py           # PDF parsing (legacy/experimental)
│   ├── pdf_cropper.py         # PDF image cropping
│   ├── markdown_images.py       # Image processing
│   ├── ai_classifier.py         # AI classification
│   ├── retrieval.py            # Search/retrieval (BM25/Semantic)
│   ├── context_expander.py      # Context expansion
│   ├── query_transformer.py     # Query transformation
│   ├── lecture_indexer.py      # FTS indexing
│   ├── practice_filters.py      # Practice filtering
│   ├── classifier_cache.py     # AI classifier caching
│   ├── embedding_utils.py      # Embedding utilities
│   └── db_guard.py            # DB read-only guard
├── models.py              # SQLAlchemy models
├── templates/             # Legacy Jinja2 templates
└── static/                # Static files (uploads)
```

## Data Flow Examples

### PDF Upload → Exam Creation
```
Next.js (upload-pdf page)
  → POST /api/manage/upload-pdf
  → pdf_parser.parse_pdf_to_questions()
  → pdf_cropper.crop_pdf_to_questions()
  → markdown_images.process_images()
  → DB: PreviousExam, Question, Choice
  → Response: exam_id
```

### AI Classification Flow
```
Flask (bulk action) or Next.js
  → POST /ai/classify/start
  → ai_classifier.start_batch()
  → retrieval.search_candidates()
  → context_expander.expand_context()
  → ai_classifier.classify_question() (Gemini API)
  → Store temporary results
  → GET /ai/classify/result/<id> (preview)
  → POST /ai/classify/apply (apply to DB)
```

### Practice Session Flow
```
Next.js (start page)
  → GET /api/practice/lectures
  → Next.js (session page)
  → POST /api/practice/lecture/<id>/submit
  → DB: PracticeSession, PracticeAnswer
  → GET /api/practice/lecture/<id>/result
```

## Missing/Incomplete Features

| Feature | Status | Notes |
|----------|--------|--------|
| Next.js 세션 생성 API | ❌ | 클라이언트 fallback 모드 사용 |
| Next.js 강의 노트 업로드 UI | ❌ | Legacy에서만 제공 |
| Next.js AI 분류 상세 미리보기 UI | ❌ | Legacy에서만 제공 |
| 로그인/인증 | ❌ | `TODO`에 명시됨 |
| 배포/CI 설정 | ❌ | `TODO`에 명시됨 |

## See Also
- [Architecture Overview](./overview.md)
- [Configuration Reference](../setup/config-reference.md)
- [Refactoring Guide](../refactoring/README.md)
