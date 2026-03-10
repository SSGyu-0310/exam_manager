from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from app.routes.crop import content_bbox_in_rect, detect_page_panels
from app.services.pdf_cropper import crop_pdf_to_questions


def _physiology3_pdf_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "parse_lab"
        / "review_sessions"
        / "20260309_104511_23359695"
        / "230310_1__.pdf"
    )


def test_content_bbox_in_rect_expands_to_detected_panel_bounds():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    panel_rect = fitz.Rect(90, 160, 520, 258)
    page.draw_rect(panel_rect, color=(0.6, 0.6, 0.6), width=0.75)
    page.insert_text((120, 205), "Panel text", fontsize=12)

    segment_rect = fitz.Rect(0, 120, 595, 320)
    panels = detect_page_panels(page)
    content_bbox = content_bbox_in_rect(page, segment_rect, panels=panels)

    assert len(panels) == 1
    assert panels[0]["kind"] == "panel"
    assert content_bbox is not None
    assert content_bbox.y0 <= panel_rect.y0 + 1.0
    assert content_bbox.y1 >= panel_rect.y1 - 1.0
    assert content_bbox.x0 <= panel_rect.x0 + 1.0
    assert content_bbox.x1 >= panel_rect.x1 - 1.0


def test_crop_includes_known_panel_regions_for_physiology3_pdf(tmp_path):
    sample_pdf = _physiology3_pdf_path()
    if not sample_pdf.exists():
        pytest.skip(f"Representative PDF not found: {sample_pdf}")

    crop_result = crop_pdf_to_questions(
        pdf_path=sample_pdf,
        exam_id=303,
        upload_folder=tmp_path,
    )
    crop_meta = crop_result.get("meta") or {}
    by_qnum = {q.get("qnum"): q for q in crop_meta.get("questions", [])}

    expected_regions = {
        33: {"page": 8, "bbox": (89.38, 480.96, 519.63, 577.15)},
        36: {"page": 10, "bbox": (89.38, 161.45, 519.63, 257.64)},
        73: {"page": 22, "bbox": (89.38, 543.51, 519.63, 572.20)},
    }

    for qnum, expected in expected_regions.items():
        question = by_qnum.get(qnum)
        assert question is not None, f"missing cropped question {qnum}"

        part = next(
            (item for item in (question.get("parts") or []) if item.get("page") == expected["page"]),
            None,
        )
        assert part is not None, f"missing page {expected['page']} crop for question {qnum}"

        x0, y0, x1, y1 = [float(value) for value in part["bbox"]]
        ex0, ey0, ex1, ey1 = expected["bbox"]
        assert x0 <= ex0 + 1.0
        assert y0 <= ey0 + 1.0
        assert x1 >= ex1 - 1.0
        assert y1 >= ey1 - 1.0
