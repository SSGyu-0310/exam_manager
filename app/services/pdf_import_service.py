from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app import db
from app.models import Choice, Question


def _resolve_crop_image_name(
    crop_question_images: Mapping[Any, Any], question_number: int
) -> Optional[str]:
    image_name = crop_question_images.get(question_number)
    if image_name is None:
        image_name = crop_question_images.get(str(question_number))
    if not image_name:
        return None
    return str(image_name)


def _resolve_question_image_path(
    exam_id: int,
    question_number: int,
    parser_image_path: Optional[str],
    crop_question_images: Mapping[Any, Any],
    crop_is_reliable: bool,
) -> Optional[str]:
    crop_image_name = _resolve_crop_image_name(crop_question_images, question_number)
    if crop_is_reliable and crop_image_name:
        return (Path("exam_crops") / f"exam_{exam_id}" / crop_image_name).as_posix()
    return parser_image_path


def _determine_question_type(question_data: Mapping[str, Any]) -> str:
    answer_count = len(question_data.get("answer_options", []))
    has_options = len(question_data.get("options", [])) > 0
    if not has_options:
        return Question.TYPE_SHORT_ANSWER
    if answer_count > 1:
        return Question.TYPE_MULTIPLE_RESPONSE
    return Question.TYPE_MULTIPLE_CHOICE


def save_parsed_questions(
    *,
    exam_id: int,
    user_id: int,
    questions_data: Sequence[Mapping[str, Any]],
    crop_question_images: Optional[Mapping[Any, Any]] = None,
    crop_is_reliable: bool = False,
) -> tuple[int, int]:
    crop_images = crop_question_images or {}
    question_count = 0
    choice_count = 0
    seen_question_numbers: set[int] = set()

    for question_data in questions_data:
        question_number = int(question_data["question_number"])
        if question_number in seen_question_numbers:
            raise ValueError(
                f"Duplicate question number detected in parsed result: {question_number}"
            )
        seen_question_numbers.add(question_number)

        option_numbers = set()
        for option in question_data.get("options", []):
            option_number = int(option["number"])
            if option_number in option_numbers:
                raise ValueError(
                    f"Duplicate choice number detected in question {question_number}: "
                    f"{option_number}"
                )
            option_numbers.add(option_number)

        if option_numbers:
            for answer_option in question_data.get("answer_options", []):
                if int(answer_option) not in option_numbers:
                    raise ValueError(
                        f"Answer option {answer_option} does not exist in "
                        f"question {question_number} choices."
                    )

        question_image_path = _resolve_question_image_path(
            exam_id=exam_id,
            question_number=question_number,
            parser_image_path=question_data.get("image_path"),
            crop_question_images=crop_images,
            crop_is_reliable=crop_is_reliable,
        )
        question_type = _determine_question_type(question_data)

        question = Question(
            exam_id=exam_id,
            user_id=user_id,
            question_number=question_number,
            content=question_data.get("content", ""),
            image_path=question_image_path,
            examiner=question_data.get("examiner"),
            q_type=question_type,
            answer=",".join(map(str, question_data.get("answer_options", []))),
            correct_answer_text=question_data.get("answer_text")
            if question_type == Question.TYPE_SHORT_ANSWER
            else None,
            explanation=question_data.get("answer_text")
            if question_type != Question.TYPE_SHORT_ANSWER
            else None,
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        for option in question_data.get("options", []):
            if option.get("content") or option.get("image_path"):
                choice = Choice(
                    question_id=question.id,
                    choice_number=option["number"],
                    content=option.get("content", ""),
                    image_path=option.get("image_path"),
                    is_correct=option.get("is_correct", False),
                )
                db.session.add(choice)
                choice_count += 1

        question_count += 1

    return question_count, choice_count
