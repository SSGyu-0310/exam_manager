"""Super AI 분류 서비스 모듈

Google Gemini API (gemini-3.1-pro-preview)를 활용한 고정확도 문제-강의 분류.
강의 제목 + 강의록 전체 청크 + 시험 문제 전체를 단일 API 요청으로 보내
한 번에 모든 문제를 분류합니다.

설계 원칙:
- 시험 단위 일괄 분류를 기본으로 하되, 누락 문항이 생기면 소배치 재요청으로 복구
- BM25 검색 단계 생략 → 전체 강의록 직접 전달 → 정보 손실 없음
- 기존 ClassificationJob 모델과 호환 (결과 조회/적용 API 재사용)
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from config import get_config

# Google GenAI SDK
try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from app import db
from app.models import (
    Question,
    Lecture,
    Block,
    LectureChunk,
    PreviousExam,
    ClassificationJob,
)
from app.services.ai_classifier import (
    build_job_payload,
    parse_job_payload,
    resolve_exam_subject_lecture_ids,
)
from app.services.folder_scope import parse_bool, resolve_lecture_ids
from app.services.block_sort import block_lecture_ordering

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_SUPER_MODEL = "gemini-3.1-pro-preview"
DEFAULT_SUPER_MAX_LECTURES = 50
DEFAULT_SUPER_MAX_OUTPUT_TOKENS = 8192
DEFAULT_SUPER_MAX_PROMPT_CHARS = 500000
DEFAULT_SUPER_MAX_CHARS_PER_LECTURE = 50000
DEFAULT_SUPER_MAX_CHARS_PER_QUESTION = 6000
DEFAULT_SUPER_RETRY_BATCH_SIZE = 8


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _normalize_int_list(raw_values: Any) -> List[int]:
    if not isinstance(raw_values, (list, tuple, set)):
        return []
    normalized: List[int] = []
    for raw_value in raw_values:
        try:
            normalized.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def _truncate_text(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    trimmed = value[:max_chars].rstrip()
    return f"{trimmed}\n...[TRUNCATED]"


def _normalize_json_response_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        # Remove markdown code fences if present.
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


def _coerce_json_items(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if not isinstance(parsed, dict):
        return []

    for key in ("results", "items", "classifications", "predictions", "data"):
        value = parsed.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [parsed]


def _extract_partial_json_items(text: str) -> List[Dict[str, Any]]:
    """Recover leading valid JSON objects from a truncated JSON array string."""
    decoder = json.JSONDecoder()
    source = text
    list_start = source.find("[")
    if list_start >= 0:
        source = source[list_start + 1 :]

    items: List[Dict[str, Any]] = []
    cursor = 0
    while cursor < len(source):
        obj_start = source.find("{", cursor)
        if obj_start < 0:
            break
        try:
            parsed, consumed = decoder.raw_decode(source[obj_start:])
        except json.JSONDecodeError:
            cursor = obj_start + 1
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
        cursor = obj_start + consumed
    return items


# ============================================================
# 강의 데이터 로드
# ============================================================


def _load_lectures_with_chunks(
    lecture_ids: Optional[List[int]] = None,
    max_lectures: int = DEFAULT_SUPER_MAX_LECTURES,
    max_chars_per_lecture: int = DEFAULT_SUPER_MAX_CHARS_PER_LECTURE,
) -> List[Dict[str, Any]]:
    """전체 강의 + 청크를 로드하여 프롬프트용 데이터 구성."""
    query = (
        Lecture.query.join(Block)
        .order_by(*block_lecture_ordering())
    )
    if lecture_ids is not None:
        query = query.filter(Lecture.id.in_(lecture_ids))

    lectures = query.limit(max_lectures).all()

    result = []
    for lecture in lectures:
        chunks = (
            LectureChunk.query
            .filter(LectureChunk.lecture_id == lecture.id)
            .order_by(LectureChunk.page_start)
            .all()
        )
        if not chunks:
            continue  # 청크 없는 강의는 건너뜀

        full_text = "\n".join(c.content for c in chunks if c.content)
        if not full_text.strip():
            continue
        full_text = _truncate_text(full_text, max_chars_per_lecture)

        result.append({
            "id": lecture.id,
            "title": lecture.title,
            "block_name": lecture.block.name,
            "full_path": f"{lecture.block.name} > {lecture.title}",
            "chunk_count": len(chunks),
            "full_text": full_text,
        })

    return result


def _load_exam_questions(
    exam_id: int,
    question_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """시험의 모든 문제를 로드."""
    exam = db.session.get(PreviousExam, exam_id)
    if not exam:
        raise ValueError(f"시험을 찾을 수 없습니다: exam_id={exam_id}")

    query = Question.query.filter(Question.exam_id == exam_id)
    if question_ids is not None:
        normalized_question_ids = _normalize_int_list(question_ids)
        if not normalized_question_ids:
            return []
        query = query.filter(Question.id.in_(normalized_question_ids))
    questions = query.order_by(Question.question_number).all()

    result = []
    for q in questions:
        choices = [c.content for c in q.choices.order_by("choice_number").all()]
        result.append({
            "id": q.id,
            "question_number": q.question_number,
            "content": q.content or "",
            "choices": choices,
            "question": q,  # ORM 객체 참조 (결과 저장용)
        })

    return result


# ============================================================
# 프롬프트 빌드
# ============================================================


def _build_super_prompt(
    lectures: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    max_chars_per_question: int = DEFAULT_SUPER_MAX_CHARS_PER_QUESTION,
) -> str:
    """시험 전체 + 강의록 전체를 포함하는 분류 프롬프트 구성."""

    # 강의 목록 섹션
    lecture_sections = []
    for lec in lectures:
        lecture_sections.append(
            f"### [Lecture ID: {lec['id']}] {lec['full_path']}\n"
            f"{lec['full_text']}"
        )
    lectures_text = "\n\n".join(lecture_sections)

    # 문제 목록 섹션
    question_sections = []
    for q in questions:
        question_content = _truncate_text(
            q["content"] or "",
            max_chars_per_question,
        )
        q_text = (
            f"### [Question ID: {q['id']}] 문제 {q['question_number']}번\n"
            f"{question_content}"
        )
        if q["choices"]:
            choices_text = "\n".join(
                f"  {i + 1}. {choice}" for i, choice in enumerate(q["choices"])
            )
            q_text += f"\n보기:\n{choices_text}"
        question_sections.append(q_text)
    questions_text = "\n\n".join(question_sections)

    # 유효한 강의 ID 목록
    valid_ids = [lec["id"] for lec in lectures]

    prompt = f"""당신은 의학 시험 문제를 강의별로 분류하는 전문가입니다.
