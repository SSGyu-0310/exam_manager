import json

from app.services.pdf_lab_parser import (
    _detect_page_panels,
    _finalize_question,
    _is_compound_subquestion_stem,
    _match_option_line,
    parse_pdf_to_lab_questions,
)
from app.services.pdf_lab_review import _build_crop_lookup


class _DummyPdf:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyPage:
    def __init__(self, page_number, lines=None, rects=None, images=None):
        self.page_number = page_number
        self.lines = list(lines or [])
        self.rects = list(rects or [])
        self.images = list(images or [])


def _patch_parse_dependencies(monkeypatch, events):
    monkeypatch.setattr("app.services.pdf_lab_parser.pdfplumber.open", lambda *_args, **_kwargs: _DummyPdf())
    monkeypatch.setattr("app.services.pdf_lab_parser.detect_answer_color", lambda _pdf: None)
    monkeypatch.setattr("app.services.pdf_lab_parser._extract_lab_events", lambda _pdf, _color: events)
    monkeypatch.setattr("app.services.pdf_lab_parser._merge_lab_orphan_labels", lambda value: value)
    monkeypatch.setattr("app.services.pdf_lab_parser.save_image_crop", lambda *_args, **_kwargs: "img.png")


def test_build_crop_lookup_prefers_existing_single_part_and_normalizes_keys(tmp_path):
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()
    (crops_dir / "Q01_p03_part1.png").write_bytes(b"png")
    (crops_dir / "Q02_merged.png").write_bytes(b"png")
    (crops_dir / "bboxes.json").write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "qnum": 1,
                        "parts": [{"image": "Q01_p03_part1.png"}],
                    },
                    {
                        "qnum": 2,
                        "parts": [
                            {"image": "Q02_p03_part1.png"},
                            {"image": "Q02_p04_part2.png"},
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lookup = _build_crop_lookup(crops_dir)

    assert lookup == {
        "1": "Q01_p03_part1.png",
        "2": "Q02_merged.png",
    }


def test_finalize_question_restores_subitem_line_breaks():
    question = {
        "question_number": 39,
        "content_lines": [
            "다음 설명중 옳은 것은?",
            "가. CD4는 class II MHC에 선택적으로 결합한다",
            "나. CTLA-4 는 B7-1과 B7-2 둘 다 결합한다",
            "다. CD4/CD8은 MHC 분자의 non-polymorphic region에 결합한다",
        ],
        "image_path": None,
        "examiner": None,
        "options_map": {
            1: {
                "number": 1,
                "chunks": [{"text": "가,나,다", "has_key": True, "x0": 10.0}],
                "image_path": None,
                "label_has_key": True,
            },
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [],
    }

    finalized = _finalize_question(question, max_option_number=16)

    assert "\n가." in finalized["content"]
    assert "\n나." in finalized["content"]
    assert finalized["answer_options"] == [1]


def test_finalize_question_repairs_shifted_sentence_tail_and_answer_flags():
    question = {
        "question_number": 20,
        "content_lines": ["IL-2의 역할과 그 수용체에 대한 설명으로 옳은 것을 모두 고르시오 (2가지 )"],
        "image_path": None,
        "examiner": None,
        "options_map": {
            1: {
                "number": 1,
                "chunks": [{"text": "첫째 선지", "has_key": False, "x0": 10.0}],
                "image_path": None,
                "label_has_key": False,
            },
            2: {
                "number": 2,
                "chunks": [{"text": "증가한", "has_key": True, "x0": 10.0}],
                "image_path": None,
                "label_has_key": True,
            },
            3: {
                "number": 3,
                "chunks": [{"text": "다", "has_key": True, "x0": 10.0}],
                "image_path": None,
                "label_has_key": True,
            },
            4: {
                "number": 4,
                "chunks": [{"text": "Resting T cell 설명", "has_key": True, "x0": 10.0}],
                "image_path": None,
                "label_has_key": True,
            },
            5: {
                "number": 5,
                "chunks": [{"text": "마지막 선지", "has_key": False, "x0": 10.0}],
                "image_path": None,
                "label_has_key": False,
            },
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [],
    }

    finalized = _finalize_question(question, max_option_number=16)
    options = {option["number"]: option for option in finalized["options"]}

    assert options[2]["content"] == "증가한다"
    assert options[3]["content"] == "Resting T cell 설명"
    assert finalized["answer_options"] == [2, 3]


def test_finalize_question_recovers_sparse_image_only_options():
    question = {
        "question_number": 1,
        "content_lines": ["아래 그림에서 Th17 T cell pathway에 의해 activation 되는 세포 두 종"],
        "image_path": None,
        "examiner": None,
        "options_map": {
            1: {
                "number": 1,
                "chunks": [{"text": "류를 고르시오. (2가지)", "has_key": False, "x0": 10.0}],
                "image_path": "img1.png",
                "label_has_key": False,
            },
            3: {"number": 3, "chunks": [], "image_path": "img3.png", "label_has_key": False},
            5: {"number": 5, "chunks": [], "image_path": "img5.png", "label_has_key": True},
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [
            {"page": 1, "top": 10.0, "image_path": "img1.png"},
            {"page": 1, "top": 20.0, "image_path": "img2.png"},
            {"page": 1, "top": 30.0, "image_path": "img3.png"},
            {"page": 1, "top": 40.0, "image_path": "img4.png"},
            {"page": 1, "top": 50.0, "image_path": "img5.png"},
        ],
    }

    finalized = _finalize_question(question, max_option_number=16)

    assert [option["number"] for option in finalized["options"]] == [1, 2, 3, 4, 5]
    assert finalized["options"][1]["image_path"] == "img2.png"
    assert finalized["options"][3]["image_path"] == "img4.png"
    assert "류를 고르시오" in finalized["content"]


def test_finalize_question_moves_incomplete_suffix_to_next_option():
    question = {
        "question_number": 24,
        "content_lines": ["Gut immune response와 관련한 면역반응에 대한 설명으로 옳은 것을 모두 고르시오. (2가지)"],
        "image_path": None,
        "examiner": None,
        "options_map": {
            2: {
                "number": 2,
                "chunks": [
                    {
                        "text": "Ag delivery를 위하여 특별한 세포인 Paneth cell이 존재하며 항원을 uptake하여 직접 T",
                        "has_key": False,
                        "x0": 10.0,
                        "from_label": True,
                    },
                    {
                        "text": "cell에 present 한다",
                        "has_key": False,
                        "x0": 20.0,
                        "from_label": False,
                    },
                    {
                        "text": "침범하는 대장균을 가능한 빨리 검색하기 위하여 대장점막 세포의 intestinal lumen 쪽에",
                        "has_key": False,
                        "x0": 20.0,
                        "from_label": False,
                    },
                ],
                "image_path": None,
                "label_has_key": False,
            },
            3: {
                "number": 3,
                "chunks": [
                    {
                        "text": "TLR-4의 발현이 특히 높다",
                        "has_key": False,
                        "x0": 10.0,
                        "from_label": True,
                    },
                ],
                "image_path": None,
                "label_has_key": False,
            },
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [],
    }

    finalized = _finalize_question(question, max_option_number=20)
    options = {option["number"]: option for option in finalized["options"]}

    assert options[2]["content"].endswith("cell에 present 한다")
    assert options[3]["content"].startswith("침범하는 대장균을")
    assert options[3]["content"].endswith("TLR-4의 발현이 특히 높다")


def test_finalize_question_moves_incomplete_trailing_line_before_short_label_without_dropping_last_option():
    question = {
        "question_number": 20,
        "content_lines": ["IL-2의 역할과 그 수용체에 대한 설명으로 옳은 것을 모두 고르시오 (2가지 )"],
        "image_path": None,
        "examiner": None,
        "options_map": {
            1: {
                "number": 1,
                "chunks": [{"text": "첫째 선지", "has_key": False, "x0": 10.0, "from_label": True}],
                "image_path": None,
                "label_has_key": False,
            },
            2: {
                "number": 2,
                "chunks": [
                    {
                        "text": "T cell의 주요 성장인자이며 CD4+보다 CD8+T cell에 의해 더 많이 생산된다.",
                        "has_key": True,
                        "x0": 10.0,
                        "from_label": True,
                    },
                    {
                        "text": "IL-2 receptor CD25가 발현되면 IL-2에 대한 affinity가 100배 정도 증가한",
                        "has_key": True,
                        "x0": 20.0,
                        "from_label": False,
                    },
                ],
                "image_path": None,
                "label_has_key": True,
            },
            3: {
                "number": 3,
                "chunks": [{"text": "다", "has_key": True, "x0": 10.0, "from_label": True}],
                "image_path": None,
                "label_has_key": True,
            },
            4: {
                "number": 4,
                "chunks": [{"text": "Resting T cell 설명", "has_key": True, "x0": 10.0, "from_label": True}],
                "image_path": None,
                "label_has_key": True,
            },
            5: {
                "number": 5,
                "chunks": [{"text": "마지막 선지", "has_key": False, "x0": 10.0, "from_label": True}],
                "image_path": None,
                "label_has_key": False,
            },
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [],
    }

    finalized = _finalize_question(question, max_option_number=20)

    assert [option["number"] for option in finalized["options"]] == [1, 2, 3, 4, 5]
    options = {option["number"]: option for option in finalized["options"]}
    assert options[2]["content"].endswith("더 많이 생산된다.")
    assert options[3]["content"] == "IL-2 receptor CD25가 발현되면 IL-2에 대한 affinity가 100배 정도 증가한다"
    assert finalized["answer_options"] == [2, 3, 4]


def test_compound_subquestion_stem_detection():
    assert _is_compound_subquestion_stem("1), 2), 3) 3개의 문항에 답하시오. (각 0.5점)") is True
    assert _is_compound_subquestion_stem("1. 2. 3. 3개의 문항에 답하시오") is True
    assert _is_compound_subquestion_stem("아래 보기에서 옳은 것을 고르시오") is False


def test_match_option_line_supports_17th_choice_when_max_is_raised():
    assert _match_option_line("17) Trichosporon beigelii", 20) == (
        17,
        ")",
        "Trichosporon beigelii",
    )
    assert _match_option_line("17) Trichosporon beigelii", 16) is None


def test_parse_pdf_to_lab_questions_promotes_existing_options_when_compound_stem_finishes_later(
    monkeypatch,
    tmp_path,
):
    events = [
        {"type": "text", "text": "6. 다음 물음에 답하시오.", "page": 1, "x0": 10.0, "top": 10.0, "has_key": False},
        {"type": "text", "text": "1) 첫째", "page": 1, "x0": 10.0, "top": 20.0, "has_key": False},
        {"type": "text", "text": "2) 둘째", "page": 1, "x0": 10.0, "top": 30.0, "has_key": False},
        {"type": "text", "text": "3) 셋째 문항에 답하시오", "page": 1, "x0": 10.0, "top": 40.0, "has_key": False},
        {"type": "text", "text": "정답: 1,2,3", "page": 1, "x0": 10.0, "top": 50.0, "has_key": True},
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert len(parsed) == 1
    assert parsed[0]["options"] == []
    assert "\n1) 첫째" in parsed[0]["content"]
    assert "\n2) 둘째" in parsed[0]["content"]
    assert "\n3) 셋째 문항에 답하시오" in parsed[0]["content"]
    assert parsed[0]["answer_text"] == "정답: 1,2,3"


def test_parse_pdf_to_lab_questions_does_not_flip_to_answer_mode_on_numbered_key_line(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "7. 1), 2), 3) 3개의 문항에 답하시오",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "1) 파란 강조가 있는 서브문항",
            "page": 1,
            "x0": 10.0,
            "top": 20.0,
            "has_key": True,
        },
        {
            "type": "text",
            "text": "2) 실제로는 아직 문제 본문",
            "page": 1,
            "x0": 10.0,
            "top": 30.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "정답: 2",
            "page": 1,
            "x0": 10.0,
            "top": 40.0,
            "has_key": True,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert len(parsed) == 1
    assert parsed[0]["options"] == []
    assert "\n1) 파란 강조가 있는 서브문항" in parsed[0]["content"]
    assert "\n2) 실제로는 아직 문제 본문" in parsed[0]["content"]
    assert parsed[0]["answer_text"] == "정답: 2"


def test_finalize_question_keeps_multiline_english_stem_in_question_content():
    question = {
        "question_number": 12,
        "content_lines": [
            "The following is true about renal blood flow",
            "during exercise",
        ],
        "image_path": None,
        "examiner": None,
        "options_map": {
            1: {
                "number": 1,
                "chunks": [
                    {
                        "text": "increases in the cortex",
                        "has_key": False,
                        "x0": 10.0,
                        "from_label": True,
                    }
                ],
                "image_path": None,
                "label_has_key": False,
            }
        },
        "answer_lines": [],
        "question_x0": 0.0,
        "option_x0": 20.0,
        "image_events": [],
    }

    finalized = _finalize_question(question, max_option_number=20)

    assert finalized["content"] == "The following is true about renal blood flow during exercise"
    assert finalized["options"][0]["content"] == "increases in the cortex"


def test_parse_pdf_to_lab_questions_treats_mapping_answer_line_as_compound_answer(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "8. 1), 2), 3) 3개의 문항에 답하시오",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "1) 첫째 설명",
            "page": 1,
            "x0": 10.0,
            "top": 20.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "2) 둘째 설명",
            "page": 1,
            "x0": 10.0,
            "top": 30.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "A: 1 B: 2",
            "page": 1,
            "x0": 10.0,
            "top": 40.0,
            "has_key": True,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert len(parsed) == 1
    assert parsed[0]["options"] == []
    assert "\n1) 첫째 설명" in parsed[0]["content"]
    assert "\n2) 둘째 설명" in parsed[0]["content"]
    assert "A: 1 B: 2" not in parsed[0]["content"]
    assert parsed[0]["answer_text"] == "A: 1 B: 2"


def test_parse_pdf_to_lab_questions_marks_option_correct_when_only_label_is_colored(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "1. 보기에서 맞는 것을 고르시오",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "1) 정답 선지",
            "page": 1,
            "x0": 20.0,
            "top": 20.0,
            "has_key": True,
            "body_has_key": False,
            "label_has_key": True,
        },
        {
            "type": "text",
            "text": "2) 오답 선지",
            "page": 1,
            "x0": 20.0,
            "top": 30.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert len(parsed) == 1
    assert parsed[0]["answer_options"] == [1]
    assert parsed[0]["answer_text"] == "정답 선지"


def test_parse_pdf_to_lab_questions_merges_rank_prefixed_indented_line_into_following_option(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "10. How does the proximal tubule handle bicarbonate?",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "1) First option",
            "page": 1,
            "x0": 10.0,
            "top": 20.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "2) Second option",
            "page": 1,
            "x0": 10.0,
            "top": 30.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "3) Third option",
            "page": 1,
            "x0": 10.0,
            "top": 40.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "1. Bicarbonate combines with a proton in the lumen and is",
            "page": 1,
            "x0": 40.0,
            "top": 50.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
        {
            "type": "text",
            "text": "4) converted to carbon dioxide and water.",
            "page": 1,
            "x0": 10.0,
            "top": 58.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
        {
            "type": "text",
            "text": "5) Fifth option",
            "page": 1,
            "x0": 10.0,
            "top": 70.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    options = {option["number"]: option for option in parsed[0]["options"]}
    assert options[1]["content"] == "First option"
    assert (
        options[4]["content"]
        == "Bicarbonate combines with a proton in the lumen and is converted to carbon dioxide and water."
    )
    assert parsed[0]["answer_options"] == [4]


def test_parse_pdf_to_lab_questions_merges_indented_line_before_short_next_label(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "33. 갑상선 문제",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "1) 첫째",
            "page": 1,
            "x0": 10.0,
            "top": 20.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "2) 둘째",
            "page": 1,
            "x0": 10.0,
            "top": 30.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "3) 셋째",
            "page": 1,
            "x0": 10.0,
            "top": 40.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "4) 하시모토 갑상선염",
            "page": 1,
            "x0": 10.0,
            "top": 50.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "선천성 갑상선 과산화효소 결핍에 의한 갑상선 기능",
            "page": 1,
            "x0": 30.0,
            "top": 60.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "5) 저하",
            "page": 1,
            "x0": 10.0,
            "top": 68.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    options = {option["number"]: option for option in parsed[0]["options"]}
    assert options[4]["content"] == "하시모토 갑상선염"
    assert options[5]["content"].startswith("선천성 갑상선 과산화효소 결핍에 의한 갑상선 기능")
    assert options[5]["content"].endswith("저하")
    assert parsed[0]["answer_options"] == [5]


def test_parse_pdf_to_lab_questions_strips_duplicate_rank_prefix_inside_option_line(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "20. 물을 많이 마신 뒤 변화는?",
            "page": 1,
            "x0": 10.0,
            "top": 10.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "1) 1. Aquaporin-2 expression in the collecting duct decreased",
            "page": 1,
            "x0": 10.0,
            "top": 20.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
        {
            "type": "text",
            "text": "2) 1. End proximal tubule fluid became dilute",
            "page": 1,
            "x0": 10.0,
            "top": 30.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
        {
            "type": "text",
            "text": "3) 1. Glomerular filtration rate (GFR) increased",
            "page": 1,
            "x0": 10.0,
            "top": 40.0,
            "has_key": False,
            "body_has_key": False,
            "label_has_key": False,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    options = {option["number"]: option for option in parsed[0]["options"]}
    assert options[1]["content"] == "Aquaporin-2 expression in the collecting duct decreased"
    assert options[2]["content"] == "End proximal tubule fluid became dilute"
    assert options[3]["content"] == "Glomerular filtration rate (GFR) increased"
    assert parsed[0]["answer_options"] == [1]


def test_detect_page_panels_finds_box_and_classifies_banner_by_geometry():
    page = _DummyPage(
        22,
        lines=[
            {
                "x0": 89.38,
                "x1": 89.38,
                "top": 543.51,
                "bottom": 572.20,
                "linewidth": 0.75,
                "stroking_color": (0.6, 0.6, 0.6),
            },
            {
                "x0": 89.38,
                "x1": 519.63,
                "top": 543.51,
                "bottom": 543.51,
                "linewidth": 0.75,
                "stroking_color": (0.6, 0.6, 0.6),
            },
            {
                "x0": 519.63,
                "x1": 519.63,
                "top": 543.51,
                "bottom": 572.20,
                "linewidth": 0.75,
                "stroking_color": (0.6, 0.6, 0.6),
            },
            {
                "x0": 89.38,
                "x1": 519.63,
                "top": 572.20,
                "bottom": 572.20,
                "linewidth": 0.75,
                "stroking_color": (0.6, 0.6, 0.6),
            },
            {
                "x0": 50.0,
                "x1": 524.5,
                "top": 473.05,
                "bottom": 473.05,
                "linewidth": 0.75,
                "stroking_color": (0.86667, 0.86667, 0.86667),
            },
        ],
    )

    panels = _detect_page_panels(page)

    assert len(panels) == 1
    assert panels[0]["panel_id"] == "p22-panel1"
    assert panels[0]["kind"] == "banner"
    assert panels[0]["bbox"] == (89.38, 543.51, 519.63, 572.2)


def test_parse_pdf_to_lab_questions_keeps_banner_box_as_separate_paragraph(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "73. 혈액검사 소견을 보고 질문에 답하시오.",
            "page": 1,
            "x0": 53.0,
            "top": 543.7,
            "x1": 282.5,
            "bottom": 564.3,
            "has_key": False,
            "inside_panel": True,
            "panel_id": "p1-panel1",
            "panel_kind": "banner",
        },
        {
            "type": "text",
            "text": "65세 남자가 코피가 잘 멎지 않아서 병원에 왔다.",
            "page": 1,
            "x0": 89.0,
            "top": 590.0,
            "x1": 400.0,
            "bottom": 604.0,
            "has_key": False,
            "inside_panel": False,
            "panel_id": None,
            "panel_kind": None,
        },
        {
            "type": "text",
            "text": "1) 알콜중독",
            "page": 1,
            "x0": 89.0,
            "top": 640.0,
            "x1": 180.0,
            "bottom": 654.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "2) vitamin K 결핍",
            "page": 1,
            "x0": 89.0,
            "top": 660.0,
            "x1": 220.0,
            "bottom": 674.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert parsed[0]["content"] == (
        "혈액검사 소견을 보고 질문에 답하시오.\n\n"
        "65세 남자가 코피가 잘 멎지 않아서 병원에 왔다."
    )
    assert [block["type"] for block in parsed[0]["content_blocks"][:2]] == [
        "banner_text",
        "stem_text",
    ]
    assert parsed[0]["answer_options"] == [2]


def test_parse_pdf_to_lab_questions_keeps_mid_stem_panel_as_distinct_block(
    monkeypatch,
    tmp_path,
):
    events = [
        {
            "type": "text",
            "text": "36. 쿠싱증후군 환자이다.",
            "page": 1,
            "x0": 89.0,
            "top": 80.0,
            "x1": 260.0,
            "bottom": 94.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "다음은 이 환자의 검사소견이다.",
            "page": 1,
            "x0": 89.0,
            "top": 110.0,
            "x1": 300.0,
            "bottom": 124.0,
            "has_key": False,
        },
        {
            "type": "text",
            "text": "24시간 소변내 cortisol 249 μg/24 h",
            "page": 1,
            "x0": 97.0,
            "top": 170.0,
            "x1": 330.0,
            "bottom": 184.0,
            "has_key": False,
            "inside_panel": True,
            "panel_id": "p1-panel1",
            "panel_kind": "panel",
        },
        {
            "type": "image",
            "page": 1,
            "x0": 87.5,
            "top": 263.27,
            "x1": 372.5,
            "bottom": 524.4,
            "page_obj": None,
            "inside_panel": False,
            "panel_id": None,
            "panel_kind": None,
        },
        {
            "type": "text",
            "text": "1) 복부 CT 검사를 시행한다",
            "page": 1,
            "x0": 89.0,
            "top": 550.0,
            "x1": 260.0,
            "bottom": 564.0,
            "has_key": True,
            "body_has_key": True,
            "label_has_key": True,
        },
        {
            "type": "text",
            "text": "2) 뇌하수체 MRI 검사",
            "page": 1,
            "x0": 89.0,
            "top": 570.0,
            "x1": 240.0,
            "bottom": 584.0,
            "has_key": False,
        },
    ]
    _patch_parse_dependencies(monkeypatch, events)

    parsed = parse_pdf_to_lab_questions("dummy.pdf", tmp_path, "lab")

    assert parsed[0]["content"] == (
        "쿠싱증후군 환자이다. 다음은 이 환자의 검사소견이다.\n\n"
        "24시간 소변내 cortisol 249 μg/24 h"
    )
    assert [block["type"] for block in parsed[0]["content_blocks"][:3]] == [
        "stem_text",
        "panel_text",
        "stem_image",
    ]
    assert parsed[0]["content_blocks"][2]["image_path"] == "img.png"
    assert parsed[0]["answer_options"] == [1]
