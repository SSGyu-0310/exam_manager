from app.services.pdf_parser_factory import get_pdf_parser


def test_get_pdf_parser_legacy_uses_pdf_lab_parser():
    parser = get_pdf_parser("legacy")

    assert parser.__module__ == "app.services.pdf_lab_parser"
    assert parser.__name__ == "parse_pdf_to_lab_questions"
