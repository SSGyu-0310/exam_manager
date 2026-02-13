"""Legacy compatibility wrapper.

This utility is preserved under scripts/legacy as a one-off legacy migration helper.
"""
from __future__ import annotations

from scripts.legacy.migrate_user_data import migrate_data


if __name__ == "__main__":
    raise RuntimeError(
        "scripts/migrate_user_data.py is legacy-only. "
        "Use scripts/legacy/migrate_user_data.py and review hardcoded parameters before running."
    )
