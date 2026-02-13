"""Legacy compatibility wrapper.

This utility is preserved under scripts/legacy for one-time migration checks.
"""
from __future__ import annotations

from scripts.legacy.compare_db_counts import main


if __name__ == "__main__":
    main()
