# Scripts

운영/마이그레이션/검증 스크립트 모음입니다.

## Core
- `scripts/init_db.py`: DB schema 초기화
- `scripts/run_migrations.py`: SQLite 마이그레이션 적용
- `scripts/init_fts.py`: SQLite/Postgres FTS 초기화/동기화

## Migration
- `scripts/migrate_sqlite_to_postgres.py`: SQLite -> Postgres 데이터 이관
- `scripts/apply_postgres_indexes.py`: Postgres 인덱스 적용
- `scripts/verify_postgres_setup.py`: Postgres FTS/확장 검증

## Ops
- `scripts/backup_db.py`: SQLite 백업
- `scripts/clone_db.py`: prod -> dev DB 복제
- `scripts/compare_db_counts.py`: DB 건수 비교
- `scripts/dev.py`: Flask + Next 동시 실행

## Example
```bash
python scripts/init_db.py --db data/exam.db
python scripts/init_fts.py --db data/exam.db --sync
python scripts/migrate_sqlite_to_postgres.py --sqlite data/exam.db --postgres "postgresql+psycopg://user:pass@host:5432/dbname"
```
