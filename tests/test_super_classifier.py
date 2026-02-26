from __future__ import annotations

import json

import pytest

from app.services.super_classifier import _parse_super_result, _validate_super_results


class _DummyBlock:
    def __init__(self, name: str):
        self.name = name


class _DummyLecture:
    def __init__(self, title: str, block_name: str):
        self.title = title
        self.block = _DummyBlock(block_name)


class _DummyExam:
    def __init__(self, title: str):
        self.title = title


class _DummyQuestion:
    def __init__(self, lecture_id: int | None, lecture: _DummyLecture | None):
        self.lecture_id = lecture_id
        self.lecture = lecture
        self.exam = _DummyExam("Dummy Exam")


def test_parse_super_result_treats_string_false_as_false():
    lecture = _DummyLecture("순환생리", "생리학")
    question_obj = _DummyQuestion(lecture_id=None, lecture=None)
    questions = [
        {
            "id": 101,
            "question_number": 1,
            "content": "문항",
            "choices": ["보기1"],
            "question": question_obj,
        }
    ]
    lectures = [
        {
            "id": 7,
            "title": lecture.title,
            "block_name": lecture.block.name,
        }
    ]
    raw_text = json.dumps(
        [
            {
                "question_id": 101,
                "lecture_id": 7,
                "confidence": 0.92,
                "reason": "핵심 개념 일치",
                "no_match": "false",
            }
        ],
        ensure_ascii=False,
    )

    results = _parse_super_result(raw_text, questions, lectures)

    assert len(results) == 1
    assert results[0]["no_match"] is False
    assert results[0]["lecture_id"] == 7


def test_validate_super_results_raises_when_partial_results_returned():
    questions = [
        {"id": 1},
        {"id": 2},
    ]
    partial_results = [
        {"question_id": 1},
    ]

    with pytest.raises(ValueError):
        _validate_super_results(partial_results, questions)


def test_parse_super_result_recovers_from_truncated_json_array():
    lecture = _DummyLecture("미생물학 총론", "미생물학")
    questions = [
        {
            "id": 1,
            "question_number": 1,
            "content": "문항1",
            "choices": [],
            "question": _DummyQuestion(lecture_id=None, lecture=None),
        },
        {
            "id": 2,
            "question_number": 2,
            "content": "문항2",
            "choices": [],
            "question": _DummyQuestion(lecture_id=None, lecture=None),
        },
        {
            "id": 3,
            "question_number": 3,
            "content": "문항3",
            "choices": [],
            "question": _DummyQuestion(lecture_id=None, lecture=None),
        },
    ]
    lectures = [
        {
            "id": 4,
            "title": lecture.title,
            "block_name": lecture.block.name,
        }
    ]
    raw_text = """
[
  {"question_id": 1, "lecture_id": 4, "confidence": 0.9, "reason": "근거1", "no_match": false},
  {"question_id": 2, "lecture_id": 4, "confidence": 0.8, "reason": "근거2", "no_match": false},
  {"question_id": 3, "lecture_id": 4, "confidence": 0.7, "reason": "근거3
"""

    results = _parse_super_result(raw_text, questions, lectures)

    assert [result["question_id"] for result in results] == [1, 2]


def test_parse_super_result_supports_question_number_field():
    lecture = _DummyLecture("순환생리", "생리학")
    question_obj = _DummyQuestion(lecture_id=None, lecture=None)
    questions = [
        {
            "id": 101,
            "question_number": 1,
            "content": "문항",
            "choices": [],
            "question": question_obj,
        }
    ]
    lectures = [
        {
            "id": 7,
            "title": lecture.title,
            "block_name": lecture.block.name,
        }
    ]
    raw_text = json.dumps(
        [
            {
                "question_number": 1,
                "lecture_id": 7,
                "confidence": 0.91,
                "reason": "문항 번호 기반 응답",
                "no_match": False,
            }
        ],
        ensure_ascii=False,
    )

    results = _parse_super_result(raw_text, questions, lectures)

    assert len(results) == 1
    assert results[0]["question_id"] == 101
    assert results[0]["lecture_id"] == 7
