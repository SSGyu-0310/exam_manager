# Ontology (Domain + Media + File Semantics)

이 문서는 이 프로젝트에서 용어 혼선을 줄이기 위한 공통 온톨로지입니다.

- Last updated: 2026-03-02
- Scope: 도메인 모델, 파일/이미지 타입, API 필드 의미, 고아 파일 정의

## 1) Core Domain Entities

| 계층 | 표준 용어(한국어) | 코드 엔티티 | 기본 식별자 | 핵심 관계 |
| --- | --- | --- | --- | --- |
| 사용자 | 사용자 | `User` | `users.id` | 데이터 소유 범위 기준 |
| 커리큘럼 | 과목 | `Subject` | `subjects.id` | `Subject -> Block` |
| 커리큘럼 | 블럭 | `Block` | `blocks.id` | `Block -> Lecture`, `Block -> BlockFolder` |
| 커리큘럼 | 블럭 폴더 | `BlockFolder` | `block_folders.id` | 트리 구조(부모/자식), `BlockFolder -> Lecture` |
| 커리큘럼 | 강의 | `Lecture` | `lectures.id` | `Lecture -> Question(분류)`, `Lecture -> LectureMaterial`, `Lecture -> LectureChunk` |
| 강의자료 | 강의자료 메타 | `LectureMaterial` | `lecture_materials.id` | 업로드 PDF 메타, `LectureMaterial -> LectureChunk` |
| 강의자료 | 강의 청크 | `LectureChunk` | `lecture_chunks.id` | 검색/분류 근거 텍스트 단위 |
| 시험 | 시험지 | `PreviousExam` | `previous_exams.id` | `PreviousExam -> Question` |
| 시험 | 문제 | `Question` | `questions.id` | `Question -> Choice`, `Question -> Lecture(선택적)` |
| 시험 | 선택지 | `Choice` | `choices.id` | 문제의 보기/선지 |
| 분류 근거 | 문제-청크 매칭 | `QuestionChunkMatch` | `question_chunk_matches.id` | 문제와 강의 청크의 근거 연결 |
| 학습 | 연습 세션 | `PracticeSession` | `practice_sessions.id` | `PracticeSession -> PracticeAnswer` |
| 학습 | 연습 답안 | `PracticeAnswer` | `practice_answers.id` | 세션 내 문항별 제출 결과 |
| 운영 | 공개 템플릿 | `PublicCurriculumTemplate` | `public_curriculum_templates.id` | 블럭/강의 payload 복제용 |

## 2) Relationship Graph

```text
User
├─ Subject
│  └─ Block
│     ├─ BlockFolder (optional tree)
│     │  └─ Lecture (optional)
│     └─ Lecture
│        ├─ LectureMaterial (PDF metadata)
│        └─ LectureChunk (indexed text)
└─ PreviousExam
   └─ Question
      ├─ Choice
      ├─ lecture_id -> Lecture (classification link)
      └─ QuestionChunkMatch (optional evidence)
```

## 3) Media/File Ontology

### 3.1 파일 타입 정의

| 표준 타입 ID | 표준 용어(권장) | 저장 위치(상대 경로) | 참조 방식 | 기본 보존 정책 |
| --- | --- | --- | --- | --- |
| `lecture_source_pdf` | 강의 원본 PDF | `lecture_notes/<lecture_id>/<filename>.pdf` | `lecture_materials.file_path` | 기본 삭제(`KEEP_PDF_AFTER_INDEX=false`) |
| `lecture_chunk_text` | 강의 청크 텍스트 | DB row(`lecture_chunks`) | `lecture_chunks.content` | DB 보존 |
| `question_crop_image` | 문항 원문 크롭 이미지 | `exam_crops/exam_<exam_id>/Q##_merged.png` 등 | 런타임 탐색(`exam_id`, `question_number`) | 파일 보존(자동 삭제 없음) |
| `question_attached_image` | 문항 첨부 이미지 | `uploads/<filename>` 또는 `uploads/<subpath>` | `questions.image_path` | 파일 보존 |
| `choice_attached_image` | 선지 첨부 이미지 | `uploads/<filename>` 또는 `uploads/<subpath>` | `choices.image_path` | 파일 보존 |
| `inline_markdown_image` | 본문 마크다운 이미지 | 주로 `uploads/<filename>` | 마크다운/정규화 후 `question.image_path`와 연동 가능 | 파일 보존 |

