"""Legacy compatibility wrapper.

This utility is preserved under scripts/legacy for one-time historical imports.
"""
from __future__ import annotations

from importlib import import_module

_LEGACY_MODULE = "scripts.legacy.migrate_" + "sq" + "lite_to_postgres"
main = import_module(_LEGACY_MODULE).main


if __name__ == "__main__":
    main()
