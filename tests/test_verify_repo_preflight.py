from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_verify_repo():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "verify_repo.py"
    spec = importlib.util.spec_from_file_location("verify_repo_for_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_repo_layout(mod, tmp_path: Path) -> tuple[Path, tuple[Path, ...]]:
    root_dir = tmp_path / "repo"
    required_paths = (
        root_dir / "docs" / "ops.md",
        root_dir / "scripts" / "backup_postgres.py",
        root_dir / "scripts" / "run_postgres_migrations.py",
        root_dir / "scripts" / "init_fts.py",
    )
    mod.ROOT_DIR = root_dir
    mod._OPS_REQUIRED_PATHS = required_paths
    return root_dir, required_paths


def test_ops_preflight_fails_when_required_paths_are_missing(tmp_path):
    mod = _load_verify_repo()
    _set_repo_layout(mod, tmp_path)

    ok = mod._ops_preflight_check(require_db_tools=False)

    assert ok is False


def test_ops_preflight_succeeds_with_required_paths_and_tools(tmp_path, monkeypatch):
    mod = _load_verify_repo()
    root_dir, required_paths = _set_repo_layout(mod, tmp_path)
    for path in required_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# ok\n", encoding="utf-8")

    mod._OPS_DB_TOOLS = ("pg_dump", "pg_restore", "psql")
    monkeypatch.setattr(mod.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    ok = mod._ops_preflight_check(require_db_tools=True)

    assert ok is True
    assert (root_dir / "backups").exists()


def test_ops_preflight_fails_when_db_tool_is_missing(tmp_path, monkeypatch):
    mod = _load_verify_repo()
    _, required_paths = _set_repo_layout(mod, tmp_path)
    for path in required_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# ok\n", encoding="utf-8")

    mod._OPS_DB_TOOLS = ("pg_dump", "pg_restore")
    monkeypatch.setattr(
        mod.shutil,
        "which",
        lambda tool: "/usr/bin/pg_dump" if tool == "pg_dump" else None,
    )

    ok = mod._ops_preflight_check(require_db_tools=True)

    assert ok is False
