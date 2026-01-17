# Scripts Usage Guide

Exam Manager의 운영 스크립트 사용법과 설계 원칙입니다.

## Script Design Principles

1. **Public API 사용**: 스크립트는 내부 모듈의 private 함수/전역에 직접 의존하지 않고, 공용 서비스 함수를 호출합니다.
2. **CLI 인터페이스 표준화**: `argparse`를 사용하여 일관된 인자 형식 유지
3. **DB 경로 유연성**: `--db` 플래그로 대상 DB를 지정할 수 있어야 합니다.
4. **코드 변경 없는 스크립트**: 리팩토링으로 인해 스크립트가 깨지 않도록 공용 API를 사용해야 합니다.

## Scripts Summary

| Script | Purpose | Public API | Dependencies |
|---------|---------|-------------|--------------|
| `verify_repo.py` | 리팩토링 검증 | `compileall`, `run_migrations`, `init_fts` | Standard library |
| `init_db.py` | DB 초기화 | `create_app` | Flask-SQLAlchemy |
| `run_migrations.py` | 마이그레이션 실행 | `sqlite3` | Standard library |
| `init_fts.py` | FTS 인덱싱 | `create_app`, `LectureChunk` | Flask-SQLAlchemy |
| `clone_db.py` | DB 복제 | `sqlite3` | Standard library |
| `backup_db.py` | DB 백업 | `sqlite3` | Standard library |
| `dump_retrieval_features.py` | 평가용 retrieval 피처 추출 | `retrieval_features`, `create_app`, `EvaluationLabel` | `app.services.retrieval_features` |
| `build_embeddings.py` | 임베딩 빌드 | `embedding_utils`, `create_app`, `LectureChunk` | `app.services.embedding_utils` |
| `evaluate_evalset.py` | 평가 스크립트 | `build_config_hash`, `ClassifierResultCache` | `app.services.classifier_cache` |
| `migrate_ai_fields.py` | AI 필드 마이그레이션 | `create_app`, `db` | Flask-SQLAlchemy |
| `tune_autoconfirm_v2.py` | Auto-Confirm V2 튜닝 | - | Custom logic |
| `drop_lecture_keywords.py` | 강의 키워드 테이블 삭제 | `create_app`, `db` | Flask-SQLAlchemy |

## Script Usage

### Verification & Setup

#### verify_repo.py
리팩토링 전후에 코드 상태를 검증합니다.

```bash
# Basic verification (compileall only)
python scripts/verify_repo.py

# Full verification (with DB migrations/FTS)
python scripts/verify_repo.py --db data/dev.db

# All checks (uses dev.db)
python scripts/verify_repo.py --all
```

### Database Operations

#### init_db.py
DB 스키마를 초기화합니다.

```bash
# Initialize exam.db
python scripts/init_db.py --db data/exam.db

# Initialize admin_local.db
python scripts/init_db.py --db data/admin_local.db
```

#### run_migrations.py
마이그레이션을 실행합니다.

```bash
# Run on specific DB
python scripts/run_migrations.py --db data/dev.db

# Run on default DB (from config)
python scripts/run_migrations.py
```

#### clone_db.py
DB를 복제합니다.

```bash
# Clone prod to dev
python scripts/clone_db.py --db data/exam.db --out data/dev.db
```

#### backup_db.py
DB를 백업합니다.

```bash
# Backup with 30 retention
python scripts/backup_db.py --db data/exam.db --keep 30

# Backup with custom directory
python scripts/backup_db.py --db data/exam.db --keep 30 --dir custom_backups
```

#### drop_lecture_keywords.py
강의 키워드 테이블을 삭제합니다.

```bash
# Drop on specific DB
python scripts/drop_lecture_keywords.py --db data/exam.db
```

### Search & Indexing

#### init_fts.py
FTS(Full-Text Search) 인덱스를 생성/재구축합니다.

```bash
# Sync (incremental update)
python scripts/init_fts.py --db data/dev.db --sync

# Rebuild (clear and rebuild all)
python scripts/init_fts.py --db data/dev.db --rebuild
```

### Embeddings & Features

#### build_embeddings.py
강의 청크 임베딩을 빌드합니다.

```bash
# Rebuild embeddings (clear and rebuild)
python scripts/build_embeddings.py --db data/dev.db --rebuild

# Update existing embeddings (no --rebuild)
python scripts/build_embeddings.py --db data/dev.db
```

#### dump_retrieval_features.py
평가용 retrieval 피처를 추출합니다.

```bash
# Dump features to CSV
python scripts/dump_retrieval_features.py --db data/dev.db --out reports/retrieval_features_evalset.csv
```

### AI & Evaluation

#### evaluate_evalset.py
AI 분류기 성능을 평가합니다.

```bash
# Run evaluation
python scripts/evaluate_evalset.py
```

#### tune_autoconfirm_v2.py
Auto-Confirm V2 파라미터를 튜닝합니다.

```bash
# Run tuning
python scripts/tune_autoconfirm_v2.py
```

### Migration

#### migrate_ai_fields.py
AI 관련 DB 필드를 마이그레이션합니다.

```bash
# Run migration
python scripts/migrate_ai_fields.py --db data/exam.db
```

## Public API Reference

### `app.services.retrieval_features`

```python
# Get retrieval features for a question
from app.services.retrieval_features import get_retrieval_features

features = get_retrieval_features(
    question_text="...",
    db_session=session,
    config=config
)
```

### `app.services.embedding_utils`

```python
# Embedding utilities
from app.services.embedding_utils import (
    DEFAULT_EMBEDDING_MODEL_NAME,
    DEFAULT_EMBEDDING_DIM,
    embed_texts,
    encode_embedding,
)

# Embed text list
embeddings = embed_texts(texts, model_name, batch_size=32)
```

### `app.services.classifier_cache`

```python
# Classifier cache
from app.services.classifier_cache import ClassifierResultCache, build_config_hash

# Build config hash
config_hash = build_config_hash(config_dict)

# Use cache
cache = ClassifierResultCache(path="path/to/cache.json")
result = cache.get(question_id, config_hash, model_name)
cache.set(question_id, config_hash, model_name, result_dict)
cache.save()
```

## Best Practices

1. **Always use `--db` flag**: 스크립트는 항상 `--db` 플래그를 지원하여 dev/prod 구분을 쉽게 합니다.
2. **Use public APIs**: 내부 구현에 의존하지 말고 공용 함수/서비스를 사용합니다.
3. **Handle errors gracefully**: 스크립트는 명확한 에러 메시지와 exit code를 제공해야 합니다.
4. **Document output**: 생성되는 파일 경로를 명시적으로 출력합니다.

## See Also

- [Cache Policy](./cache-policy.md)
- [Operations Overview](../README.md)
- [Configuration Reference](../setup/config-reference.md)
