# API for Development

프론트엔드/백엔드 개발 연동 기준의 API 요약입니다.

## 1) 호출 경로

- 브라우저/SSR 모두 Next proxy 경유 호출을 기본으로 사용합니다.
- Next 내부 호출: `/api/proxy/<flask-path>`
- 실제 Flask 경로 예시: `/api/manage/exams`

## 2) 인증/세션

- 인증 API: `/api/auth/*`
- 로그인 성공 시 JWT 쿠키(`auth_token`)가 설정됩니다.
- mutation 요청은 CSRF 헤더(`X-CSRF-TOKEN`)가 필요할 수 있습니다.

## 3) 기능별 엔드포인트 맵

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Manage (커리큘럼/시험/문항)

- Subject/Block/Lecture: `/api/manage/subjects*`, `/api/manage/blocks*`, `/api/manage/lectures*`
- Exam/Question: `/api/manage/exams*`, `/api/manage/questions/<id>`
- PDF 업로드: `POST /api/manage/upload-pdf`
- 강의노트 인덱싱: `POST /api/manage/lectures/<id>/materials`

### Unclassified / Classification

- 큐 조회: `GET /api/exam/unclassified`
- 수동 일괄 분류: `POST /exam/questions/bulk-classify`
- 이동/초기화: `POST /manage/questions/move`, `POST /manage/questions/reset`
- AI 분류: `/ai/classify/start|status|result|apply|diagnostics|recent`

### Practice

- 강의/시험 문제 조회: `/api/practice/lecture/<id>/questions`, `/api/practice/exam/<id>/questions`
- 제출: `/api/practice/lecture/<id>/submit`, `/api/practice/exam/<id>/submit`
- 결과: `/api/practice/lecture/<id>/result`, `/api/practice/exam/<id>/result`
- 세션 조회: `/api/practice/sessions`, `/api/practice/sessions/<id>`

### Dashboard / Review

- `/api/dashboard/stats`
- `/api/dashboard/progress`
- `/api/dashboard/bookmarks`
- `/api/review/notes`
- `/api/review/weakness`
- `/api/review/history`
- `/api/dashboard/config`

### Public Curriculum Templates

- Public: `/api/public/curriculums*`
- Admin: `/api/admin/public/curriculums*`

## 4) 연동 시 주의사항

- 응답 포맷이 완전히 단일화되어 있지 않아 `ok/data`와 legacy 필드를 함께 방어적으로 파싱해야 합니다.
- 일부 연습 시작 흐름은 서버 세션 API 대신 client fallback(sessionStorage)을 병행합니다.
- Legacy Flask UI 라우트(`/manage`, `/exam`, `/practice`)와 JSON API가 함께 존재합니다.

## 5) 코드 위치

- Flask routes: `app/routes`
- Next API client: `next_app/src/lib/api`
- Next proxy: `next_app/src/app/api/proxy/[...path]/route.ts`
