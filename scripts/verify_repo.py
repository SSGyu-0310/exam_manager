"""
Repository verification script for refactoring safety.

This script runs basic validation checks to ensure the repository is in a good state
before and after refactoring changes.

Usage:
  python scripts/verify_repo.py                    # Basic compileall check
  python scripts/verify_repo.py --ops-preflight    # Run ops backup/restore preflight checks
  python scripts/verify_repo.py --db "$DATABASE_URL" # Include DB migrations/FTS check
  python scripts/verify_repo.py --all                # All checks (preflight + compileall + DB)

Exit codes:
  0 - All checks passed
  1 - One or more checks failed
"""

from __future__ import annotations

import argparse
import compileall
import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

_OPS_REQUIRED_PATHS = (
    ROOT_DIR / "docs" / "ops.md",
    ROOT_DIR / "scripts" / "backup_postgres.py",
    ROOT_DIR / "scripts" / "run_postgres_migrations.py",
    ROOT_DIR / "scripts" / "init_fts.py",
)
_OPS_DB_TOOLS = ("pg_dump", "pg_restore", "psql")


def _ops_preflight_check(require_db_tools: bool) -> bool:
    """
    Verify backup/restore drill prerequisites.

    - Required docs/scripts exist.
    - backups/ is writable for dump outputs.
    - PostgreSQL client tools are available when DB checks are requested.
    """
    print("\nRunning ops preflight checks...")
    ok = True

    for path in _OPS_REQUIRED_PATHS:
        if path.exists():
            print(f"  [OK] {path.relative_to(ROOT_DIR)}")
        else:
            print(f"  [FAIL] Missing required path: {path.relative_to(ROOT_DIR)}")
            ok = False

    backup_dir = ROOT_DIR / "backups"
    probe_path = backup_dir / ".verify_repo_write_probe"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("ok", encoding="utf-8")
        print(f"  [OK] {backup_dir.relative_to(ROOT_DIR)} is writable")
    except Exception as exc:
        print(f"  [FAIL] backups directory preflight failed: {exc}")
        ok = False
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass

    if require_db_tools:
        for tool in _OPS_DB_TOOLS:
            resolved = shutil.which(tool)
            if resolved:
                print(f"  [OK] {tool}: {resolved}")
            else:
                print(f"  [FAIL] Required DB tool not found in PATH: {tool}")
                ok = False

    if ok:
        print("[PASS] Ops preflight checks passed")
    else:
        print("[FAIL] Ops preflight checks failed")
    return ok


def _compile_check() -> bool:
    """Run compileall on Python source files."""
    print("Running compileall check...")
    targets = [
        ROOT_DIR / "app",
        ROOT_DIR / "scripts",
        ROOT_DIR / "run.py",
    ]

    for target in targets:
        if not target.exists():
            print(f"  [SKIP] {target} does not exist")
            continue

        if target.is_dir():
            result = compileall.compile_dir(
                target,
                force=True,
                quiet=1,
            )
        else:
            result = compileall.compile_file(
                target,
                force=True,
                quiet=1,
            )
        if not result:
            print(f"  [FAIL] Compilation failed for {target}")
            return False
        print(f"  [OK] {target}")

    print("[PASS] All Python files compiled successfully")
    return True


def _normalize_db_uri(db_uri: str) -> str:
    uri = db_uri.strip()
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql+psycopg://"):
        return uri
    raise RuntimeError(
        "verify_repo.py DB check supports PostgreSQL URI only "
        "(postgresql+psycopg://...)."
    )


def _db_check(db_uri: str) -> bool:
    """Run DB migrations and FTS check on specified PostgreSQL database."""
    normalized_uri = _normalize_db_uri(db_uri)
    print("\nRunning DB migration/FTS check...")

    try:
        from scripts.run_postgres_migrations import (
            DEFAULT_MIGRATIONS_DIR,
            run_migrations,
        )
        from scripts.init_fts import init_fts

        # Run migrations.
        count = run_migrations(
            db_uri=normalized_uri,
            migrations_dir=DEFAULT_MIGRATIONS_DIR,
            dry_run=False,
        )
        if count > 0:
            print(f"  [INFO] Applied {count} migration(s)")
        else:
            print("  [INFO] No pending migrations")

        # Run FTS sync (doesn't rebuild, just syncs).
        init_fts(normalized_uri, rebuild=False, sync=True)
        print("  [OK] FTS sync completed")

        print("[PASS] DB checks passed")
        return True
    except Exception as e:
        print(f"  [FAIL] DB check failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify repository state for refactoring safety."
    )
    parser.add_argument(
        "--db",
        help="PostgreSQL URI for migration/FTS check.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks including ops preflight and DB checks.",
    )
    parser.add_argument(
        "--ops-preflight",
        action="store_true",
        help="Run backup/restore readiness checks (plus compileall).",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip ops preflight checks.",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("EXAM MANAGER - REPOSITORY VERIFICATION")
    print("=" * 60)

    run_preflight = args.ops_preflight or args.all or not args.skip_preflight
    if run_preflight:
        require_db_tools = bool(args.ops_preflight or args.all or args.db)
        if not _ops_preflight_check(require_db_tools=require_db_tools):
            print("\n[FAIL] Ops preflight checks failed")
            return 1

    # Always run compileall
    if not _compile_check():
        print("\n[FAIL] Compile check failed")
        return 1

    # Run DB checks if requested
    if args.all or args.db:
        db_uri = args.db or os.environ.get("DATABASE_URL")
        if not db_uri:
            print("  [SKIP] DB check skipped: pass --db or set DATABASE_URL")
        elif not _db_check(db_uri):
            print("\n[FAIL] DB check failed")
            return 1

    print("\n" + "=" * 60)
    print("[SUCCESS] All verification checks passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
