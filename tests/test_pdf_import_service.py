from app.services.pdf_import_service import _resolve_question_image_path


def test_resolve_question_image_path_prefers_parser_image():
    resolved = _resolve_question_image_path(
        exam_id=42,
        question_number=7,
        parser_image_path="parsed_stem.png",
        crop_question_images={7: "crop_q7.png"},
        crop_is_reliable=True,
    )

    assert resolved == "parsed_stem.png"


def test_resolve_question_image_path_falls_back_to_crop_when_parser_missing():
    resolved = _resolve_question_image_path(
        exam_id=42,
        question_number=7,
        parser_image_path=None,
        crop_question_images={7: "crop_q7.png"},
        crop_is_reliable=True,
    )

    assert resolved == "exam_crops/exam_42/crop_q7.png"
