from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Set

from flask import current_app

from app import db
from app.models import Question, Choice, PreviousExam
from app.services.pdf_cropper import get_exam_crop_dir
from app.services.transaction import transactional


def _resolve_upload_folder() -> Path:
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        return Path(upload_folder)
    return Path(current_app.static_folder) / "uploads"


def _normalize_upload_path(path_value: str, upload_root: Path) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = upload_root / candidate
    try:
        resolved = candidate.resolve()
    except FileNotFoundError:
        resolved = candidate.absolute()
    try:
        resolved.relative_to(upload_root.resolve())
    except ValueError:
        return None
    return resolved


def _collect_exam_image_paths(exam_id: int) -> Set[str]:
    paths: Set[str] = set()
    questions = Question.query.filter_by(exam_id=exam_id).all()
    for question in questions:
        if question.image_path:
            paths.add(question.image_path)
        for choice in question.choices:
            if choice.image_path:
                paths.add(choice.image_path)
    return paths


def _collect_shared_image_paths(exam_id: int) -> Set[str]:
    other_question_paths = {
        row[0]
        for row in db.session.query(Question.image_path)
        .filter(Question.exam_id != exam_id, Question.image_path.isnot(None))
        .distinct()
        .all()
        if row[0]
    }
    other_choice_paths = {
        row[0]
        for row in db.session.query(Choice.image_path)
        .join(Question)
        .filter(Question.exam_id != exam_id, Choice.image_path.isnot(None))
        .distinct()
        .all()
        if row[0]
    }
    return other_question_paths | other_choice_paths


def _delete_files(
    paths: Iterable[str], shared_paths: Set[str], upload_root: Path
) -> None:
    for path_value in paths:
        if path_value in shared_paths:
            continue
        resolved = _normalize_upload_path(path_value, upload_root)
        if not resolved:
            continue
        try:
            resolved.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Failed to delete file: %s", resolved)


def _delete_crop_dir(exam_id: int, upload_root: Path) -> None:
    crop_dir = get_exam_crop_dir(exam_id, upload_folder=upload_root)
    if crop_dir.exists():
        shutil.rmtree(crop_dir, ignore_errors=True)


@transactional
def delete_exam_with_assets(exam: PreviousExam) -> None:
    exam_id = exam.id
    upload_root = _resolve_upload_folder()
    exam_paths = _collect_exam_image_paths(exam_id)
    shared_paths = _collect_shared_image_paths(exam_id)

    db.session.delete(exam)

    _delete_files(exam_paths, shared_paths, upload_root)
    _delete_crop_dir(exam_id, upload_root)
