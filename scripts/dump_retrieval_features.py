"""
Dump per-question retrieval features for evalset.

Usage:
  python scripts/dump_retrieval_features.py --db "postgresql+psycopg://user:pass@host:5432/dbname" --out reports/retrieval_features_evalset.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app import create_app
from app.models import EvaluationLabel, LectureChunk
from app.services import retrieval_features


def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    db_uri = db_value.strip()
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if not db_uri.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "--db must be a PostgreSQL URI (postgresql+psycopg://...)."
        )
    return db_uri


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        db_uri = _normalize_db_uri(db_arg)
    else:
        from config import get_config

        db_uri = _normalize_db_uri(str(get_config().runtime.db_uri))
    if not db_uri:
        raise RuntimeError("DATABASE_URL is required for this script.")
    return db_uri


def _parse_page_ranges(raw: str) -> list[tuple[int, int]]:
    if not raw:
        return []
    parts = re.split(r"[;,]", raw)
    ranges = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
        elif "~" in part:
            left, right = part.split("~", 1)
        else:
            left, right = part, part
        try:
            start = int(left.strip())
            end = int(right.strip())
        except ValueError:
            continue
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def _find_gold_chunk_id(label: EvaluationLabel) -> int | None:
    if not label.gold_lecture_id or not label.gold_pages:
        return None
    ranges = _parse_page_ranges(label.gold_pages)
    if not ranges:
        return None
    chunks = LectureChunk.query.filter_by(lecture_id=label.gold_lecture_id).all()
    for start, end in ranges:
        for chunk in chunks:
            if chunk.page_start <= end and chunk.page_end >= start:
                return chunk.id
    return None


def _build_question_text(question) -> str:
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    question_text = question.content or ""
    if choices:
        question_text = f"{question_text}\n" + " ".join(choices)
    return question_text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump retrieval features for evalset.")
    parser.add_argument("--db", default=None, help="PostgreSQL URI override.")
    parser.add_argument("--out", default="reports/retrieval_features_evalset.csv", help="Output CSV path.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k to record.")
    parser.add_argument("--include-ambiguous", action="store_true", help="Include ambiguous labels.")
    args = parser.parse_args()

    db_uri = _resolve_db_uri(args.db)
    app = create_app("default", db_uri_override=db_uri, skip_migration_check=True)

    rows = []
    with app.app_context():
        labels = EvaluationLabel.query.order_by(EvaluationLabel.id.asc()).all()
        for label in labels:
            if label.is_ambiguous and not args.include_ambiguous:
                continue
            if not label.gold_lecture_id:
                continue
            question = label.question
            if not question:
                continue
            question_text = _build_question_text(question)
            artifacts = retrieval_features.build_retrieval_artifacts(
                question_text,
                question.id,
                top_n=80,
                top_k=args.top_k,
            )
            features = artifacts.features
            rows.append(
                {
                    "question_id": question.id,
                    "gold_lecture_id": label.gold_lecture_id,
                    "gold_chunk_id": _find_gold_chunk_id(label),
                    "bm25_topk": json.dumps(features.get("bm25_topk", []), ensure_ascii=False),
                    "embed_topk": json.dumps(features.get("embed_topk", []), ensure_ascii=False),
                    "hybrid_topk": json.dumps(features.get("hybrid_topk", []), ensure_ascii=False),
                    "bm25_margin": features.get("bm25_margin"),
                    "embed_margin": features.get("embed_margin"),
                    "bm25_hybrid_agree": features.get("bm25_hybrid_agree"),
                    "embed_hybrid_agree": features.get("embed_hybrid_agree"),
                    "bm25_embed_agree": features.get("bm25_embed_agree"),
                    "hybrid_top1_bm25_rank": features.get("hybrid_top1_bm25_rank"),
                    "hybrid_top1_embed_rank": features.get("hybrid_top1_embed_rank"),
                    "hybrid_top1_chunk_len": features.get("hybrid_top1_chunk_len"),
                }
            )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question_id",
        "gold_lecture_id",
        "gold_chunk_id",
        "bm25_topk",
        "embed_topk",
        "hybrid_topk",
        "bm25_margin",
        "embed_margin",
        "bm25_hybrid_agree",
        "embed_hybrid_agree",
        "bm25_embed_agree",
        "hybrid_top1_bm25_rank",
        "hybrid_top1_embed_rank",
        "hybrid_top1_chunk_len",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
