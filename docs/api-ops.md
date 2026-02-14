# API for Operations

운영/장애 대응 관점에서 자주 쓰는 API 점검 포인트입니다.

## 1) 기본 생존 확인

```bash
curl -sS http://localhost:5000/health
curl -sS http://localhost:5000/api/exam/health
```

확인 항목
- HTTP 200 여부
- 응답 JSON의 상태 필드

## 2) 인증 상태 확인

로그인 쿠키가 있는 상태에서 사용자 확인:

```bash
curl -sS http://localhost:5000/api/auth/me
```

401이 반복되면
- JWT/SECRET 설정
- 쿠키 전달 경로
- `JWT_COOKIE_SECURE`(HTTP 환경에서 0인지) 를 확인합니다.

## 3) 미분류 큐/분류 파이프라인 확인

### 큐 확인

```bash
curl -sS "http://localhost:5000/api/exam/unclassified?status=unclassified&limit=20"
```

### AI 분류 작업 상태

```bash
curl -sS "http://localhost:5000/ai/classify/recent"
curl -sS "http://localhost:5000/ai/classify/status/<JOB_ID>"
curl -sS "http://localhost:5000/ai/classify/result/<JOB_ID>"
curl -sS "http://localhost:5000/ai/classify/diagnostics/<JOB_ID>?include_rows=1&row_limit=100"
```

로그 확인(도커):

```bash
./scripts/dc logs -f api
```

필요 시 `CLASSIFIER_DEBUG_LOG=1`로 상세 로깅을 활성화합니다.

## 4) 대시보드/복습 API 점검

```bash
curl -sS http://localhost:5000/api/dashboard/stats
curl -sS http://localhost:5000/api/dashboard/progress
curl -sS http://localhost:5000/api/review/history
```

비정상 시 점검
- 사용자 스코프 문제
- 데이터 누락(PracticeSession/PracticeAnswer)
- DB 연결/마이그레이션 상태

## 5) 쓰기 차단/안전 모드

운영 중 위험 작업 차단이 필요하면:

- `DB_READ_ONLY=1`
- `AI_AUTO_APPLY=0`

변경 후에는 API 재기동이 필요합니다.

## 6) 관련 문서

- 운영 전체 체크리스트: `docs/ops.md`
- 스크립트 가이드: `docs/operations/scripts.md`
- 환경 변수: `docs/setup/env.md`
