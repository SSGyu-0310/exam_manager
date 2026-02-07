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
- `scripts/validate_pdf_parser_manifest.py`: PDF 파서 결과를 체크표(expected/uploaded)와 비교
