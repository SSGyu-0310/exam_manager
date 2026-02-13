# 문제→강의 분류 파이프라인 업그레이드 리포트 (2026-02-10)

## 1) 분석 리포트(.md)

### 1-1. 현재 파이프라인 흐름(모듈/함수 단위)

```text
[API] app/routes/ai.py:start_classification
  -> AsyncBatchProcessor.start_classification_job()
  -> AsyncBatchProcessor._process_job()
    -> LectureRetriever.find_candidates()
      -> retrieval.search_chunks_bm25() or retrieval.search_chunks_hybrid_rrf()
      -> retrieval.aggregate_candidates() / aggregate_candidates_rrf()
    -> (optional) context_expander.expand_candidates()
    -> GeminiClassifier.classify_single()
      -> _build_classification_prompt()
      -> LLM call + JSON parse/fallback parse
      -> _normalize_evidence()
    -> ClassificationJob.result_json(preview 저장)

[API] app/routes/ai.py:apply_classification
  -> apply_classification_results()
    -> 후보 밖 lecture_id 제약 처리(out-of-candidate)
    -> ai_suggested/ai_final 필드 저장
    -> QuestionChunkMatch evidence 저장(페이지/인용 검증 반영)
    -> 조건 충족 시 question.lecture_id 자동 반영
```

### 1-2. 후보 Top-K 생성 지점/검색 SQL 호출 지점

- 엔트리: `app/services/ai_classifier.py:262` `LectureRetriever.find_candidates`
- BM25 검색: `app/services/retrieval.py:301` `search_chunks_bm25`
- Legacy BM25 SQL path: `app/services/retrieval.py:404` (legacy helper)
- Postgres FTS SQL: `app/services/retrieval.py:439` `_search_chunks_bm25_postgres`
- Postgres trigram fallback SQL: `app/services/retrieval.py:480` `_search_chunks_trgm_postgres`
- 후보 집계: `app/services/retrieval.py:857` `aggregate_candidates`
- RRF 후보 집계: `app/services/retrieval.py:934` `aggregate_candidates_rrf`

### 1-3. Candidate Lectures 포맷/후처리 추적

- 검색 결과 chunk 포맷:
  - `chunk_id`, `lecture_id`, `page_start`, `page_end`, `snippet`, `bm25_score|rrf_score|embedding_score`
- 후보 강의 포맷:
  - `id`, `title`, `block_name`, `full_path`, `score`, `evidence[]`
  - evidence 항목: `page_start`, `page_end`, `snippet`, `chunk_id`
- LLM 출력 후처리:
  - 후보 ID 제한: `app/services/ai_classifier.py:622`
  - evidence 정규화/필터: `app/services/ai_classifier.py:430`
  - 근거 불충분 시 강제 `no_match`: `app/services/ai_classifier.py:649`
  - DB 반영 시 page_span 재검증: `app/services/ai_classifier.py:975`, `app/services/ai_classifier.py:1083`

### 1-4. 구조적 취약점(원인/영향/우선순위)

- P0: Docker 런타임 불가 시 운영 검증 공백
  - 원인: 현재 WSL에서 Docker Desktop daemon 연결 불가(`dockerDesktopLinuxEngine` 파이프 미존재).
  - 영향: 컨테이너 기동/헬스체크/실DB 검증 미완료 상태로 배포 위험.
- P0: 멀티워커 시작 시 스키마 패치 레이스
  - 원인: Gunicorn 워커가 동시에 `ALTER TABLE questions ADD COLUMN ai_final_lecture_id` 실행.
  - 영향: `DuplicateColumn`으로 워커 부팅 실패 가능.
  - 조치: `app/services/schema_patch.py`에 duplicate-column 예외 무시 + rollback 처리 반영 완료.
- P0: 후보 밖 lecture_id 환각
  - 원인: LLM이 candidate 외 ID 생성 가능.
  - 영향: 잘못된 자동 반영/데이터 오염.
  - 조치: 후보 ID 화이트리스트 강제 + apply 단계 재검증 반영 완료.
- P0: evidence quote/page 환각
  - 원인: 비정합 quote/page를 그대로 저장하면 근거 신뢰성 붕괴.
  - 영향: 디버깅 불가/검토 품질 저하.
  - 조치: verbatim/page_span 강제 플래그와 저장단 필터 반영 완료.
- P1: 검색 백엔드/점수 체계 혼선
  - 원인: legacy BM25(작을수록 좋음)와 Postgres rank(클수록 좋음) 방향 차이.
  - 영향: 후보 집계 순위 왜곡 가능.
  - 조치: `_chunk_relevance` 기준으로 점수 방향 통일 반영 완료.
