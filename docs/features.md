# Current Feature Snapshot

이 문서는 현재 코드베이스에 실제로 구현된 기능만 요약합니다.

## Feature Matrix

| 영역 | 상태 | 구현 내용 | 주요 코드 |
| --- | --- | --- | --- |
| 인증 | Implemented | 회원가입/로그인/로그아웃/내 정보 조회, JWT 쿠키 인증 | `app/routes/api_auth.py`, `next_app/src/context/AuthContext.tsx` |
| 커리큘럼 관리 | Implemented | Subject/Block/Lecture CRUD, 공개/개인 스코프, 정렬/수정 | `app/routes/api_manage.py`, `next_app/src/components/manage/CurriculumManager.tsx` |
| 강의 자료 인덱싱 | Implemented | 강의노트 PDF 업로드, 청크 인덱싱, 상태 조회 | `app/routes/api_manage.py`, `app/services/lecture_indexer.py` |
| 시험지/문항 관리 | Implemented | 시험 CRUD, PDF 업로드 파싱, 문항/선지 편집 | `app/routes/api_manage.py`, `app/services/pdf_*` |
| 미분류 큐/수동 분류 | Implemented | 미분류 조회, 필터, 일괄 분류/이동/초기화 | `app/routes/api_exam.py`, `app/routes/exam.py`, `app/routes/manage.py` |
| AI 분류 배치 | Implemented | 분류 작업 start/status/cancel/result/apply/diagnostics/recent | `app/routes/ai.py`, `app/services/ai_classifier.py` |
| 문제 근거(evidence) | Implemented | 문제별 매칭 근거 조회 | `app/routes/api_questions.py` |
| 연습/채점 | Implemented | 강의/시험 문제 조회, 제출, 채점 결과, 세션 조회 | `app/routes/api_practice.py`, `app/services/practice_service.py` |
| 대시보드/복습 | Implemented | 진행도, 약점 분석, 노트, 히스토리 | `app/routes/api_dashboard.py`, `next_app/src/app/review/*` |
| 공개 커리큘럼 템플릿 | Implemented | 템플릿 조회/상세/복제, 관리자 템플릿 관리 | `app/routes/api_public_curriculum.py`, `app/routes/api_admin_curriculum.py` |
| Legacy UI | Implemented | Flask 템플릿 기반 관리/시험/연습 화면 유지 | `app/routes/manage.py`, `app/routes/exam.py`, `app/routes/practice.py` |
| 추천 학습 페이지 | Partial | 화면 뼈대는 있으나 실제 추천 로직은 준비 중 | `next_app/src/app/learn/recommended/page.tsx` |
| Next 세션 시작 API | Partial | 일부 경로에서 fallback(sessionStorage) 사용 | `next_app/src/app/practice/start/page.tsx` |

## User Flow Summary

1. 사용자 등록/로그인
2. 커리큘럼(과목/블록/강의) 구성
3. 시험 PDF 업로드로 문항 생성
4. 미분류 큐에서 수동 또는 AI로 강의 분류
5. 연습 모드에서 풀이/제출/결과 확인
6. 대시보드와 복습 탭에서 약점/이력 점검

## Non-Goals in Current Scope

- 완전한 추천 학습 엔진
- Next 단독 세션 생성 흐름의 완성
- Legacy UI 제거
