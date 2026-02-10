from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pdf_cropper import crop_pdf_to_questions
from app.services.pdf_parser_factory import parse_pdf


def _sample_pdf_path() -> Path:
    return Path(__file__).resolve().parents[1] / "parse_lab" / "pdfs" / "sample.pdf"


def test_crop_matches_parser_question_numbers_for_sample_pdf(tmp_path):
    pytest.importorskip("fitz")

    sample_pdf = _sample_pdf_path()
    if not sample_pdf.exists():
        pytest.skip(f"Sample PDF not found: {sample_pdf}")

    parser_media_dir = tmp_path / "parser_media"
    parser_media_dir.mkdir(parents=True, exist_ok=True)

    parsed_questions = parse_pdf(
        pdf_path=sample_pdf,
        upload_dir=parser_media_dir,
        exam_prefix="sample",
        mode="legacy",
    )
    parsed_numbers = {int(q["question_number"]) for q in parsed_questions}

    crop_result = crop_pdf_to_questions(
        pdf_path=sample_pdf,
        exam_id=1,
        upload_folder=tmp_path,
    )
    crop_meta = crop_result.get("meta") or {}
    crop_numbers = {
        int(q["qnum"])
        for q in crop_meta.get("questions", [])
        if isinstance(q.get("qnum"), int)
    }

    assert crop_numbers == parsed_numbers
    assert len(crop_result.get("question_images", {})) == len(parsed_numbers)
    assert crop_meta.get("duplicate_qnums") in (None, [])


def test_crop_keeps_image_region_for_known_continuation_questions(tmp_path):
    pytest.importorskip("fitz")

    sample_pdf = _sample_pdf_path()
    if not sample_pdf.exists():
        pytest.skip(f"Sample PDF not found: {sample_pdf}")

    crop_result = crop_pdf_to_questions(
        pdf_path=sample_pdf,
        exam_id=2,
        upload_folder=tmp_path,
    )
    crop_meta = crop_result.get("meta") or {}
    by_qnum = {q.get("qnum"): q for q in crop_meta.get("questions", [])}

    for qnum in (101, 103, 110):
        question = by_qnum.get(qnum)
        assert question is not None
        assert len(question.get("parts") or []) >= 2
        second_part = question["parts"][1]
        # Regression guard: this part used to start at text-only y and clipped top image area.
        assert float(second_part["bbox"][1]) <= 60.0