- P1: Postgres query mode 미통일
  - 원인: FTS 쿼리 생성 방식이 코드 경로별로 분산될 때 불일치 가능.
  - 영향: 검색 재현성 저하.
  - 조치: `postgres_tsquery_expression()`로 통일 반영 완료.

### 1-5. Postgres 전환 설계 요약(스키마/인덱스/쿼리/플래그)

- 스키마:
  - `lecture_chunks.content_tsv tsvector` 추가
  - `lecture_chunks_tsv_update()` trigger 함수 + `lecture_chunks_tsv_trigger`
- 인덱스:
  - `GIN(content_tsv)` 기본
  - 선택: `pg_trgm` + `GIN(content gin_trgm_ops)` fallback
- 쿼리:
  - 기본: `websearch_to_tsquery('simple', :query)` + `ts_rank_cd`
  - 운영 이유:
    - 사용자 입력(띄어쓰기/따옴표/연산자)에 상대적으로 관대
    - `to_tsquery`보다 파싱 실패 위험 낮음
  - 선택 모드:
    - `SEARCH_PG_QUERY_MODE=plainto|to_tsquery` 지원
- 플래그:
  - `SEARCH_BACKEND=postgres|auto` (현재 legacy 플래그는 비권장/미지원)
  - `SEARCH_PG_QUERY_MODE=websearch|plainto|to_tsquery`
  - `SEARCH_PG_TRGM_ENABLED=0|1`
  - `CLASSIFIER_REQUIRE_VERBATIM_QUOTE=0|1`
  - `CLASSIFIER_REQUIRE_PAGE_SPAN=0|1`
  - `CLASSIFIER_ALLOW_ID_FROM_TEXT=0|1`

## 2) 변경 계획 체크리스트

### 2-1. 수정/추가 파일 목록

- 검색/분류 코어:
  - `app/services/retrieval.py`
  - `app/services/ai_classifier.py`
  - `app/services/context_expander.py`
- 설정:
  - `config/base.py`
  - `config/schema.py`
  - `config/experiment.py`
  - `config.py`
- 스키마/마이그레이션:
  - `migrations/postgres/20260210_1600_search_fts.sql`
  - `migrations/postgres/20260210_1600_search_fts_down.sql`
  - `scripts/migrate_ai_fields.py`
  - `app/services/schema_patch.py`
  - `app/models.py`
  - `app/__init__.py`
- 도커/문서:
  - `.env.example`
  - `.env.docker.example`
  - `.env.docker`
  - `docker-compose.yml`
  - `docker-compose.dev.yml`
  - `scripts/dc`
  - `docs/setup/docker.md`
  - `docs/setup/env.md`
  - `docs/setup/config-reference.md`
- 테스트:
  - `tests/test_retrieval_candidate_aggregation.py`
  - `tests/test_classifier_postprocess.py`

### 2-2. 필요한 환경변수(.env/.env.docker)

- `RETRIEVAL_MODE=bm25`
- `SEARCH_BACKEND=postgres`
- `SEARCH_PG_QUERY_MODE=websearch`
- `SEARCH_PG_TRGM_ENABLED=0`
- `SEARCH_PG_TRGM_MIN_SIMILARITY=0.2`
- `SEARCH_PG_TRGM_TOP_N=40`
- `CLASSIFIER_ALLOW_ID_FROM_TEXT=0`
- `CLASSIFIER_REQUIRE_VERBATIM_QUOTE=1`
- `CLASSIFIER_REQUIRE_PAGE_SPAN=1`

### 2-3. 마이그레이션 순서 및 롤백

- 적용 순서:
  1. 앱 스키마 보강: `python scripts/migrate_ai_fields.py --config production --db "$DATABASE_URL"`
  2. Postgres FTS 마이그레이션: `psql "$DATABASE_URL" -f migrations/postgres/20260210_1600_search_fts.sql`
  3. 점검: `python scripts/verify_postgres_setup.py --db "$DATABASE_URL"`
- 롤백 순서:
  1. FTS 롤백: `psql "$DATABASE_URL" -f migrations/postgres/20260210_1600_search_fts_down.sql`
  2. 검색 백엔드 플래그 복구: `SEARCH_BACKEND=auto`, `RETRIEVAL_MODE=bm25`
  3. 앱 재기동 후 smoke test

## 3) 핵심 SQL(인덱스/트리거/쿼리) 초안

### 3-1. 인덱스/트리거

```sql
ALTER TABLE lecture_chunks
ADD COLUMN IF NOT EXISTS content_tsv tsvector;

CREATE OR REPLACE FUNCTION lecture_chunks_tsv_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.content_tsv := to_tsvector('simple', coalesce(NEW.content, ''));
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lecture_chunks_tsv_trigger ON lecture_chunks;
CREATE TRIGGER lecture_chunks_tsv_trigger
BEFORE INSERT OR UPDATE OF content
ON lecture_chunks
FOR EACH ROW EXECUTE FUNCTION lecture_chunks_tsv_update();

CREATE INDEX IF NOT EXISTS idx_lecture_chunks_content_tsv
ON lecture_chunks USING GIN (content_tsv);
```

