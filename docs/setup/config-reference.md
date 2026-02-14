# Configuration Reference

Exam Manager의 환경 설정에 대한 상세 레퍼런스입니다.

## Configuration Files

| File | Purpose |
|------|---------|
| `config.py` | Flask 설정 클래스 정의 (기본값 포함) |
| `.env` | 실제 환경 변수 (프로젝트 루트, `.gitignore`) |
| `.env.example` | 템플릿 (새로 설정 시 복사해서 사용) |
| `next_app/.env.local` | Next.js 전용 설정 |

## Configuration Sections

### Core Settings

| Key | Default | Description |
|-----|---------|-------------|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask 세션/보안 키 (프로덕션에서 필수 변경) |
| `FLASK_CONFIG` | `development` | 실행 프로파일 (`development`, `production`, `local_admin`) |
| `JWT_COOKIE_SECURE` | `True` in production, else `False` | JWT 쿠키를 `Secure`로 강제 (`http://localhost`에서는 `0` 권장) |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | `720` | 액세스 토큰 만료 시간(분) |
| `JWT_REFRESH_WINDOW_MINUTES` | `30` | 만료 임박 시 자동 재발급 기준(분) |

### Database Operations

| Key | Default | Description |
|-----|---------|-------------|
| `AUTO_CREATE_DB` | `False` (`True` in Dev) | 앱 시작 시 DB 자동 생성 |
| `DB_READ_ONLY` | `False` | DB 쓰기 금지 모드 |
| `CHECK_PENDING_MIGRATIONS` | `True` | 앱 시작 시 미적용 마이그레이션 감지 |
| `FAIL_ON_PENDING_MIGRATIONS` | `False` | 프로덕션에서 미적용 마이그레이션 있으면 중단 |
| `LOCAL_ADMIN_ONLY` | `False` | 관리자 라우트 localhost만 허용 |
| `DATABASE_URL` | None (required) | Postgres 연결 URI (`postgresql+psycopg://...`) |
| `LOCAL_ADMIN_DATABASE_URL` | `DATABASE_URL` fallback | local_admin 프로파일 전용 Postgres URI |

### Backup

| Key | Default | Description |
|-----|---------|-------------|
| `AUTO_BACKUP_BEFORE_WRITE` | `False` | 레거시 플래그 (현재 in-app DB backup 미지원) |
| `AUTO_BACKUP_KEEP` | `30` | 레거시 플래그 (외부 백업 정책 사용 권장) |
| `AUTO_BACKUP_DIR` | `backups` | 레거시 플래그 (외부 백업 정책 사용 권장) |
| `ENFORCE_BACKUP_BEFORE_WRITE` | `False` | `1`이면 쓰기 차단(외부 Postgres 백업 정책 강제 목적) |

### AI Classification (Gemini)

| Key | Default | Description |
|-----|---------|-------------|
| `GEMINI_API_KEY` | None | Gemini API 키 (AI 기능 사용 시 필수) |
| `GEMINI_MODEL_NAME` | `gemini-2.0-flash-lite` | Gemini 모델명 |
| `AI_AUTO_APPLY` | `False` | AI 분류 결과 자동 적용 |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Gemini 최대 출력 토큰 |

### Classifier Cache

| Key | Default | Description |
|-----|---------|-------------|
| `CLASSIFIER_CACHE_PATH` | `data/classifier_cache.json` | 분류기 캐시 경로 (호환용, 사용 권장 x) |

### Cache & Artifacts

| Key | Default | Description |
|-----|---------|-------------|
| `DATA_CACHE_DIR` | `data/cache` | 캐시 디렉토리 경로 |
| `REPORTS_DIR` | `reports` | 리포트 디렉토리 경로 |

### Auto-Confirm V2

| Key | Default | Description |
|-----|---------|-------------|
| `AUTO_CONFIRM_V2_ENABLED` | `True` | Auto-Confirm V2 활성화 |
| `AUTO_CONFIRM_V2_DELTA` | `0.05` | 신뢰도 차이 임계값 |
| `AUTO_CONFIRM_V2_MAX_BM25_RANK` | `5` | BM25 순위 최대값 |
| `AUTO_CONFIRM_V2_DELTA_UNCERTAIN` | `0.03` | 불확실한 경우 델타 |
| `AUTO_CONFIRM_V2_MIN_CHUNK_LEN` | `200` | 최소 청크 길이 |

### Context Expansion

