from scripts.pdf_lab import analyze_parse_result, build_diff_report


def test_analyze_parse_result_detects_key_anomalies():
    questions = [
        {
            "question_number": 1,
            "content": "",
            "image_path": None,
            "options": [{"number": 1, "content": "", "image_path": None}],
            "answer_options": [2],
            "answer_text": "",
        },
        {
            "question_number": 1,
            "content": "duplicate",
            "image_path": None,
            "options": [],
            "answer_options": [],
            "answer_text": "",
        },
    ]

    anomalies = analyze_parse_result(questions, max_option_number=5)
    codes = {item["code"] for item in anomalies}

    assert "EMPTY_QUESTION_CONTENT" in codes
    assert "EMPTY_OPTION_CONTENT" in codes
    assert "ANSWER_OPTION_MISSING" in codes
    assert "DUPLICATE_QUESTION_NUMBER" in codes


def test_build_diff_report_tracks_added_removed_and_changed():
    baseline = [
        {
            "question_number": 1,
            "content": "alpha",
            "image_path": None,
            "options": [{"number": 1, "content": "A", "is_correct": True}],
            "answer_options": [1],
            "answer_text": "A",
        },
        {
            "question_number": 2,
            "content": "beta",
            "image_path": None,
            "options": [],
            "answer_options": [],
            "answer_text": "x",
        },
    ]
    current = [
        {
            "question_number": 1,
            "content": "alpha updated",
            "image_path": None,
            "options": [{"number": 1, "content": "A", "is_correct": False}],
            "answer_options": [],
            "answer_text": "",
        },
        {
            "question_number": 3,
            "content": "gamma",
            "image_path": None,
            "options": [],
            "answer_options": [],
            "answer_text": "",
        },
    ]

    diff = build_diff_report(current, baseline)

    assert diff["summary"] == {"added": 1, "removed": 1, "changed": 1}
    assert diff["added_questions"] == [3]
    assert diff["removed_questions"] == [2]
    assert diff["changed_questions"][0]["question_number"] == 1
    assert "content" in diff["changed_questions"][0]["changed_fields"]
    assert "answer_options" in diff["changed_questions"][0]["changed_fields"]
