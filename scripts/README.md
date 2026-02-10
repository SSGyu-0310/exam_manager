# Scripts

Operational and migration scripts.

## Docker helper
- `scripts/dc`: wrapper for `docker compose --env-file .env.docker`

Example:
```bash
./scripts/dc up -d
./scripts/dc logs -f api web
```

## Core DB scripts
- `scripts/init_db.py`: initialize schema
- `scripts/init_fts.py`: sync/rebuild FTS
- `scripts/run_migrations.py`: apply SQLite migrations

## Postgres migration scripts
- `scripts/migrate_sqlite_to_postgres.py`
- `scripts/apply_postgres_indexes.py`
- `scripts/verify_postgres_setup.py`

## Utility scripts
- `scripts/backup_db.py`
- `scripts/clone_db.py`
- `scripts/compare_db_counts.py`
- `scripts/backfill_crop_image_paths.py`: 기존 문제 `image_path`를 `exam_crops/...`로 백필
- `scripts/validate_pdf_parser_manifest.py`: PDF 파서 결과를 체크표(expected/uploaded)와 비교
- `scripts/pdf_lab.py`: 로컬 PDF 실험실 (파싱/이상치/diff/선택적 강의 분류)

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
