from __future__ import annotations

from app.services import lecture_indexer


class _DummyPdfPlumberPage:
    def __init__(self, text: str | None):
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _DummyPdfPlumberDoc:
    def __init__(self, pages: list[_DummyPdfPlumberPage]):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyFitzPage:
    def __init__(self, text: str | None):
        self._text = text

    def get_text(self, _mode: str) -> str | None:
        return self._text


class _DummyFitzDoc:
    def __init__(self, pages: list[_DummyFitzPage]):
        self._pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._pages)


def test_extract_pdf_pages_uses_pdfplumber_when_available(monkeypatch, tmp_path):
    dummy_pages = [
        _DummyPdfPlumberPage("\u00A0First   line\x00"),
        _DummyPdfPlumberPage(""),
        _DummyPdfPlumberPage("Line 1\n\n\nLine 2"),
    ]
    monkeypatch.setattr(
        lecture_indexer.pdfplumber,
        "open",
        lambda _path: _DummyPdfPlumberDoc(dummy_pages),
    )

    fitz_called = {"value": False}

    def _mark_fitz_call(_path):
        fitz_called["value"] = True
        return _DummyFitzDoc([])

    monkeypatch.setattr(lecture_indexer.fitz, "open", _mark_fitz_call)

    pages = lecture_indexer.extract_pdf_pages(tmp_path / "sample.pdf")

    assert pages == [(1, "First line"), (3, "Line 1\n\nLine 2")]
    assert fitz_called["value"] is False


def test_extract_pdf_pages_falls_back_to_pymupdf(monkeypatch, tmp_path):
    def _raise_pdfplumber_error(_path):
        raise ValueError(
            "Invalid dictionary construct: [/'Registry', b'', /'Ordering', b'', /'Supplement']"
        )

    fitz_pages = [
        _DummyFitzPage("Fallback   text"),
        _DummyFitzPage(""),
        _DummyFitzPage("Another\n\n\npage"),
    ]

    monkeypatch.setattr(lecture_indexer.pdfplumber, "open", _raise_pdfplumber_error)
    monkeypatch.setattr(
        lecture_indexer.fitz,
        "open",
        lambda _path: _DummyFitzDoc(fitz_pages),
    )

    pages = lecture_indexer.extract_pdf_pages(tmp_path / "broken.pdf")

    assert pages == [(1, "Fallback text"), (3, "Another\n\npage")]
