# Scripts Usage Guide (Postgres)

Exam Manager 운영 스크립트 사용 가이드입니다.

## Script Design Principles

1. Public API 우선: 스크립트는 공용 서비스/진입점만 호출합니다.
2. CLI 표준화: `argparse` 기반 인자 규칙을 유지합니다.
3. Postgres URI 기준: DB 대상은 `--db postgresql+psycopg://...` 형식으로 지정합니다.
4. 명확한 실패: 미지원(legacy 경로 등) 입력은 즉시 에러 처리합니다.

## Scripts Summary

| Script | Purpose | Public API | Dependencies |
|---------|---------|-------------|--------------|
| `verify_repo.py` | 리팩토링/운영 사전점검(ops preflight + 컴파일/DB/FTS) | `compileall`, `run_postgres_migrations`, `init_fts` | Standard library + project scripts |
| `init_db.py` | 스키마 초기화 | `create_app` | Flask-SQLAlchemy |
| `run_postgres_migrations.py` | Postgres 마이그레이션 실행 | migration executor | `psycopg` |
| `run_migrations.py` | 호환 별칭(Postgres) | `run_postgres_migrations` | `psycopg` |
| `init_fts.py` | FTS 동기화/재구성 | `create_app`, SQLAlchemy | Flask-SQLAlchemy |
| `backup_postgres.py` | DB 백업(`pg_dump`) | subprocess | PostgreSQL client |
| `backup_db.py` | 호환 별칭(Postgres + retention) | subprocess | PostgreSQL client |
| `migrate_ai_fields.py` | AI 필드 마이그레이션 | `create_app`, `db` | Flask-SQLAlchemy |
| `dump_retrieval_features.py` | retrieval 피처 추출 | `retrieval_features`, `create_app`, `EvaluationLabel` | app services |
| `build_queries.py` | HyDE-lite 질의 구축 | `query_transformer`, `create_app`, `QuestionQuery` | app services |
| `evaluate_evalset.py` | 평가 스크립트 | `build_config_hash`, `ClassifierResultCache` | app services |
| `tune_autoconfirm_v2.py` | auto-confirm 튜닝 | `retrieval_features`, `create_app`, `EvaluationLabel` | app services |

## Core Usage

### Verification & setup
```bash
# compileall only
python scripts/verify_repo.py

# ops preflight + compileall
python scripts/verify_repo.py --ops-preflight

# compileall + DB/FTS checks
python scripts/verify_repo.py --db "$DATABASE_URL"

# same as above, but reads DATABASE_URL from env when --db is omitted
python scripts/verify_repo.py --all
```

### Database operations
```bash
# schema init
python scripts/init_db.py --db "$DATABASE_URL"

# migrations
python scripts/run_postgres_migrations.py --db "$DATABASE_URL"

# compatibility alias
python scripts/run_migrations.py --db "$DATABASE_URL"

# backup
python scripts/backup_postgres.py --db "$DATABASE_URL"

# backup compatibility alias with retention
python scripts/backup_db.py --db "$DATABASE_URL" --keep 30
```

### Search & indexing
```bash
# incremental sync
python scripts/init_fts.py --db "$DATABASE_URL" --sync

# full rebuild
python scripts/init_fts.py --db "$DATABASE_URL" --rebuild
```

### Retrieval features
```bash
python scripts/dump_retrieval_features.py --db "$DATABASE_URL" --out reports/retrieval_features_evalset.csv
```

### AI & evaluation
```bash
python scripts/evaluate_evalset.py --db "$DATABASE_URL"
python scripts/tune_autoconfirm_v2.py --db "$DATABASE_URL"
```

## Legacy / migration-only scripts
- `scripts/legacy/`: 과거 데이터 1회 이관 스크립트 모음
- `scripts/legacy/compare_db_counts.py`: legacy DB/Postgres row count 비교
- `scripts/legacy/migrate_user_data.py`: 과거 사용자 데이터 보정 스크립트
- `scripts/clone_db.py`: legacy clone 경로 제거됨 (Postgres 운영에서는 사용하지 않음)
- `scripts/drop_lecture_keywords.py`: deprecated (Postgres 스키마 변경은 migration SQL 사용)

## Best Practices

1. 프로덕션 작업 전 `backup_postgres.py` 먼저 실행합니다.
2. 마이그레이션은 `run_postgres_migrations.py`를 표준으로 사용합니다.
3. `--db`를 명시해 대상 DB를 항상 분리합니다.
4. 스크립트 출력 경로/적용 건수 로그를 배포 기록에 남깁니다.