| Key | Default | Description |
|-----|---------|-------------|
| `PARENT_ENABLED` | `False` | Parent Context Expansion 활성화 |
| `PARENT_WINDOW_PAGES` | `1` | 상위 컨텍스트 윈도우 페이지 |
| `PARENT_MAX_CHARS` | `3500` | 상위 컨텍스트 최대 길이 |
| `PARENT_TOPK` | `5` | 상위 컨텍스트 top-k |
| `SEMANTIC_EXPANSION_ENABLED` | `True` | Semantic Expansion 활성화 |
| `SEMANTIC_EXPANSION_TOP_N` | `6` | Semantic Expansion top-N |
| `SEMANTIC_EXPANSION_MAX_EXTRA` | `2` | Semantic Expansion 최대 추가 수 |
| `SEMANTIC_EXPANSION_QUERY_MAX_CHARS` | `1200` | 쿼리 최대 길이 |

### Retrieval & Search

| Key | Default | Description |
|-----|---------|-------------|
| `RETRIEVAL_MODE` | `bm25` | 검색 모드 (`bm25`) |
| `SEARCH_BACKEND` | `auto` | 검색 백엔드 (`auto`, `postgres`) |
| `SEARCH_PG_QUERY_MODE` | `websearch` | Postgres tsquery 모드 (`websearch`, `plainto`, `to_tsquery`) |
| `SEARCH_PG_TRGM_ENABLED` | `False` | Postgres에서 pg_trgm fallback 사용 여부 |
| `SEARCH_PG_TRGM_MIN_SIMILARITY` | `0.2` | pg_trgm fallback 최소 유사도 |
| `SEARCH_PG_TRGM_TOP_N` | `40` | pg_trgm fallback 검색 상한 |

### HYDE (Hypothetical Document Embeddings)

| Key | Default | Description |
|-----|---------|-------------|
| `HYDE_ENABLED` | `False` | HYDE 활성화 |
| `HYDE_AUTO_GENERATE` | `False` | HYDE 자동 생성 |
| `HYDE_PROMPT_VERSION` | `hyde_v1` | HYDE 프롬프트 버전 |
| `HYDE_MODEL_NAME` | None | HYDE 모델명 |
| `HYDE_STRATEGY` | `blend` | HYDE 전략 (`blend`, `best_of_two`) |
| `HYDE_BM25_VARIANT` | `mixed_light` | HYDE BM25 변형 |
| `HYDE_NEGATIVE_MODE` | `stopwords` | HYDE 네거티브 모드 |
| `HYDE_MARGIN_EPS` | `0.0` | HYDE 마진 EPS |
| `HYDE_MAX_KEYWORDS` | `7` | HYDE 최대 키워드 |
| `HYDE_MAX_NEGATIVE` | `6` | HYDE 최대 네거티브 |

### PDF Processing

| Key | Default | Description |
|-----|---------|-------------|
| `PDF_PARSER_MODE` | `legacy` | PDF 파서 모드 (`legacy`, `experimental`) |
| `KEEP_PDF_AFTER_INDEX` | `False` | `False`면 인덱싱 성공 직후 원본 PDF 삭제 (청크/메타데이터만 유지) |

### Classifier Post-process Hardening

| Key | Default | Description |
|-----|---------|-------------|
| `CLASSIFIER_ALLOW_ID_FROM_TEXT` | `False` | reason/study_hint 텍스트에서 lecture_id 복구 허용 여부 |
| `CLASSIFIER_REQUIRE_VERBATIM_QUOTE` | `True` | evidence.quote가 후보 snippet의 verbatim일 때만 저장 |
| `CLASSIFIER_REQUIRE_PAGE_SPAN` | `True` | page_start/page_end 없는 evidence 제거 |
| `CLASSIFIER_DEBUG_LOG` | `False` | 분류 및 적용 단계의 `CLASSIFIER_*` 디버그 로그 출력 |

## Environment Profiles

### Development (`FLASK_CONFIG=development`)
- `DEBUG = True`
- `AUTO_CREATE_DB = True`

### Production (`FLASK_CONFIG=production`)
- `DEBUG = False`

### Local Admin (`FLASK_CONFIG=local_admin`)
- 모든 Development 설정 상속
- `SQLALCHEMY_DATABASE_URI` → `LOCAL_ADMIN_DATABASE_URL` 또는 `DATABASE_URL`
- `UPLOAD_FOLDER` → `app/static/uploads_admin`
- `LOCAL_ADMIN_ONLY = True`
- `PDF_PARSER_MODE = 'experimental'`

## Quick Reference for Common Tasks

### Enable AI Classification
```bash
GEMINI_API_KEY=your_key_here
```

### Switch to Experimental PDF Parser
```bash
PDF_PARSER_MODE=experimental
```

### Enable Read-Only Mode
```bash
DB_READ_ONLY=1
```

### Run with Local Admin DB
```bash
FLASK_CONFIG=local_admin
```

## See Also
- [Environment Setup](../setup/env.md)
- [Operations Scripts](../operations/scripts.md)
