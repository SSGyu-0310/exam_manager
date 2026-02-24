from __future__ import annotations

from app.services import pdf_parser


class _DummyPdf:
    pages = []


class _DummyPdfContext:
    def __enter__(self):
        return _DummyPdf()

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyPage:
    width = 100.0
    height = 100.0


def test_parse_pdf_skips_image_crop_failure(monkeypatch, tmp_path):
    def _raise_crop_failure(*args, **kwargs):
        raise RuntimeError("code=4: Invalid bandwriter header dimensions/setup")

    monkeypatch.setattr(pdf_parser.pdfplumber, "open", lambda _path: _DummyPdfContext())
    monkeypatch.setattr(pdf_parser, "detect_answer_color", lambda _pdf: None)
    monkeypatch.setattr(
        pdf_parser,
        "extract_events",
        lambda _pdf, _answer_color: [
            {
                "type": "text",
                "page": 1,
                "top": 10.0,
                "x0": 10.0,
                "x1": 60.0,
                "bottom": 20.0,
                "text": "1. Question body",
                "has_key": False,
            },
            {
                "type": "image",
                "page": 1,
                "top": 24.0,
                "x0": 10.0,
                "x1": 90.0,
                "bottom": 80.0,
                "page_obj": _DummyPage(),
            },
        ],
    )
    monkeypatch.setattr(pdf_parser, "merge_orphan_labels", lambda events: events)
    monkeypatch.setattr(pdf_parser, "save_image_crop", _raise_crop_failure)

    parsed = pdf_parser.parse_pdf_to_questions(
        pdf_path=tmp_path / "broken-image.pdf",
        upload_dir=tmp_path,
        exam_prefix="sample",
    )

    assert len(parsed) == 1
    assert parsed[0]["question_number"] == 1
    assert parsed[0]["content"] == "Question body"
    assert parsed[0]["image_path"] is None
