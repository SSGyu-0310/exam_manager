# Release Operations Checklist (Postgres)

Final deploy-readiness checklist and rollback runbook.

## 0) HTTP request log standard

- Format: JSON line (machine-parseable).
- Required fields:
  - `request_id`: Correlation ID from `X-Request-ID` header or generated UUID.
  - `route`: Flask route rule (fallback: request path).
  - `status`: HTTP status code.
  - `latency`: Request latency in milliseconds.
  - `error_code`: API code for failures, `HTTP_<status>` fallback, `null` for success.
- Example:
```json
{"request_id":"8fe6034b249d45f6be08b9267f444e18","route":"/api/manage/upload-pdf","status":201,"latency":24.37,"error_code":null}
```

## 1) Pre-deploy gate (ordered)

- [ ] Confirm release owner, rollback owner, and incident channel.
- [ ] Confirm target env is loaded (`DATABASE_URL`, `FLASK_CONFIG`, secrets).
- [ ] Confirm migration guard flags:
  - `CHECK_PENDING_MIGRATIONS=1`
  - `FAIL_ON_PENDING_MIGRATIONS=1` (production)
- [ ] Confirm write safety flags match rollout plan:
  - `DB_READ_ONLY` (normally `0` before release)
  - `AI_AUTO_APPLY`
  - `RETRIEVAL_MODE`
- [ ] Verify tooling availability: `pg_dump`, `pg_restore`, `psql`.
- [ ] Run repository baseline checks:
```bash
python scripts/verify_repo.py --ops-preflight
```
- [ ] Create pre-deploy DB backup:
```bash
python scripts/backup_postgres.py --db "$DATABASE_URL"
```
- [ ] Record backup file path and release timestamp.

## Backup/restore rehearsal drill (non-prod target)

Run this drill regularly against a dedicated restore DB.

1. Prepare DB URLs.
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/exam_prod_like"
export LIBPQ_DATABASE_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"
export DRILL_DB_NAME="exam_restore_drill"
export DRILL_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/${DRILL_DB_NAME}"
export DRILL_DATABASE_URL_LIBPQ="${DRILL_DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"
export POSTGRES_ADMIN_URL="postgresql://user:pass@host:5432/postgres"
```
2. Run preflight tooling checks.
```bash
python scripts/verify_repo.py --ops-preflight
```
3. Take a backup and capture the newest artifact.
```bash
python scripts/backup_postgres.py --db "$DATABASE_URL"
LATEST_DUMP="$(ls -1t backups/*.dump | head -n 1)"
pg_restore --list "$LATEST_DUMP" > /tmp/exam_restore_drill.list
```
4. Recreate drill DB and restore.
```bash
psql "$POSTGRES_ADMIN_URL" -c "DROP DATABASE IF EXISTS ${DRILL_DB_NAME};"
psql "$POSTGRES_ADMIN_URL" -c "CREATE DATABASE ${DRILL_DB_NAME};"
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$DRILL_DATABASE_URL_LIBPQ" "$LATEST_DUMP"
```
5. Validate post-restore state.
```bash
python scripts/run_postgres_migrations.py --db "$DRILL_DATABASE_URL"
python scripts/init_fts.py --db "$DRILL_DATABASE_URL" --sync
psql "$DRILL_DATABASE_URL_LIBPQ" -c "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC LIMIT 20;"
```

## 2) Deploy execution (ordered)

1. Apply Postgres migrations:
```bash
python scripts/run_postgres_migrations.py --db "$DATABASE_URL"
```
2. Sync FTS metadata:
```bash
python scripts/init_fts.py --db "$DATABASE_URL" --sync
```
3. Deploy/restart services:
```bash
./scripts/dc up -d --build
```
4. Verify app health and startup migration checks:
```bash
./scripts/dc logs --tail=200 api
```

## 3) Post-deploy verification (must pass)

- [ ] API health check returns success.
- [ ] `/manage` CRUD smoke path works.
- [ ] Retrieval returns expected candidates for a known query.
- [ ] AI classification flow behaves as expected for current `AI_AUTO_APPLY`.
- [ ] No migration mismatch errors in API logs.

## 4) No-Go / blocking conditions

Treat release as `No-Go` immediately if any item below is true:
- [ ] Backup command fails or backup file is missing/corrupt.
- [ ] Migration command fails or reports checksum/version mismatch.
- [ ] API cannot start cleanly after deploy.
- [ ] Core smoke flows (auth/manage/retrieval) fail.
- [ ] Rollback backup candidate cannot be identified.

## 5) Rollback completeness checklist

Rollback is complete only when all items are checked:
- [ ] Trigger condition and incident timestamp recorded.
- [ ] Writes blocked (`DB_READ_ONLY=1`) and high-risk auto actions disabled (`AI_AUTO_APPLY=0`).
- [ ] DB restore performed from known-good dump.
- [ ] `schema_migrations` state verified after restore.
- [ ] FTS re-synced after restore.
- [ ] API/UI smoke checks pass on rolled-back state.
- [ ] Release status communicated (`rolled back`) with backup file and verification evidence.

## 6) Rollback procedure (validated commands)

1. Freeze risky behavior and block writes.
```bash
# apply in deployment env, then restart services
export DB_READ_ONLY=1
export AI_AUTO_APPLY=0
export RETRIEVAL_MODE=bm25
```
2. Convert SQLAlchemy URI for libpq CLI tools (`pg_restore`, `psql`).
```bash
export LIBPQ_DATABASE_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"
```
3. Select restore target dump and verify file exists.
```bash
ls -lh backups/*.dump | tail -n 10
export BACKUP_FILE="backups/<db>_YYYYMMDD_HHMMSS.dump"
test -f "$BACKUP_FILE"
```
4. Restore database.
```bash
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$LIBPQ_DATABASE_URL" "$BACKUP_FILE"
```
5. Verify migration state after restore.
```bash
psql "$LIBPQ_DATABASE_URL" -c "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC LIMIT 20;"
```
6. Re-sync FTS metadata.
```bash
python scripts/init_fts.py --db "$DATABASE_URL" --sync
```
7. Run smoke checks and keep `DB_READ_ONLY=1` until verification passes.
8. Re-open writes only after explicit go decision (`DB_READ_ONLY=0` + restart).

## 7) Destructive-change standard

- Keep schema changes in `migrations/postgres/*.sql`.
- Include related index/constraint changes in the same migration unit.
- Apply in dev/staging first, then production.

## 8) Canonical operation commands

```bash
python scripts/backup_postgres.py --db "$DATABASE_URL"
python scripts/run_postgres_migrations.py --db "$DATABASE_URL"
python scripts/init_fts.py --db "$DATABASE_URL" --sync
./scripts/dc up -d --build
```