### 3.2 UI/API에서 보이는 이미지 필드 의미

| 필드명 | 의미 | 주 용도 |
| --- | --- | --- |
| `imagePath` | DB에 저장된 원시 경로(`questions.image_path`) | 관리 화면 편집/조회 |
| `imageUrl` | 문제/선지 첨부 이미지를 브라우저 렌더 가능한 URL로 변환한 값 | 풀이 화면 표시 |
| `originalImageUrl` | 문항 원문 크롭 이미지 URL(동적 탐색 결과) | 원문 보기/대조 |

핵심 규칙:

- `Question.image_path`가 `exam_crops/...`가 아니면 일반적으로 `imageUrl`로 노출
- 크롭 원문 이미지는 `find_question_crop_image(exam_id, question_number)`로 동적 탐색
- 강의자료 PDF는 메타(`lecture_materials`)는 남아도 파일은 삭제될 수 있음

## 4) “고아 파일” 정의 (분석/청소 용어)

### 4.1 Strict Orphan (DB 기준)

다음 컬럼 어디에서도 참조되지 않는 파일:

- `questions.image_path`
- `choices.image_path`
- `lecture_materials.file_path`

주의: 이 기준만 쓰면 `question_crop_image`(동적 탐색 참조)를 고아로 오판할 수 있음.

### 4.2 Effective Orphan (런타임 기준, 권장)

아래 참조를 모두 반영한 뒤에도 사용되지 않는 파일:

- DB 직접 참조(`questions/choices/lecture_materials`)
- 동적 크롭 참조(`exam_id + question_number -> find_question_crop_image`)

정리 작업은 반드시 Effective 기준으로 실행.

## 5) 대화용 표준 용어 (앞으로 이 표현 권장)

| 대화 표현(짧게) | 온톨로지 타입 |
| --- | --- |
| 강의 원본 PDF | `lecture_source_pdf` |
| 강의 청크 | `lecture_chunk_text` |
| 문항 원문 크롭 | `question_crop_image` |
| 문항 첨부 이미지 | `question_attached_image` |
| 선지 첨부 이미지 | `choice_attached_image` |
| 본문 마크다운 이미지 | `inline_markdown_image` |

예시:

- “문항 첨부 이미지 용량만 계산해줘” = `question_attached_image`만 집계
- “크롭 포함 실사용 파일” = `question_crop_image + question_attached_image + choice_attached_image`
- “강의자료는 청킹만 남기고 싶어” = `lecture_source_pdf` 삭제, `lecture_chunk_text` 유지

## 6) Export/Import 설계 시 최소 단위 (참고)

동일 상태 재현을 목표로 하면 번들에 아래를 포함:

- 구조 데이터: `Subject`, `Block`, `BlockFolder`, `Lecture`
- 문제 데이터: `PreviousExam`, `Question`, `Choice`, 분류 링크(`question.lecture_id`)
- 근거 데이터(선택): `QuestionChunkMatch`
- 파일 데이터: `question_attached_image`, `choice_attached_image`, `question_crop_image`
- 강의자료 원본 PDF(`lecture_source_pdf`)는 정책 선택:
  - 재청킹 가능 환경이면 제외 가능
  - 원본 재현이 필요하면 포함

---

문서 목적은 “같은 단어로 같은 대상을 가리키기”입니다.  
새 타입/필드가 추가되면 이 문서를 먼저 갱신합니다.