아래에 강의 목록과 각 강의의 전체 내용(강의록)이 제공됩니다.
그 아래에 시험 문제 목록이 있습니다.
각 문제를 **가장 적합한 강의 하나**에 분류해주세요.

## 분류 규칙
1. 유효한 강의 ID 목록: {valid_ids}
2. lecture_id는 반드시 위 목록에서만 선택하세요. 새로운 ID를 만들지 마세요.
3. 분류가 확실하지 않거나 어떤 강의에도 맞지 않으면 lecture_id를 null로 설정하고 no_match를 true로 해주세요.
4. confidence는 0.0~1.0 사이 값으로, 분류 확신도를 나타냅니다.
5. reason은 한국어로 간결하게 분류 근거를 작성하세요.
6. evidence_pages는 해당 강의록에서 관련 페이지 번호(있는 경우)를 포함하세요.
7. 반드시 유효한 JSON 배열만 반환하세요. 마크다운이나 추가 설명은 넣지 마세요.

## 강의 목록 및 전체 내용

{lectures_text}

## 시험 문제 목록

{questions_text}

## 응답 형식 (JSON 배열)
[
  {{
    "question_id": (문제 ID, 숫자),
    "lecture_id": (선택한 강의 ID 숫자 또는 null),
    "confidence": (0.0~1.0),
    "reason": "한국어 분류 근거",
    "no_match": (true/false),
    "evidence_pages": [페이지 번호 목록]
  }},
  ...
]
"""
    return prompt


# ============================================================
# 결과 파싱
# ============================================================


def _parse_super_result(
    raw_text: str,
    questions: List[Dict[str, Any]],
    lectures: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Gemini 응답을 파싱하여 기존 결과 형식으로 변환."""
    valid_lecture_ids = {lec["id"] for lec in lectures}
    lecture_map = {lec["id"]: lec for lec in lectures}
    candidate_ids = [lec["id"] for lec in lectures]
    question_map = {q["id"]: q for q in questions}
    question_number_map = {
        int(q["question_number"]): int(q["id"])
        for q in questions
        if q.get("question_number") is not None and q.get("id") is not None
    }

    text = _normalize_json_response_text(raw_text)
    parsed_items: List[Dict[str, Any]] = []

    try:
        parsed_items = _coerce_json_items(json.loads(text))
    except json.JSONDecodeError:
        # First, try extracting array substring.
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                parsed_items = _coerce_json_items(json.loads(text[start:end + 1]))
            except json.JSONDecodeError:
                parsed_items = []
        # Finally, recover leading valid objects from truncated JSON.
        if not parsed_items:
            parsed_items = _extract_partial_json_items(text)

    if not parsed_items:
        logger.error("SUPER_CLASSIFIER_PARSE_FAILED text=%s", text[:1000])
        return []

    def _resolve_question_id(item: Dict[str, Any]) -> Optional[int]:
        nested_question = item.get("question")
        id_candidates = [
            item.get("question_id"),
            item.get("questionId"),
            item.get("id"),
        ]
        if isinstance(nested_question, dict):
            id_candidates.extend(
                [
                    nested_question.get("question_id"),
                    nested_question.get("questionId"),
                    nested_question.get("id"),
                ]
            )
        for raw_value in id_candidates:
            try:
                question_id = int(raw_value)
            except (TypeError, ValueError):
                continue
            if question_id in question_map:
                return question_id

        number_candidates = [
            item.get("question_number"),
            item.get("questionNumber"),
            item.get("question_no"),
            item.get("questionNo"),
            item.get("number"),
        ]
        if isinstance(nested_question, dict):
            number_candidates.extend(
                [
                    nested_question.get("question_number"),
                    nested_question.get("questionNumber"),
                    nested_question.get("number"),
                ]
            )
        for raw_value in number_candidates:
            try:
                question_number = int(raw_value)
            except (TypeError, ValueError):
                continue
            question_id = question_number_map.get(question_number)
            if question_id is not None:
                return question_id
        return None

    def _parse_evidence_pages(raw_value: Any) -> List[int]:
        if isinstance(raw_value, list):
            pages: List[int] = []
            for page in raw_value:
                try:
                    pages.append(int(page))
                except (TypeError, ValueError):
                    continue
            return pages
        return []

    def _build_result_entry(
        q_data: Dict[str, Any],
        *,
        lecture_id: Optional[int],
        no_match: bool,
        confidence: float,
        reason: str,
        evidence_pages: List[int],
    ) -> Dict[str, Any]:
        lecture_info = lecture_map.get(lecture_id) if lecture_id else None
        lecture_title = lecture_info["title"] if lecture_info else None
        block_name = lecture_info["block_name"] if lecture_info else None

        question_obj = q_data["question"]
        current_lecture = question_obj.lecture
        current_lecture_id = question_obj.lecture_id
        current_lecture_title = (
            f"{current_lecture.block.name} > {current_lecture.title}"
            if current_lecture
            else None
        )
        current_block_name = (
            current_lecture.block.name if current_lecture else None
        )

        return {
            "question_id": int(q_data["id"]),
            "question_number": q_data["question_number"],
            "exam_title": (
                question_obj.exam.title if question_obj.exam else ""
            ),
            "question_content": q_data["content"],
            "question_choices": q_data["choices"],
            "current_lecture_id": current_lecture_id,
            "current_lecture_title": current_lecture_title,
            "current_block_name": current_block_name,
            "lecture_id": lecture_id,
            "lecture_title": lecture_title,
            "block_name": block_name,
            "confidence": confidence,
            "reason": reason,
            "study_hint": "",
            "evidence": [],  # super 분류는 chunk 단위 evidence 없음
            "evidence_pages": evidence_pages,
            "no_match": no_match,
            "model_name": _env_str("SUPER_CLASSIFY_MODEL", DEFAULT_SUPER_MODEL),
            "decision_mode": "no_match" if no_match else "strict_match",
            "rejudge_attempted": False,
            "rejudge_decision_mode": None,
            "rejudge_confidence": None,
            "rejudge_reason": None,
            "final_decision_source": "super",
            "response_omitted": False,
            "candidate_ids": candidate_ids,
            "will_change": bool(
                lecture_id and lecture_id != current_lecture_id
            ),
            "error": False,
        }

    results = []
    for item in parsed_items:
        question_id = _resolve_question_id(item)
        if question_id is None:
            continue

        q_data = question_map.get(question_id)
        if not q_data:
            continue

        lecture_id = item.get("lecture_id")
        if lecture_id is None:
            lecture_id = item.get("lectureId")
        no_match = parse_bool(
            item.get("no_match", item.get("noMatch")),
            False,
        )

        if lecture_id is not None:
            try:
                lecture_id = int(lecture_id)
            except (TypeError, ValueError):
                lecture_id = None

        if lecture_id is not None and lecture_id not in valid_lecture_ids:
            lecture_id = None
            no_match = True

        if no_match:
            lecture_id = None
        if lecture_id is None and not no_match:
            no_match = True

        raw_confidence = item.get("confidence", item.get("score", 0.0))
        try:
            if isinstance(raw_confidence, str) and raw_confidence.endswith("%"):
                confidence = float(raw_confidence.rstrip("%")) / 100.0
            else:
                confidence = float(raw_confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.0

        reason = str(item.get("reason") or item.get("rationale") or "")
        evidence_pages = _parse_evidence_pages(
            item.get("evidence_pages", item.get("evidencePages"))
        )
        results.append(
            _build_result_entry(
                q_data,
                lecture_id=lecture_id,
                no_match=no_match,
                confidence=confidence,
                reason=reason,
                evidence_pages=evidence_pages,
            )
        )

    return results


def _missing_super_question_ids(
    results: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
) -> List[int]:
    expected_ids = {
        int(question["id"])
        for question in questions
        if question.get("id") is not None
    }
    matched_ids: set[int] = set()
    for result in results:
        raw_question_id = result.get("question_id")
        if raw_question_id is None:
            continue
        try:
            matched_ids.add(int(raw_question_id))
        except (TypeError, ValueError):
            continue
    return sorted(expected_ids - matched_ids)


def _build_super_no_match_result(
    question_data: Dict[str, Any],
    lectures: List[Dict[str, Any]],
    *,
    reason: str,
    candidate_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    question_obj = question_data["question"]
    current_lecture = question_obj.lecture
    current_lecture_id = question_obj.lecture_id
    current_lecture_title = (
        f"{current_lecture.block.name} > {current_lecture.title}"
        if current_lecture
        else None
    )
    current_block_name = current_lecture.block.name if current_lecture else None
    return {
        "question_id": int(question_data["id"]),
        "question_number": question_data["question_number"],
        "exam_title": question_obj.exam.title if question_obj.exam else "",
        "question_content": question_data["content"],
        "question_choices": question_data["choices"],
        "current_lecture_id": current_lecture_id,
        "current_lecture_title": current_lecture_title,
        "current_block_name": current_block_name,
        "lecture_id": None,
        "lecture_title": None,
        "block_name": None,
        "confidence": 0.0,
        "reason": reason,
        "study_hint": "",
        "evidence": [],
        "evidence_pages": [],
        "no_match": True,
        "model_name": _env_str("SUPER_CLASSIFY_MODEL", DEFAULT_SUPER_MODEL),
        "decision_mode": "no_match",
        "rejudge_attempted": False,
        "rejudge_decision_mode": None,
        "rejudge_confidence": None,
        "rejudge_reason": None,
        "final_decision_source": "super",
        "response_omitted": True,
        "candidate_ids": (
            candidate_ids
            if candidate_ids is not None
            else [lec["id"] for lec in lectures]
        ),
        "will_change": bool(current_lecture_id),
        "error": False,
    }


def _validate_super_results(
    results: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
) -> None:
    expected_ids = {
        int(question["id"])
        for question in questions
        if question.get("id") is not None
    }
    matched_ids: set[int] = set()
    duplicate_ids: set[int] = set()
    for result in results:
        raw_question_id = result.get("question_id")
        if raw_question_id is None:
            continue
        try:
            question_id = int(raw_question_id)
        except (TypeError, ValueError):
            continue
        if question_id in matched_ids:
            duplicate_ids.add(question_id)
        matched_ids.add(question_id)

    if duplicate_ids:
        logger.warning(
            "SUPER_CLASSIFY_DUPLICATE_RESULTS question_ids=%s",
            sorted(duplicate_ids),
        )

    missing_ids = sorted(expected_ids - matched_ids)
    if missing_ids:
        preview = missing_ids[:10]
        raise ValueError(
            "분류 결과가 불완전합니다. "
            f"expected={len(expected_ids)} got={len(matched_ids)} "
            f"missing_preview={preview}"
        )


# ============================================================
# Super 분류 실행
# ============================================================


class SuperClassifier:
    """전체 강의록 기반 고정확도 분류기 (gemini-3.1-pro-preview)."""

    _executor = ThreadPoolExecutor(max_workers=1)

    def __init__(self):
        if not GENAI_AVAILABLE:
            raise RuntimeError(
                "google-genai 패키지가 설치되지 않았습니다. pip install google-genai 실행하세요."
            )

        cfg = get_config()
        api_key = (
            cfg.runtime.gemini_api_key or os.environ.get("GOOGLE_API_KEY") or ""
        ).strip()
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되지 않았습니다."
            )

        self.client = genai.Client(api_key=api_key)
        self.model_name = _env_str("SUPER_CLASSIFY_MODEL", DEFAULT_SUPER_MODEL)
        self.max_lectures = _env_int(
            "SUPER_CLASSIFY_MAX_LECTURES", DEFAULT_SUPER_MAX_LECTURES
        )
        self.max_output_tokens = _env_int(
            "SUPER_CLASSIFY_MAX_OUTPUT_TOKENS", DEFAULT_SUPER_MAX_OUTPUT_TOKENS
        )
        self.max_prompt_chars = _env_int(
            "SUPER_CLASSIFY_MAX_PROMPT_CHARS", DEFAULT_SUPER_MAX_PROMPT_CHARS
        )
        self.max_chars_per_lecture = _env_int(
            "SUPER_CLASSIFY_MAX_CHARS_PER_LECTURE",
            DEFAULT_SUPER_MAX_CHARS_PER_LECTURE,
        )
        self.max_chars_per_question = _env_int(
            "SUPER_CLASSIFY_MAX_CHARS_PER_QUESTION",
            DEFAULT_SUPER_MAX_CHARS_PER_QUESTION,
        )
        self.retry_batch_size = max(
            1,
            _env_int("SUPER_CLASSIFY_RETRY_BATCH_SIZE", DEFAULT_SUPER_RETRY_BATCH_SIZE),
        )

    def _generate_json_response(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        return (response.text or "").strip()

    def _recover_missing_results(
        self,
        exam_id: int,
        lectures: List[Dict[str, Any]],
        questions: List[Dict[str, Any]],
        missing_ids: List[int],
    ) -> List[Dict[str, Any]]:
        question_lookup = {
            int(question["id"]): question
            for question in questions
            if question.get("id") is not None
        }
        recovered_results: List[Dict[str, Any]] = []
        for start in range(0, len(missing_ids), self.retry_batch_size):
            batch_ids = missing_ids[start:start + self.retry_batch_size]
            batch_questions = [
                question_lookup[question_id]
                for question_id in batch_ids
                if question_id in question_lookup
            ]
            if not batch_questions:
                continue

            retry_prompt = _build_super_prompt(
                lectures,
                batch_questions,
                max_chars_per_question=self.max_chars_per_question,
            )
            try:
                raw_text = self._generate_json_response(retry_prompt)
                logger.info(
                    "SUPER_CLASSIFY_RETRY_RESPONSE exam_id=%s batch_size=%s response_len=%s",
                    exam_id,
                    len(batch_questions),
                    len(raw_text),
                )
                recovered_results.extend(
                    _parse_super_result(raw_text, batch_questions, lectures)
                )
            except Exception:
                logger.exception(
                    "SUPER_CLASSIFY_RETRY_FAILED exam_id=%s batch_size=%s",
                    exam_id,
                    len(batch_questions),
                )
        return recovered_results

    def classify_exam(
        self,
        exam_id: int,
        *,
        question_ids: Optional[List[int]] = None,
        lecture_ids: Optional[List[int]] = None,
        block_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        include_descendants: bool = True,
    ) -> Dict[str, Any]:
        """
        시험 전체를 단일 API 호출로 분류.

        Returns:
            {
                'results': List[Dict],  분류 결과 리스트
                'lecture_count': int,
                'question_count': int,
                'model_name': str,
            }
        """
        # 1. Resolve lecture scope
        effective_lecture_ids = lecture_ids
        if effective_lecture_ids is None and (block_id or folder_id):
            effective_lecture_ids = resolve_lecture_ids(
                block_id, folder_id, include_descendants
            )

        # If still None, try resolving from exam subject
        if effective_lecture_ids is None:
            exam = db.session.get(PreviousExam, exam_id)
            if exam:
                # 시험의 첫번째 문제로 subject scope resolve
                first_q = (
                    Question.query
                    .filter(Question.exam_id == exam_id)
                    .first()
                )
                if first_q:
                    effective_lecture_ids = resolve_exam_subject_lecture_ids(
                        first_q
                    )

        # 2. Load data
        lectures = _load_lectures_with_chunks(
            lecture_ids=effective_lecture_ids,
            max_lectures=self.max_lectures,
            max_chars_per_lecture=self.max_chars_per_lecture,
        )
        if not lectures:
            raise ValueError(
                "분류 대상 강의가 없습니다. 강의록(청크)이 업로드되었는지 확인하세요."
            )

        questions = _load_exam_questions(exam_id, question_ids=question_ids)
        if not questions:
            raise ValueError("시험에 문제가 없습니다.")

        # 3. Build prompt
        prompt = _build_super_prompt(
            lectures,
            questions,
            max_chars_per_question=self.max_chars_per_question,
        )
        if self.max_prompt_chars > 0 and len(prompt) > self.max_prompt_chars:
            raise ValueError(
                "Super 분류 프롬프트 크기가 제한을 초과했습니다. "
                f"prompt_len={len(prompt)} max={self.max_prompt_chars}. "
                "강의 범위를 줄이거나 SUPER_CLASSIFY_MAX_PROMPT_CHARS를 조정하세요."
            )

        logger.info(
            "SUPER_CLASSIFY_START exam_id=%s lectures=%s questions=%s model=%s prompt_len=%s",
            exam_id,
            len(lectures),
            len(questions),
            self.model_name,
            len(prompt),
        )

        # 4. Call Gemini API (single request)
        raw_text = self._generate_json_response(prompt)
        logger.info(
            "SUPER_CLASSIFY_RESPONSE exam_id=%s response_len=%s",
            exam_id,
            len(raw_text),
        )

        # 5. Parse results
        results = _parse_super_result(raw_text, questions, lectures)
        missing_ids = _missing_super_question_ids(results, questions)
        if missing_ids:
            logger.warning(
                "SUPER_CLASSIFY_INCOMPLETE_FIRST_PASS exam_id=%s expected=%s got=%s missing=%s",
                exam_id,
                len(questions),
                len(questions) - len(missing_ids),
                len(missing_ids),
            )
            recovered_results = self._recover_missing_results(
                exam_id,
                lectures,
                questions,
                missing_ids,
            )
            if recovered_results:
                existing_ids = {
                    int(result["question_id"])
                    for result in results
                    if result.get("question_id") is not None
                }
                for recovered in recovered_results:
                    recovered_qid = recovered.get("question_id")
                    if recovered_qid is None:
                        continue
                    try:
                        recovered_qid = int(recovered_qid)
                    except (TypeError, ValueError):
                        continue
                    if recovered_qid in existing_ids:
                        continue
                    results.append(recovered)
                    existing_ids.add(recovered_qid)

        remaining_missing_ids = _missing_super_question_ids(results, questions)
        if remaining_missing_ids:
            question_lookup = {
                int(question["id"]): question
                for question in questions
                if question.get("id") is not None
            }
            candidate_ids = [lecture["id"] for lecture in lectures]
            for missing_id in remaining_missing_ids:
                question_data = question_lookup.get(missing_id)
                if not question_data:
                    continue
                results.append(
                    _build_super_no_match_result(
                        question_data,
                        lectures,
                        reason="모델 응답 누락으로 자동 no_match 처리",
                        candidate_ids=candidate_ids,
                    )
                )
            logger.warning(
                "SUPER_CLASSIFY_FILLED_NO_MATCH exam_id=%s missing=%s",
                exam_id,
                len(remaining_missing_ids),
            )

        results.sort(
            key=lambda result: (
                int(result.get("question_number") or 0),
                int(result.get("question_id") or 0),
            )
        )
        _validate_super_results(results, questions)

        # Log summary
        matched = sum(1 for r in results if not r.get("no_match"))
        no_match = sum(1 for r in results if r.get("no_match"))
        logger.info(
            "SUPER_CLASSIFY_DONE exam_id=%s total=%s matched=%s no_match=%s missing=%s",
            exam_id,
            len(questions),
            matched,
            no_match,
            len(questions) - len(results),
        )

        return {
            "results": results,
            "lecture_count": len(lectures),
            "question_count": len(questions),
            "model_name": self.model_name,
        }

    @classmethod
    def start_super_classification_job(
        cls,
        exam_id: int,
        request_meta: Optional[Dict] = None,
        *,
        lecture_ids: Optional[List[int]] = None,
        question_ids: Optional[List[int]] = None,
        block_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        include_descendants: bool = True,
    ) -> int:
        """
        Super 분류 작업을 비동기로 시작.

        Returns:
            job_id: 생성된 작업 ID
        """
        if question_ids is None:
            question_ids = [
                q.id
                for q in Question.query
                .filter(Question.exam_id == exam_id)
                .order_by(Question.question_number)
                .all()
            ]
        else:
            question_ids = _normalize_int_list(question_ids)

        question_count = len(question_ids)
        if question_count == 0:
            raise ValueError("시험에 문제가 없습니다.")

        # Job 생성
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=question_count,
        )
        meta = dict(request_meta or {})
        meta["super_classify"] = True
        meta["exam_id"] = exam_id
        meta["question_ids"] = question_ids

        scope_meta_raw = meta.get("scope")
        scope_meta = dict(scope_meta_raw) if isinstance(scope_meta_raw, dict) else {}

        if lecture_ids is not None:
            lecture_ids = _normalize_int_list(lecture_ids)
            scope_meta["lecture_ids"] = lecture_ids

        if block_id is not None:
            try:
                scope_meta["block_id"] = int(block_id)
            except (TypeError, ValueError):
                scope_meta["block_id"] = block_id
        if folder_id is not None:
            try:
                scope_meta["folder_id"] = int(folder_id)
            except (TypeError, ValueError):
                scope_meta["folder_id"] = folder_id
        if block_id is not None or folder_id is not None:
            scope_meta["include_descendants"] = bool(include_descendants)

        if scope_meta:
            meta["scope"] = scope_meta

        job.result_json = json.dumps(
            build_job_payload(meta, []),
            ensure_ascii=False,
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

        logger.info(
            "SUPER_CLASSIFY_JOB_ENQUEUED job_id=%s exam_id=%s questions=%s",
            job_id,
            exam_id,
            question_count,
        )

        # 백그라운드 처리 시작
        cls._executor.submit(
            cls._process_job,
            job_id,
            exam_id,
            question_ids=question_ids,
            lecture_ids=lecture_ids,
            block_id=block_id,
            folder_id=folder_id,
            include_descendants=include_descendants,
        )

        return job_id

    @classmethod
    def _process_job(
        cls,
        job_id: int,
        exam_id: int,
        *,
        question_ids: Optional[List[int]] = None,
        lecture_ids: Optional[List[int]] = None,
        block_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        include_descendants: bool = True,
    ):
        """백그라운드에서 super 분류 작업 수행."""
        from app import create_app

        config_name = os.environ.get("FLASK_CONFIG") or "default"
        app = create_app(config_name)

        with app.app_context():
            job = db.session.get(ClassificationJob, job_id)
            if not job:
                return

            request_meta, _ = parse_job_payload(job.result_json)
            if job.status == ClassificationJob.STATUS_CANCELLED:
                return

            job.status = ClassificationJob.STATUS_PROCESSING
            db.session.commit()

            results = []
            try:
                classifier = SuperClassifier()
                output = classifier.classify_exam(
                    exam_id,
                    question_ids=question_ids,
                    lecture_ids=lecture_ids,
                    block_id=block_id,
                    folder_id=folder_id,
                    include_descendants=include_descendants,
                )
                results = output["results"]

                # 성공/실패 카운트
                job.success_count = sum(
                    1 for r in results if not r.get("error")
                )
                job.failed_count = sum(
                    1 for r in results if r.get("error")
                )
                job.processed_count = len(results)

                # Check for cancellation
                db.session.refresh(job)
                if job.status == ClassificationJob.STATUS_CANCELLED:
                    job.result_json = json.dumps(
                        build_job_payload(request_meta, results),
                        ensure_ascii=False,
                    )
                    job.completed_at = datetime.utcnow()
                else:
                    job.status = ClassificationJob.STATUS_COMPLETED
                    job.result_json = json.dumps(
                        build_job_payload(request_meta, results),
                        ensure_ascii=False,
                    )
                    job.completed_at = datetime.utcnow()

                logger.info(
                    "SUPER_CLASSIFY_JOB_COMPLETED job_id=%s processed=%s success=%s failed=%s",
                    job_id,
                    job.processed_count,
                    job.success_count,
                    job.failed_count,
                )

            except Exception as e:
                db.session.refresh(job)
                if job.status == ClassificationJob.STATUS_CANCELLED:
                    pass
                else:
                    job.status = ClassificationJob.STATUS_FAILED
                    job.error_message = str(e)
                job.result_json = json.dumps(
                    build_job_payload(request_meta, results),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.utcnow()
                logger.exception(
                    "SUPER_CLASSIFY_JOB_FAILED job_id=%s exam_id=%s",
                    job_id,
                    exam_id,
                )

            db.session.commit()


__all__ = [
    "SuperClassifier",
    "GENAI_AVAILABLE",
]
