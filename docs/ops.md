# Ops Playbook (SQLite)

## Standard change flow
1) Hot backup before any change.
2) Clone prod -> dev, test migrations/backfill.
3) Apply to prod.
4) Rebuild FTS when chunk/index schema changes.

### 1) Backup (hot)
```bash
python scripts/backup_db.py --db data/exam.db --keep 30
```

### 2) Clone prod -> dev
```bash
python scripts/clone_db.py --db data/exam.db --out data/dev.db
```

### 3) Run migrations on dev
```bash
python scripts/run_migrations.py --db data/dev.db
```

### 4) FTS rebuild on dev (if chunks/index changed)
```bash
python scripts/init_fts.py --db data/dev.db --rebuild
```

### 5) Apply to prod
```bash
python scripts/backup_db.py --db data/exam.db --keep 30
python scripts/run_migrations.py --db data/exam.db
python scripts/init_fts.py --db data/exam.db --rebuild
```

## Init a new DB
```bash
python scripts/init_db.py --db data/dev.db
```

## Read-only / safety flags
- `DB_READ_ONLY=1` blocks write paths (uploads, indexing, classification apply, practice submit).
- `AI_AUTO_APPLY=0` prevents automatic classification apply.
- `RETRIEVAL_MODE=bm25` (default) or `off` to disable retrieval.
- Optional hot backup hook: `AUTO_BACKUP_BEFORE_WRITE=1` and `AUTO_BACKUP_KEEP=30`.

## Rollback / recovery
1) Enable read-only mode:
   - `DB_READ_ONLY=1`
2) Restore backup:
```bash
copy backups/exam.db.YYYYMMDD_HHMMSS data/exam.db
```
3) Rebuild FTS:
```bash
python scripts/init_fts.py --db data/exam.db --rebuild
```
4) Disable read-only after validation:
   - `DB_READ_ONLY=0`

## Migration rules
- Migration files live in `migrations/` and run in filename order.
- Do not include `BEGIN/COMMIT` in migration SQL (runner wraps them).
- Use `scripts/run_migrations.py --db ...` for all schema changes.
