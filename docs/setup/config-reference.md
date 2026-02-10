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

### Database Operations

| Key | Default | Description |
|-----|---------|-------------|
| `AUTO_CREATE_DB` | `False` (`True` in Dev) | 앱 시작 시 DB 자동 생성 |
| `DB_READ_ONLY` | `False` | DB 쓰기 금지 모드 |
| `CHECK_PENDING_MIGRATIONS` | `True` | 앱 시작 시 미적용 마이그레이션 감지 |
| `FAIL_ON_PENDING_MIGRATIONS` | `False` | 프로덕션에서 미적용 마이그레이션 있으면 중단 |
| `LOCAL_ADMIN_ONLY` | `False` | 관리자 라우트 localhost만 허용 |
| `LOCAL_ADMIN_DB` | `data/admin_local.db` | local admin DB 경로 |

### Backup

| Key | Default | Description |
|-----|---------|-------------|
| `AUTO_BACKUP_BEFORE_WRITE` | `False` | 쓰기 전 핫백업 수행 |
| `AUTO_BACKUP_KEEP` | `30` | 백업 유지 개수 |
| `AUTO_BACKUP_DIR` | `backups` | 백업 디렉토리 |
| `ENFORCE_BACKUP_BEFORE_WRITE` | `False` | 프로덕션에서 백업 강제 |

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
| `RETRIEVAL_MODE` | `hybrid_rrf` | 검색 모드 (`bm25`, `hybrid_rrf`) |
| `RRF_K` | `60` | RRF K 파라미터 (hybrid_rrf에서만 사용) |
| `EMBEDDING_MODEL_NAME` | `intfloat/multilingual-e5-base` | Embedding 모델명 |
| `EMBEDDING_DIM` | `768` | Embedding 차원 |
| `EMBEDDING_TOP_N` | `300` | Embedding top-N |

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
| `HYDE_EMBED_WEIGHT` | `0.7` | HYDE Embedding 가중치 |
| `HYDE_EMBED_WEIGHT_ORIG` | `0.3` | HYDE 원본 Embedding 가중치 |

### PDF Processing

| Key | Default | Description |
|-----|---------|-------------|
| `PDF_PARSER_MODE` | `legacy` | PDF 파서 모드 (`legacy`, `experimental`) |

## Environment Profiles

### Development (`FLASK_CONFIG=development`)
- `DEBUG = True`
- `AUTO_CREATE_DB = True`

### Production (`FLASK_CONFIG=production`)
- `DEBUG = False`

### Local Admin (`FLASK_CONFIG=local_admin`)
- 모든 Development 설정 상속
- `SQLALCHEMY_DATABASE_URI` → `data/admin_local.db`
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
