# Architecture Map - Route to Feature

현재 코드 기준으로 Next 페이지/Flask 라우트/API를 기능 단위로 매핑한 문서입니다.

## 1) Frontend Route Map (Next.js)

| Route | 주요 기능 | 연동 API |
| --- | --- | --- |
| `/login`, `/register` | 인증 | `/api/auth/*` |
| `/dashboard` | 학습 대시보드 | `/api/dashboard/stats`, `/api/dashboard/progress`, `/api/dashboard/bookmarks` |
| `/dashboard/activity` | 최근 활동 상세 | `/api/review/history` |
| `/learn/practice` | 강의 선택형 연습 진입 | `/api/practice/lectures` |
| `/practice/start` | 연습 시작(모드/시험 필터) | `/api/practice/lecture/<id>` |
| `/practice/session/[sessionId]` | 문제 풀이/제출 | `/api/practice/lecture/<id>/questions`, `/api/practice/exam/<id>/questions`, `/api/practice/*/submit` |
| `/practice/session/[sessionId]/result` | 결과 상세 | `/api/practice/lecture/<id>/result`, `/api/practice/exam/<id>/result` |
| `/review/notes` | 복습 노트/오답 | `/api/review/notes` |
| `/review/weakness` | 약점 분석 | `/api/review/weakness` |
| `/review/history` | 세션 이력 | `/api/review/history` |
| `/manage` | 커리큘럼 관리(Subject/Block/Lecture) | `/api/manage/subjects`, `/api/manage/blocks`, `/api/manage/lectures` |
| `/manage/exams` | 시험 목록 + PDF 업로드 | `/api/manage/exams`, `/api/manage/upload-pdf` |
| `/exam/[id]` | 시험 상세/문항 목록 | `/api/manage/exams/<id>` |
| `/manage/questions/[id]/edit` | 문제 상세 수정 | `/api/manage/questions/<id>` |
| `/manage/classifications`, `/exam/unclassified` | 미분류 큐/대량 작업/AI 분류 | `/api/exam/unclassified`, `/exam/questions/bulk-classify`, `/manage/questions/move`, `/manage/questions/reset`, `/ai/classify/*` |
| `/manage/classifications/[jobId]` | AI 분류 결과 미리보기 | `/ai/classify/result/<job_id>`, `/ai/classify/diagnostics/<job_id>` |
| `/manage/settings` | 사용자/시스템 설정 보기 | `/api/dashboard/config`, `/api/auth/logout` |
| `/templates`, `/templates/[id]` | 공개 커리큘럼 템플릿 조회/복제 | `/api/public/curriculums*` |

모든 서버 호출은 Next proxy (`next_app/src/app/api/proxy/[...path]/route.ts`)를 통해 Flask로 전달됩니다.

## 2) Backend Blueprint Map (Flask)

| Blueprint file | Prefix | 역할 |
| --- | --- | --- |
| `app/routes/main.py` | `/` | 랜딩/헬스체크 |
| `app/routes/api_auth.py` | `/api/auth` | 인증(회원가입/로그인/로그아웃/me) |
| `app/routes/api_manage.py` | `/api/manage` | 관리 API (커리큘럼/시험/문항/업로드) |
| `app/routes/api_exam.py` | `/api/exam` | 미분류 큐 API |
| `app/routes/ai.py` | `/ai` | AI 분류 배치/진단/적용, 텍스트 교정 |
| `app/routes/api_practice.py` | `/api/practice` | 연습 문제/제출/결과/세션 조회 |
| `app/routes/api_dashboard.py` | none (absolute route) | 대시보드/복습 지표 API |
| `app/routes/api_questions.py` | `/api/questions` | 문제 증거(evidence) 조회 |
| `app/routes/api_public_curriculum.py` | `/api/public/curriculums` | 공개 템플릿 조회/복제 |
| `app/routes/api_admin_curriculum.py` | `/api/admin/public/curriculums` | 공개 템플릿 관리자 API |
| `app/routes/manage.py` | `/manage` | Legacy 관리 UI + 일부 JSON 엔드포인트 |
| `app/routes/exam.py` | `/exam` | Legacy 시험 UI + bulk classify JSON |
| `app/routes/practice.py` | `/practice` | Legacy 연습 UI |

## 3) Core Data Flows

### PDF 업로드 -> 시험/문항 생성

1. Next `/manage/exams`에서 PDF 업로드
2. `POST /api/manage/upload-pdf`
3. 파싱/크롭/저장 서비스 실행
   - `pdf_parser_factory`
   - `pdf_cropper`
   - `pdf_import_service.save_parsed_questions`
4. `PreviousExam`, `Question`, `Choice` 저장

### 미분류 큐 -> 수동/AI 분류

1. 큐 조회: `GET /api/exam/unclassified`
2. 수동 작업
   - 대량 분류: `POST /exam/questions/bulk-classify`
   - 대량 이동: `POST /manage/questions/move`
   - 초기화: `POST /manage/questions/reset`
3. AI 작업
   - 시작: `POST /ai/classify/start`
   - 상태/결과: `GET /ai/classify/status/<id>`, `GET /ai/classify/result/<id>`
   - 적용: `POST /ai/classify/apply`

### 연습 -> 제출 -> 결과

1. 강의/시험 문제 조회
   - `GET /api/practice/lecture/<id>/questions`
   - `GET /api/practice/exam/<id>/questions`
2. 제출
   - `POST /api/practice/lecture/<id>/submit`
   - `POST /api/practice/exam/<id>/submit`
3. 결과
   - `GET /api/practice/lecture/<id>/result`
   - `GET /api/practice/exam/<id>/result`

## 4) Known Partial Areas

- Next 연습 시작 시 서버 세션 생성 엔드포인트가 불완전해서 클라이언트 fallback 세션을 병행 사용합니다.
- 일부 페이지(`/learn/recommended` 등)는 준비 상태 UI를 제공합니다.
- Legacy Flask UI는 여전히 유효하며 Next UI와 함께 운용됩니다.
