#!/usr/bin/env python3
"""
Backfill evaluation_labels with gold labels from user-confirmed lecture assignments.

Policy:
  - Only questions whose lecture_id points to a lecture in the specified block
    (e.g. '생리학1차') are eligible.
  - The gold_lecture_id is taken from questions.lecture_id (user-confirmed).
  - A 'source' column is added to evaluation_labels if missing, and set to
    the --source tag (default: 'gold_physio1').
  - Idempotent: re-runs skip existing labels (matched by question_id + source).

Usage:
  # Dry run (default):
  python scripts/backfill_eval_labels.py --block-name "생리학1차"

  # Execute:
  python scripts/backfill_eval_labels.py --block-name "생리학1차" --dry-run false

  # Inside Docker:
  docker compose exec api python scripts/backfill_eval_labels.py \
      --block-name "생리학1차" --source gold_physio1 --dry-run false
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import text as sa_text
from app import create_app, db


def ensure_source_column(engine):
    """Add 'source' column to evaluation_labels if it doesn't exist."""
    with engine.connect() as conn:
        result = conn.execute(sa_text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'evaluation_labels' AND column_name = 'source'
        """))
        if result.fetchone() is None:
            conn.execute(sa_text(
                "ALTER TABLE evaluation_labels ADD COLUMN source VARCHAR(50)"
            ))
            conn.commit()
            print("[schema] Added 'source' column to evaluation_labels.")
        else:
            print("[schema] 'source' column already exists.")


def find_gold_questions(block_name: str, limit: int | None = None):
    """Find questions with user-confirmed lecture_id in the specified block."""
    query = sa_text("""
        SELECT
            q.id AS question_id,
            q.exam_id,
            q.question_number,
            q.lecture_id AS gold_lecture_id,
            l.title AS lecture_title,
            b.name AS block_name,
            LEFT(q.content, 80) AS content_preview
        FROM questions q
        JOIN lectures l ON q.lecture_id = l.id
        JOIN blocks b ON l.block_id = b.id
        WHERE b.name = :block_name
          AND q.lecture_id IS NOT NULL
        ORDER BY q.id
    """)
    params = {"block_name": block_name}

    with db.engine.connect() as conn:
        rows = conn.execute(query, params).fetchall()

    if limit:
        rows = rows[:limit]

    return rows


def find_existing_labels(source: str):
    """Return set of question_ids that already have labels with given source."""
    query = sa_text("""
        SELECT question_id FROM evaluation_labels
        WHERE source = :source
    """)
    with db.engine.connect() as conn:
        rows = conn.execute(query, {"source": source}).fetchall()
    return {r[0] for r in rows}


def backfill(
    block_name: str,
    source: str,
    dry_run: bool = True,
    limit: int | None = None,
):
    """Insert gold labels for the given block."""

    # Step 1: Ensure schema
    ensure_source_column(db.engine)

    # Step 2: Find eligible questions
    gold_rows = find_gold_questions(block_name, limit=limit)
    print(f"[query] Found {len(gold_rows)} questions with lecture_id in block '{block_name}'")

    if not gold_rows:
        print("[done] No questions found. Nothing to do.")
        return {"inserted": 0, "skipped": 0, "missing": 0, "total": 0}

    # Step 3: Find existing labels (for idempotency)
    existing = find_existing_labels(source)
    print(f"[existing] {len(existing)} labels already exist with source='{source}'")

    # Step 4: Determine inserts vs skips
    to_insert = []
    skipped = []
    missing_lecture = []
    now = datetime.utcnow()

    for row in gold_rows:
        qid = row[0]
        exam_id = row[1]
        question_number = row[2]
        gold_lecture_id = row[3]

        if qid in existing:
            skipped.append(qid)
            continue

        if gold_lecture_id is None:
            missing_lecture.append({
                "question_id": qid,
                "exam_id": exam_id,
                "question_number": question_number,
                "reason": "lecture_id is NULL",
            })
            continue

        to_insert.append({
            "question_id": qid,
            "exam_id": exam_id,
            "question_number": question_number,
            "gold_lecture_id": gold_lecture_id,
            "source": source,
            "note": f"backfill from block '{block_name}', questions.lecture_id",
            "is_ambiguous": False,
            "created_at": now,
            "updated_at": now,
        })

    # Report
    print(f"\n{'=' * 50}")
    print(f"  Block:       {block_name}")
    print(f"  Source:       {source}")
    print(f"  Total found:  {len(gold_rows)}")
    print(f"  To insert:    {len(to_insert)}")
    print(f"  Skipped:      {len(skipped)} (already exist)")
    print(f"  Missing:      {len(missing_lecture)} (no lecture_id)")
    print(f"  Dry run:      {dry_run}")
    print(f"{'=' * 50}\n")

    if dry_run:
        print("[dry-run] No changes made. Pass --dry-run false to execute.")
        # Show sample
        if to_insert:
            print("\n[sample] First 5 records that would be inserted:")
            for rec in to_insert[:5]:
                print(f"  Q{rec['question_id']} -> lecture {rec['gold_lecture_id']}")
        return {
            "inserted": 0,
            "skipped": len(skipped),
            "missing": len(missing_lecture),
            "total": len(gold_rows),
            "would_insert": len(to_insert),
        }

    # Step 5: Insert
    if to_insert:
        insert_sql = sa_text("""
            INSERT INTO evaluation_labels
                (question_id, exam_id, question_number, gold_lecture_id,
                 source, note, is_ambiguous, created_at, updated_at)
            VALUES
                (:question_id, :exam_id, :question_number, :gold_lecture_id,
                 :source, :note, :is_ambiguous, :created_at, :updated_at)
        """)
        with db.engine.begin() as conn:
            conn.execute(insert_sql, to_insert)
        print(f"[insert] Inserted {len(to_insert)} records.")
    else:
        print("[insert] Nothing to insert.")

    # Step 6: Write missing records for manual review
    if missing_lecture:
        out_path = ROOT_DIR / "reports" / "backfill_missing.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            for m in missing_lecture:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"[missing] Wrote {len(missing_lecture)} missing records to {out_path}")

    result = {
        "inserted": len(to_insert),
        "skipped": len(skipped),
        "missing": len(missing_lecture),
        "total": len(gold_rows),
    }
    print(f"\n[done] Result: {json.dumps(result)}")
    return result


def sanity_check(source: str, sample_size: int = 20):
    """Print a random sample of inserted labels for verification."""
    query = sa_text("""
        SELECT
            el.question_id,
            el.gold_lecture_id,
            l.title AS lecture_title,
            b.name AS block_name,
            LEFT(q.content, 60) AS content_preview,
            el.source
        FROM evaluation_labels el
        JOIN questions q ON el.question_id = q.id
        JOIN lectures l ON el.gold_lecture_id = l.id
        JOIN blocks b ON l.block_id = b.id
        WHERE el.source = :source
        ORDER BY RANDOM()
        LIMIT :sample_size
    """)
    with db.engine.connect() as conn:
        rows = conn.execute(query, {"source": source, "sample_size": sample_size}).fetchall()

    if not rows:
        print(f"\n[sanity] No labels found with source='{source}'")
        return

    print(f"\n{'=' * 70}")
    print(f"  Sanity Check: {len(rows)} random samples (source='{source}')")
    print(f"{'=' * 70}")
    for r in rows:
        qid, gold_lid, ltitle, bname, preview, src = r
        preview_clean = (preview or "").replace("\n", " ").strip()
        print(f"  Q{qid:>5} -> L{gold_lid:>3} ({ltitle}) [{bname}]")
        print(f"         {preview_clean[:70]}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill evaluation_labels with gold labels from confirmed lecture assignments."
    )
    parser.add_argument("--block-name", required=True, help="Block name (e.g. '생리학1차')")
    parser.add_argument("--source", default="gold_physio1", help="Source tag for labels")
    parser.add_argument("--dry-run", default="true", help="'true' or 'false'")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions")
    parser.add_argument("--sanity-only", action="store_true", help="Only run sanity check")
    parser.add_argument("--db", default=None, help="DATABASE_URL override")

    args = parser.parse_args()
    dry_run = args.dry_run.lower() in ("true", "1", "yes", "t")

    config_name = os.environ.get("FLASK_CONFIG") or "default"
    db_url = args.db or os.environ.get("DATABASE_URL")
    app = create_app(config_name, db_uri_override=db_url, skip_migration_check=True)

    with app.app_context():
        if args.sanity_only:
            sanity_check(args.source)
            return

        result = backfill(
            block_name=args.block_name,
            source=args.source,
            dry_run=dry_run,
            limit=args.limit,
        )

        # Always run sanity check after insert
        if not dry_run and result.get("inserted", 0) > 0:
            sanity_check(args.source)


if __name__ == "__main__":
    main()
