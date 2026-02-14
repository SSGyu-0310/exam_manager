"""
Inspect AI classification job diagnostics from terminal.

Usage:
  python scripts/inspect_classification_job.py --job-id 42
  python scripts/inspect_classification_job.py --job-id 42 --config production --no-rows
  python scripts/inspect_classification_job.py --job-id 42 --question-ids 101,102,103
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / ".env.docker")

from app import create_app
from app.models import ClassificationJob
from app.services.ai_classifier import build_job_diagnostics


def _parse_question_ids(raw: str) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except ValueError:
            continue
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect classification job diagnostics.")
    parser.add_argument("--job-id", type=int, required=True, help="ClassificationJob id")
    parser.add_argument(
        "--config",
        default="default",
        help="Flask config profile (default/development/production/local_admin)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Optional DB URI override (e.g., postgresql+psycopg://...)",
    )
    parser.add_argument(
        "--question-ids",
        default="",
        help="Optional comma-separated question ids to filter diagnostics",
    )
    parser.add_argument(
        "--row-limit",
        type=int,
        default=120,
        help="Max row details to print when rows are enabled (default: 120)",
    )
    parser.add_argument(
        "--no-rows",
        action="store_true",
        help="Print only summary without per-question rows",
    )
    args = parser.parse_args()

    app = create_app(
        args.config,
        db_uri_override=args.db,
        skip_migration_check=True,
    )
    question_ids = _parse_question_ids(args.question_ids)
    row_limit = max(0, min(args.row_limit, 2000))

    with app.app_context():
        job = ClassificationJob.query.get(args.job_id)
        if not job:
            print(
                json.dumps(
                    {"ok": False, "error": f"job_id={args.job_id} not found"},
                    ensure_ascii=False,
                )
            )
            return 1

        diagnostics = build_job_diagnostics(
            job,
            question_ids=question_ids or None,
            include_rows=not args.no_rows,
            row_limit=row_limit,
        )

    print(json.dumps({"ok": True, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