### 3-2. 선택: pg_trgm

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_lecture_chunks_content_trgm
ON lecture_chunks USING GIN (content gin_trgm_ops);
```

### 3-3. FTS 검색 쿼리 기본형

```sql
SELECT
  c.id AS chunk_id,
  c.lecture_id,
  c.page_start,
  c.page_end,
  ts_headline(
    'simple',
    c.content,
    websearch_to_tsquery('simple', :query),
    'MaxFragments=1, MaxWords=24, MinWords=8, ShortWord=2'
  ) AS snippet,
  ts_rank_cd(c.content_tsv, websearch_to_tsquery('simple', :query)) AS bm25_score
FROM lecture_chunks c
WHERE c.content_tsv @@ websearch_to_tsquery('simple', :query)
ORDER BY bm25_score DESC
LIMIT :top_n;
```

## 4) 파일별 수정 가이드(함수 단위)

- `app/services/retrieval.py`
  - `_resolve_search_backend`, `use_postgres_search_backend` 추가.
  - `postgres_tsquery_expression` 추가.
  - `search_chunks_bm25`에 Postgres/legacy 스위칭 + trigram fallback.
  - `aggregate_candidates_rrf` 구현 및 점수 정규화.
- `app/services/context_expander.py`
  - Postgres 여부 판단을 `retrieval.use_postgres_search_backend()`로 통일.
  - tsquery 표현식도 retrieval 공용 함수로 통일.
- `app/services/ai_classifier.py`
  - 프롬프트에서 후보 ID 제한/근거 규칙 강화.
  - `_normalize_evidence`에서 verbatim/page_span 검증 강화.
  - 후보 밖 lecture_id 또는 근거 불충분 시 `no_match` 강제.
  - 적용 단계에서 evidence 저장 전 page_span 재검증.
- `config/*`
  - 검색/분류 하드닝 관련 env 스키마 추가.
  - 기본 retrieval 모드를 `bm25`로 변경.
- `migrations/postgres/20260210_1600_search_fts.sql`
  - FTS 컬럼/트리거/인덱스/pg_trgm 인덱스 정의.
- `scripts/dc`
  - WSL에서 `docker` 미탐지 시 `docker.exe` 경로 fallback 추가.

## 5) 테스트/검증 플랜 및 실행 결과

### 5-1. 최소 단위 테스트

- 검색 후보 구조 검증:
  - `tests/test_retrieval_candidate_aggregation.py`
  - lecture_id/chunk_id/page/snippet 보존 및 랭킹 확인

### 5-2. 회귀 테스트

- 후보 밖 lecture_id 금지:
  - `tests/test_classifier_postprocess.py::test_classify_single_rejects_out_of_candidate_lecture_id`
- JSON 파싱 실패 안전처리:
  - `tests/test_classifier_postprocess.py::test_classify_single_invalid_json_falls_back_to_no_match`
- quote 환각 방지:
  - `tests/test_classifier_postprocess.py::test_classify_single_forces_no_match_when_quote_not_verbatim`

### 5-3. 운영 지표(권장)

- `Top-K recall@K`: 오프라인 정답셋 기준, 후보 Top-K 내 정답 lecture 포함 비율
- `Auto-apply precision proxy`: 자동 반영 건 중 사후 수동 거절 비율 역지표
- `No-match rate`: 전체 중 `no_match=true` 비율(급증 시 검색 recall 저하 의심)
- `Out-of-candidate rejection rate`: 후보 밖 출력 차단 비율(프롬프트/모델 불안정 지표)

### 5-4. 현재 실행 검증 결과

- 코드 컴파일: `python3 -m py_compile ...` 통과
- 테스트: `tests/test_retrieval_candidate_aggregation.py`, `tests/test_classifier_postprocess.py` 통과(`5 passed`)
- Docker compose 정적 검증: `docker compose -f docker-compose.yml config` 통과
- Docker 런타임 검증:
  - 2026-02-10 1차 시도: Docker daemon 미기동으로 실패
  - 2026-02-10 2차 시도: Docker Desktop 기동 후 `scripts/dc up -d --build` 성공
  - 상태: `db`, `api`, `web` 모두 `healthy`
  - `api` 내부 헬스 체크: `GET /health` 정상 응답
  - Postgres 검증: `python scripts/verify_postgres_setup.py --db "$DATABASE_URL"` 모든 항목 `OK`
