# Scripts

Operational and migration scripts.

## Docker helper
- `scripts/dc`: wrapper for `docker compose --env-file .env.docker`

Example:
```bash
./scripts/dc up -d
./scripts/dc logs -f api web
```

## Local dev helpers
- `scripts/dev-db`: DB-only compose wrapper (defaults to `docker-compose.yml` DB + host `5432` port override)
- `scripts/dev-init-db`: initialize Postgres schema + FTS for local dev
- `scripts/dev-backend`: run Flask in development mode on host (auto-start DB by default)
- `scripts/dev-frontend`: run Next.js dev server on host
- `scripts/dev-test-backend`: run backend pytest against Postgres test DB (auto-create if missing)

Example:
```bash
./scripts/dev-db up -d db
./scripts/dev-init-db
./scripts/dev-backend   # terminal 1
./scripts/dev-frontend  # terminal 2
./scripts/dev-test-backend
```

Isolated DB mode (separate volume):
```bash
DEV_DB_COMPOSE_FILE=docker-compose.local.yml ./scripts/dev-db up -d db
```

## Core DB scripts
- `scripts/init_db.py`: initialize schema
- `scripts/init_fts.py`: sync/rebuild FTS
- `scripts/run_postgres_migrations.py`: apply Postgres migrations (`migrations/postgres/*.sql`)
- `scripts/run_migrations.py`: compatibility alias to Postgres migrations

## Postgres operations
- `scripts/backup_postgres.py`: Postgres backup (`pg_dump`)
- `scripts/backup_db.py`: compatibility alias to Postgres backup
- `scripts/apply_postgres_indexes.py`
- `scripts/verify_postgres_setup.py`

## Utility scripts
- `scripts/backfill_crop_image_paths.py`: 기존 문제 `image_path`를 `exam_crops/...`로 백필
- `scripts/validate_pdf_parser_manifest.py`: PDF 파서 결과를 체크표(expected/uploaded)와 비교
- `scripts/pdf_lab.py`: 로컬 PDF 실험실 (파싱/이상치/diff/선택적 강의 분류)
- `scripts/inspect_classification_job.py`: AI 분류 job의 미분류 원인/적용 가능 여부 진단 출력
- `scripts/build_embeddings.py`: Postgres 기반 임베딩 구축
- `scripts/build_queries.py`: Postgres 기반 질의 변환(HyDE-lite) 구축
- `scripts/dump_retrieval_features.py`: Postgres 기반 retrieval feature 덤프
- `scripts/evaluate_evalset.py`: Postgres 기반 평가 실행
- `scripts/tune_autoconfirm_v2.py`: Postgres 기반 auto-confirm 튜닝

## Legacy migration-only utilities
- `scripts/legacy/`: one-time historical DB import utilities
- `scripts/legacy/compare_db_counts.py`
- `scripts/legacy/migrate_user_data.py`
- `scripts/clone_db.py` (deprecated stub)

### Crop image backfill
```bash
# dry-run
.venv/bin/python scripts/backfill_crop_image_paths.py --config default

# apply
.venv/bin/python scripts/backfill_crop_image_paths.py --config default --apply
```

## PDF Lab quick examples
```bash
# 1) 단발 실행: 파싱 + 이상치 리포트
.venv/bin/python scripts/pdf_lab.py --pdf parse_lab/pdfs/sample.pdf --mode legacy

# 2) 비교 실행: experimental 결과를 legacy와 diff
.venv/bin/python scripts/pdf_lab.py \
  --pdf parse_lab/pdfs/sample.pdf \
  --mode experimental \
  --compare-mode legacy

# 3) 자동 재실행: parser 코드/대상 PDF 변경 감지
.venv/bin/python scripts/pdf_lab.py \
  --pdf parse_lab/pdfs/sample.pdf \
  --mode experimental \
  --watch

# 4) 강의 후보 + 분류기까지 확인 (GEMINI_API_KEY 필요)
.venv/bin/python scripts/pdf_lab.py \
  --pdf parse_lab/pdfs/sample.pdf \
  --mode experimental \
  --with-classifier \
  --top-k 8
```

## Classification diagnostics
```bash
# job 요약 + 문항별 원인 태그
.venv/bin/python scripts/inspect_classification_job.py --job-id 123 --config production

# 요약만 출력
.venv/bin/python scripts/inspect_classification_job.py --job-id 123 --config production --no-rows
```
