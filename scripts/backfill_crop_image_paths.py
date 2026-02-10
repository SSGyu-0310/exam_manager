"""
Backfill question.image_path to use cropped original images when available.

This is useful after deploying crop/parser fixes to existing Docker volumes.

Usage:
  python scripts/backfill_crop_image_paths.py --config production --apply
  python scripts/backfill_crop_image_paths.py --config production --exam-id 25 --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import create_app, db
from app.models import PreviousExam, Question
from app.services.pdf_cropper import find_question_crop_image, to_static_relative


def _normalize_relative_path(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    normalized = relative_path.strip().replace("\\", "/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/") :]
    return normalized or None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill question.image_path from exam_crops when available."
    )
    parser.add_argument(
        "--config",
        default="default",
        help="Config name: development|production|local_admin|default",
    )
    parser.add_argument("--exam-id", type=int, help="Only process one exam id.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply DB updates. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    app = create_app(args.config, skip_migration_check=True)
    with app.app_context():
        upload_folder = app.config.get("UPLOAD_FOLDER")
        static_root = app.static_folder

        query = PreviousExam.query
        if args.exam_id is not None:
            query = query.filter(PreviousExam.id == args.exam_id)
        exams = query.order_by(PreviousExam.id.asc()).all()

        checked = 0
        updated = 0
        skipped = 0

        for exam in exams:
            questions = Question.query.filter_by(exam_id=exam.id).all()
            for question in questions:
                checked += 1
                crop_path = find_question_crop_image(
                    exam.id,
                    question.question_number,
                    upload_folder=upload_folder,
                )
                if not crop_path:
                    skipped += 1
                    continue

                relative_path = to_static_relative(crop_path, static_root=static_root)
                normalized = _normalize_relative_path(relative_path)
                if not normalized:
                    skipped += 1
                    continue

                if question.image_path == normalized:
                    continue

                question.image_path = normalized
                updated += 1

        if args.apply and updated:
            db.session.commit()
        else:
            db.session.rollback()

        mode = "apply" if args.apply else "dry-run"
        print(
            f"[{mode}] exams={len(exams)} checked={checked} updated={updated} skipped={skipped}"
        )
        if not args.apply and updated:
            print("Run again with --apply to persist changes.")


if __name__ == "__main__":
    main()
