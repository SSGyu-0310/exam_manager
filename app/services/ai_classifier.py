"""AI 분류 서비스 모듈

Google Gemini API를 활용한 문제-강의 자동 분류 서비스.
2단계 분류 프로세스: 1) 텍스트 기반 후보 추출 2) LLM 정밀 분류
"""

import json
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
import threading

from flask import current_app
from sqlalchemy import func
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

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
    Subject,
    User,
    ClassificationJob,
    LectureChunk,
    QuestionChunkMatch,
)
from app.services import retrieval
from app.services.folder_scope import parse_bool, resolve_lecture_ids
from app.services.classification_scope import (
    normalize_classification_scope,
    normalize_scope_user_id,
)
from app.services.block_sort import block_lecture_ordering

logger = logging.getLogger(__name__)

# ============================================================
# Job payload helpers (idempotency + compatibility)
# ============================================================


def build_job_payload(
    request_meta: Optional[Dict], results: Optional[List[Dict]] = None
) -> Dict:
    return {
        "request": request_meta or {},
        "results": results or [],
    }


def parse_job_payload(result_json: Optional[str]) -> Tuple[Dict, List[Dict]]:
    if not result_json:
        return {}, []
    try:
        payload = json.loads(result_json)
    except (TypeError, ValueError):
        return {}, []
    if isinstance(payload, list):
        return {}, payload
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return payload.get("request", {}) or {}, results
        return payload.get("request", {}) or {}, []
    return {}, []


def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _sanitize_json_text(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "")
    text = re.sub(r"[\x00-\x1F\x7F]", " ", text)
    text = (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()


def _fallback_parse_result(text: str) -> Dict:
    cleaned = _sanitize_json_text(text)
    data: Dict = {}

    m = re.search(r"lecture_id\s*[:=]\s*(null|\d+)", cleaned, re.IGNORECASE)
    if m:
        raw = m.group(1).lower()
        data["lecture_id"] = None if raw == "null" else int(raw)

    m = re.search(r"no_match\s*[:=]\s*(true|false)", cleaned, re.IGNORECASE)
    if m:
        data["no_match"] = m.group(1).lower() == "true"

    # Try multiple confidence-related keys: confidence, score, certainty, probability
    for conf_key in ("confidence", "score", "certainty", "probability"):
        m = re.search(
            rf"{conf_key}\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", cleaned, re.IGNORECASE
        )
        if m:
            try:
                data["confidence"] = float(m.group(1))
                break
            except ValueError:
                continue

    for key in ("reason", "study_hint"):
        m = re.search(
            rf'"?{key}"?\s*[:=]\s*"(.*?)"', cleaned, re.IGNORECASE | re.DOTALL
        )
        if not m:
            m = re.search(rf'"?{key}"?\s*[:=]\s*([^\n\r]+)', cleaned, re.IGNORECASE)
        if m:
            data[key] = m.group(1).strip().strip('"').strip()

    data.setdefault("lecture_id", None)
    if "no_match" not in data:
        data["no_match"] = data["lecture_id"] is None
    data.setdefault("confidence", 0.0)
    data.setdefault("reason", "")
    data.setdefault("study_hint", "")
    data.setdefault("evidence", [])
    return data


def _extract_lecture_id_from_text(
    text: Optional[str], valid_ids: Optional[set]
) -> Optional[int]:
    if not text:
        return None
    patterns = [
        "\uac15\uc758\ub85d\\s*(\\d+)\\s*\ubc88",
        r"lecture\s*#?\s*(\d+)",
        r"id\s*[:=]?\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        try:
            lecture_id = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if valid_ids and lecture_id not in valid_ids:
            continue
        return lecture_id
    return None


def _coerce_confidence(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    raw = value.strip()
    if not raw:
        return 0.0
    if "%" in raw:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
        if not match:
            return 0.0
        try:
            return float(match.group(1)) / 100.0
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _normalize_subject_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    normalized = re.sub(r"\s+", " ", str(raw)).strip().lower()
    return normalized or None


def resolve_exam_subject_lecture_ids(
    question: Question,
    *,
    cache: Optional[Dict[str, Optional[List[int]]]] = None,
) -> Optional[List[int]]:
    """Resolve lecture scope from exam subject.

    Returns `None` when subject is empty or when there is no matching lecture,
    so caller can gracefully fall back to unrestricted search.
    """
    exam = getattr(question, "exam", None)
    subject_key = _normalize_subject_name(getattr(exam, "subject", None))
    if not subject_key:
        return None

    if cache is not None and subject_key in cache:
        return cache[subject_key]

    normalized_block_subject = func.lower(func.trim(func.coalesce(Block.subject, "")))
    normalized_subject_name = func.lower(func.trim(func.coalesce(Subject.name, "")))

    direct_rows = (
        Lecture.query.join(Block, Lecture.block_id == Block.id)
        .filter(normalized_block_subject == subject_key)
        .with_entities(Lecture.id)
        .all()
    )

    subject_rows = (
        Subject.query.filter(normalized_subject_name == subject_key)
        .with_entities(Subject.id)
        .all()
    )
    subject_ids = [
        int(row[0]) for row in subject_rows if row is not None and row[0] is not None
    ]
    reference_rows = (
        Lecture.query.join(Block, Lecture.block_id == Block.id)
        .filter(Block.subject_id.in_(subject_ids))
        .with_entities(Lecture.id)
        .all()
        if subject_ids
        else []
    )

    lecture_ids = sorted(
        {
            int(row[0])
            for row in (direct_rows + reference_rows)
            if row is not None and row[0] is not None
        }
    )
    resolved = lecture_ids or None
    if cache is not None:
        cache[subject_key] = resolved
    return resolved


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


def build_job_diagnostics(
    job: ClassificationJob,
    question_ids: Optional[List[int]] = None,
    *,
    include_rows: bool = True,
    row_limit: int = 200,
) -> Dict[str, Any]:
    """Summarize classification result payload for debugging/troubleshooting."""
    request_meta, results = parse_job_payload(job.result_json)

    selected_ids: Optional[set[int]] = None
    if question_ids:
        selected_ids = set()
        for raw_qid in question_ids:
            try:
                selected_ids.add(int(raw_qid))
            except (TypeError, ValueError):
                continue

    threshold = float(current_app.config.get("AI_CONFIDENCE_THRESHOLD", 0.7))
    inspected_ids: set[int] = set()
    rows: List[Dict[str, Any]] = []

    summary: Dict[str, Any] = {
        "job_total_count": int(job.total_count or 0),
        "result_total_count": len(results),
        "requested_count": len(selected_ids) if selected_ids is not None else len(results),
        "inspected_count": 0,
        "applyable_count": 0,
        "no_match_count": 0,
        "missing_lecture_count": 0,
        "out_of_candidates_count": 0,
        "error_count": 0,
        "with_evidence_count": 0,
        "high_confidence_count": 0,
        "low_confidence_count": 0,
        "rejudge_attempted_count": 0,
        "rejudge_salvaged_count": 0,
        "weak_match_count": 0,
    }

    for result in results:
        question_id = result.get("question_id")
        if question_id is None:
            continue
        try:
            question_id = int(question_id)
        except (TypeError, ValueError):
            continue

        if selected_ids is not None and question_id not in selected_ids:
            continue

        inspected_ids.add(question_id)
        summary["inspected_count"] += 1

        lecture_id = result.get("lecture_id")
        try:
            lecture_id = int(lecture_id) if lecture_id is not None else None
        except (TypeError, ValueError):
            lecture_id = None

        raw_candidates = result.get("candidate_ids")
        candidate_ids: List[int] = []
        if isinstance(raw_candidates, list):
            for candidate_id in raw_candidates:
                try:
                    candidate_ids.append(int(candidate_id))
                except (TypeError, ValueError):
                    continue

        no_match = parse_bool(result.get("no_match"), False)
        if lecture_id is None:
            no_match = True
        if no_match:
            summary["no_match_count"] += 1

        decision_mode = str(
            result.get("decision_mode") or ("no_match" if no_match else "strict_match")
        ).strip().lower()
        final_decision_source = str(result.get("final_decision_source") or "pass1").strip()
        rejudge_attempted = parse_bool(result.get("rejudge_attempted"), False)
        if rejudge_attempted:
            summary["rejudge_attempted_count"] += 1
        if (
            final_decision_source == "pass2"
            and decision_mode in {"strict_match", "weak_match"}
            and lecture_id is not None
            and not no_match
        ):
            summary["rejudge_salvaged_count"] += 1
        if decision_mode == "weak_match" and lecture_id is not None and not no_match:
            summary["weak_match_count"] += 1

        if lecture_id is None:
            summary["missing_lecture_count"] += 1

        out_of_candidates = (
            lecture_id is not None and bool(candidate_ids) and lecture_id not in candidate_ids
        )
        if out_of_candidates:
            summary["out_of_candidates_count"] += 1

        confidence = _coerce_confidence(result.get("confidence"))
        if confidence >= threshold:
            summary["high_confidence_count"] += 1
        else:
            summary["low_confidence_count"] += 1

        evidence_list = result.get("evidence")
        evidence_count = len(evidence_list) if isinstance(evidence_list, list) else 0
        if evidence_count > 0:
            summary["with_evidence_count"] += 1

        has_error = bool(result.get("error"))
        if has_error:
            summary["error_count"] += 1

        applyable = bool(lecture_id and not no_match and not out_of_candidates)
        if applyable:
            summary["applyable_count"] += 1

        if include_rows and len(rows) < max(row_limit, 0):
            reason_tags: List[str] = []
            if has_error:
                reason_tags.append("error")
            if no_match:
                reason_tags.append("no_match")
            if lecture_id is None:
                reason_tags.append("no_lecture")
            if out_of_candidates:
                reason_tags.append("out_of_candidates")
            if evidence_count == 0:
                reason_tags.append("no_evidence")
            if confidence < threshold:
                reason_tags.append("below_threshold")
            if decision_mode == "weak_match":
                reason_tags.append("weak_match")
            if rejudge_attempted:
                reason_tags.append("rejudge_attempted")
            if applyable:
                reason_tags.append("applyable")

            rows.append(
                {
                    "question_id": question_id,
                    "lecture_id": lecture_id,
                    "candidate_ids": candidate_ids,
                    "no_match": no_match,
                    "confidence": confidence,
                    "evidence_count": evidence_count,
                    "decision_mode": decision_mode,
                    "final_decision_source": final_decision_source,
                    "rejudge_attempted": rejudge_attempted,
                    "classification_status": result.get("classification_status"),
                    "reason_tags": reason_tags,
                    "reason": result.get("reason", ""),
                    "error": result.get("error", False),
                }
            )

    missing_result_ids: List[int] = []
    if selected_ids is not None:
        missing_result_ids = sorted(selected_ids - inspected_ids)
    summary["missing_result_count"] = len(missing_result_ids)

    diagnostics: Dict[str, Any] = {
        "job_id": job.id,
        "job_status": job.status,
        "threshold": threshold,
        "request_meta": request_meta,
        "summary": summary,
    }
    if include_rows:
        diagnostics["rows"] = rows
    if missing_result_ids:
        diagnostics["missing_result_ids"] = missing_result_ids
    return diagnostics


# ============================================================
# 1단계: 후보 강의 추출 (검색 기반)
# ============================================================


class LectureRetriever:
    """강의 후보 검색기 - 검색 기반 Top-K 추출"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._lectures_cache = []
        self._initialized = True

    def refresh_cache(self):
        """강의 캐시 갱신 (앱 컨텍스트 내에서 호출)"""
        lectures = Lecture.query.join(Block).order_by(*block_lecture_ordering()).all()
        self._lectures_cache = []
        for lecture in lectures:
            self._lectures_cache.append(
                {
                    "id": lecture.id,
                    "title": lecture.title,
                    "block_name": lecture.block.name,
                    "full_path": f"{lecture.block.name} > {lecture.title}",
                }
            )

    def find_candidates(
        self,
        question_text: str,
        top_k: int = 8,
        *,
        question_id: int | None = None,
        lecture_ids: Optional[List[int]] = None,
        evidence_per_lecture: int = 3,
    ) -> List[Dict]:
        """BM25 기반 후보 강의 검색."""
        mode = (get_config().experiment.retrieval_mode or "bm25").strip().lower()
        if mode != "bm25":
            logging.warning("Unsupported RETRIEVAL_MODE=%s; forcing bm25.", mode)

        chunks = retrieval.search_chunks_bm25(
            question_text,
            top_n=80,
            question_id=question_id,
            lecture_ids=lecture_ids,
        )
        cfg = get_config().experiment
        return retrieval.aggregate_candidates(
            chunks,
            top_k_lectures=top_k,
            evidence_per_lecture=evidence_per_lecture,
            agg_mode=cfg.lecture_agg_mode,
            topm=cfg.lecture_topm,
            chunk_cap=cfg.lecture_chunk_cap,
        )


# ============================================================
# 2단계: LLM 기반 정밀 분류
# ============================================================


class GeminiClassifier:
    """Google Gemini API를 사용한 문제 분류기"""

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
        self.model_name = cfg.runtime.gemini_model_name or "gemini-2.5-flash"
        self.confidence_threshold = current_app.config.get(
            "AI_CONFIDENCE_THRESHOLD", 0.7
        )
        self.auto_apply_margin = current_app.config.get("AI_AUTO_APPLY_MARGIN", 0.2)

    def _build_classification_prompt(
        self, question_content: str, choices: List[str], candidates: List[Dict]
    ) -> str:
        """Build the classification prompt."""
        candidate_lines = []
        for c in candidates:
            # Use expanded context if available
            parent_text = c.get("parent_text")

            if parent_text:
                # Expanded context mode
                range_info = ""
                ranges = c.get("parent_page_ranges", [])
                if ranges:
                    # summarize ranges
                    min_p = min(r[0] for r in ranges if r[0] is not None)
                    max_p = max(r[1] for r in ranges if r[1] is not None)
                    range_info = f" (Pages {min_p}-{max_p})"

                candidate_lines.append(
                    f"- ID: {c['id']}, Lecture: {c['full_path']}{range_info}\n"
                    f"  [Expanded Context Start]\n"
                    f"{parent_text}\n"
                    f"  [Expanded Context End]"
                )
            else:
                # Fallback to snippets
                evidence_lines = []
                for e in c.get("evidence", []) or []:
                    page_start = e.get("page_start")
                    page_end = e.get("page_end")
                    if page_start is None or page_end is None:
                        page_label = "p.?"
                    else:
                        page_label = (
                            f"p.{page_start}"
                            if page_start == page_end
                            else f"p.{page_start}-{page_end}"
                        )
                    snippet = e.get("snippet") or ""
                    evidence_lines.append(
                        f'  - {page_label}: "{snippet}" (chunk_id: {e.get("chunk_id")})'
                    )
                if not evidence_lines:
                    evidence_lines.append("  - evidence: none")
                candidate_lines.append(
                    f"- ID: {c['id']}, Lecture: {c['full_path']}\n"
                    + "\n".join(evidence_lines)
                )

        candidates_text = (
            "\n".join(candidate_lines) if candidate_lines else "(no candidates)"
        )

        choices_text = (
            "\n".join([f"  {i + 1}. {c}" for i, c in enumerate(choices)])
            if choices
            else "(no choices)"
        )

        candidate_ids = [c.get("id") for c in candidates if c.get("id") is not None]

        prompt = f"""You are a medical lecture classifier. Select exactly one lecture from candidates, or return no_match=true.

## Question
{question_content}

## Choices
{choices_text}

## Candidate Lectures (with evidence)
{candidates_text}

## Instructions
1. Candidate lecture IDs: {candidate_ids}
2. You MUST choose lecture_id from candidate IDs only. Never create a new ID.
3. If evidence is weak/ambiguous/missing, set no_match=true and lecture_id=null.
4. If no_match=true, evidence must be [].
5. If no_match=false, include 1~3 evidence items from the selected lecture only.
6. evidence.quote must be verbatim text copied from provided snippet/expanded context.
7. page_start/page_end/chunk_id must match provided candidate evidence.
8. If page information is unknown or verbatim quote cannot be grounded, choose no_match=true.
9. Return valid JSON only. No markdown, no extra explanation.

## Response JSON
{{
    "lecture_id": (selected lecture ID or null),
    "confidence": (0.0~1.0),
    "reason": "short reason in Korean",
    "study_hint": "e.g., Review p.12-13 for the definition and compare with related concepts.",
    "no_match": (true/false),
    "evidence": [
        {{
            "lecture_id": 123,
            "page_start": 12,
            "page_end": 13,
            "quote": "copied snippet text",
            "chunk_id": 991
        }}
    ]
}}
"""
        return prompt

    def _invoke_json_prompt(self, prompt: str, *, temperature: float = 0.2) -> Dict:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                top_p=0.8,
                max_output_tokens=current_app.config.get(
                    "GEMINI_MAX_OUTPUT_TOKENS", 2048
                ),
                thinking_config=types.ThinkingConfig(include_thoughts=False),
                response_mime_type="application/json",
            ),
        )
        result_text = (response.text or "").strip()
        json_text = _extract_first_json_object(result_text) or result_text
        json_text = _sanitize_json_text(json_text)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            parsed = _fallback_parse_result(result_text)
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_evidence(
        self,
        lecture_id: int,
        candidates: List[Dict],
        evidence_raw: List[Dict],
        *,
        max_items: int = 3,
    ) -> List[Dict]:
        cfg = get_config().experiment
        require_verbatim = _env_flag(
            "CLASSIFIER_REQUIRE_VERBATIM_QUOTE",
            bool(cfg.classifier_require_verbatim_quote),
        )
        require_page_span = _env_flag(
            "CLASSIFIER_REQUIRE_PAGE_SPAN",
            bool(cfg.classifier_require_page_span),
        )

        selected = next((c for c in candidates if c.get("id") == lecture_id), None)
        if not selected:
            return []

        candidate_evidence = {
            e.get("chunk_id"): e
            for e in (selected.get("evidence", []) or [])
            if e.get("chunk_id") is not None
        }
        cleaned = []

        for item in evidence_raw or []:
            if not isinstance(item, dict):
                continue

            item_lecture_id = item.get("lecture_id")
            if item_lecture_id is not None:
                try:
                    if int(item_lecture_id) != lecture_id:
                        continue
                except (TypeError, ValueError):
                    continue
            chunk_id = item.get("chunk_id")
            try:
                chunk_id = int(chunk_id)
            except (TypeError, ValueError):
                continue

            candidate_item = candidate_evidence.get(chunk_id)
            if not candidate_item:
                continue

            snippet = candidate_item.get("snippet") or ""
            page_start = candidate_item.get("page_start")
            page_end = candidate_item.get("page_end")
            if require_page_span and (page_start is None or page_end is None):
                continue

            quote = str(item.get("quote") or "").strip()
            if require_verbatim:
                if not quote:
                    continue
                if not snippet or quote not in snippet:
                    continue
                quote_to_save = quote
            else:
                if quote and snippet and quote in snippet:
                    quote_to_save = quote
                elif snippet:
                    quote_to_save = snippet
                else:
                    continue

            cleaned.append(
                {
                    "lecture_id": lecture_id,
                    "page_start": page_start,
                    "page_end": page_end,
                    "quote": quote_to_save,
                    "chunk_id": chunk_id,
                }
            )

        return cleaned[: max(max_items, 1)]

    def _normalize_decision_mode(self, raw_mode: object) -> str:
        mode = str(raw_mode or "").strip().lower()
        if mode in {"strict_match", "strict", "match"}:
            return "strict_match"
        if mode in {"weak_match", "weak"}:
            return "weak_match"
        return "no_match"

    def _build_question_text(self, question: Question, choices: List[str]) -> str:
        question_text = question.content or ""
        if choices:
            question_text = f"{question_text}\n" + " ".join(choices)
        question_text = question_text.strip()
        if len(question_text) > 4000:
            question_text = question_text[:4000]
        return question_text

    def _should_attempt_rejudge(self, candidates: List[Dict], no_match: bool) -> bool:
        cfg = get_config().experiment
        enabled = _env_flag(
            "CLASSIFIER_REJUDGE_ENABLED",
            bool(cfg.classifier_rejudge_enabled),
        )
        if not enabled or not no_match:
            return False
        min_candidates = _env_int(
            "CLASSIFIER_REJUDGE_MIN_CANDIDATES",
            int(cfg.classifier_rejudge_min_candidates),
        )
        candidate_count = len([c for c in candidates if c.get("id") is not None])
        return candidate_count >= max(1, min_candidates)

    def _prepare_rejudge_candidates(
        self,
        question: Question,
        choices: List[str],
        candidates: List[Dict],
    ) -> List[Dict]:
        cfg = get_config().experiment
        top_k = _env_int(
            "CLASSIFIER_REJUDGE_TOP_K",
            int(cfg.classifier_rejudge_top_k),
        )
        evidence_per_lecture = _env_int(
            "CLASSIFIER_REJUDGE_EVIDENCE_PER_LECTURE",
            int(cfg.classifier_rejudge_evidence_per_lecture),
        )

        ordered_ids: List[int] = []
        for candidate in candidates:
            lecture_id = candidate.get("id")
            if lecture_id is None:
                continue
            try:
                lecture_id = int(lecture_id)
            except (TypeError, ValueError):
                continue
            if lecture_id in ordered_ids:
                continue
            ordered_ids.append(lecture_id)
        selected_ids = ordered_ids[: max(top_k, 1)]
        if not selected_ids:
            return []

        base_map = {
            int(c.get("id")): c
            for c in candidates
            if c.get("id") is not None
            and str(c.get("id")).isdigit()
        }

        question_text = self._build_question_text(question, choices)
        retriever = LectureRetriever()
        refreshed = retriever.find_candidates(
            question_text,
            top_k=len(selected_ids),
            question_id=question.id,
            lecture_ids=selected_ids,
            evidence_per_lecture=evidence_per_lecture,
        )
        refreshed_map = {
            c.get("id"): c for c in refreshed if c.get("id") is not None
        }

        prepared: List[Dict] = []
        for lecture_id in selected_ids:
            base = base_map.get(lecture_id) or {}
            fresh = refreshed_map.get(lecture_id) or {}
            merged = {
                "id": lecture_id,
                "title": fresh.get("title") or base.get("title"),
                "block_name": fresh.get("block_name") or base.get("block_name"),
                "full_path": fresh.get("full_path")
                or base.get("full_path")
                or f"Lecture {lecture_id}",
                "score": fresh.get("score", base.get("score", 0.0)),
            }

            evidence_combined: List[Dict] = []
            seen_keys: set[str] = set()
            for source_items in (fresh.get("evidence") or [], base.get("evidence") or []):
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    chunk_id = item.get("chunk_id")
                    key = (
                        f"chunk:{chunk_id}"
                        if chunk_id is not None
                        else f"text:{item.get('snippet')}|{item.get('page_start')}|{item.get('page_end')}"
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    evidence_combined.append(
                        {
                            "page_start": item.get("page_start"),
                            "page_end": item.get("page_end"),
                            "snippet": item.get("snippet") or "",
                            "chunk_id": item.get("chunk_id"),
                        }
                    )
                    if len(evidence_combined) >= max(evidence_per_lecture, 1):
                        break
                if len(evidence_combined) >= max(evidence_per_lecture, 1):
                    break
            merged["evidence"] = evidence_combined
            if base.get("parent_text") and not fresh.get("parent_text"):
                merged["parent_text"] = base.get("parent_text")
                merged["parent_chunk_ids"] = base.get("parent_chunk_ids")
                merged["parent_page_ranges"] = base.get("parent_page_ranges")
            prepared.append(merged)

        try:
            from app.services import context_expander

            prepared = context_expander.expand_candidates(prepared)
        except Exception:
            if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                logger.exception(
                    "CLASSIFIER_REJUDGE_EXPANSION_FAILED qid=%s",
                    question.id if question else "unknown",
                )
        return prepared

    def _build_rejudge_prompt(
        self,
        question_content: str,
        choices: List[str],
        candidates: List[Dict],
    ) -> str:
        candidate_lines = []
        for c in candidates:
            parent_text = c.get("parent_text")
            evidence_lines = []
            for e in c.get("evidence", []) or []:
                page_start = e.get("page_start")
                page_end = e.get("page_end")
                if page_start is None or page_end is None:
                    page_label = "p.?"
                else:
                    page_label = (
                        f"p.{page_start}"
                        if page_start == page_end
                        else f"p.{page_start}-{page_end}"
                    )
                evidence_lines.append(
                    f'  - {page_label}: "{e.get("snippet") or ""}" (chunk_id: {e.get("chunk_id")})'
                )
            if not evidence_lines:
                evidence_lines.append("  - evidence: none")

            if parent_text:
                candidate_lines.append(
                    f"- ID: {c['id']}, Lecture: {c['full_path']}\n"
                    + "\n".join(evidence_lines)
                    + "\n  [Parent Context Start]\n"
                    + f"{parent_text}\n"
                    + "  [Parent Context End]"
                )
            else:
                candidate_lines.append(
                    f"- ID: {c['id']}, Lecture: {c['full_path']}\n"
                    + "\n".join(evidence_lines)
                )

        candidates_text = "\n".join(candidate_lines) if candidate_lines else "(no candidates)"
        choices_text = (
            "\n".join([f"  {idx + 1}. {choice}" for idx, choice in enumerate(choices)])
            if choices
            else "(no choices)"
        )
        candidate_ids = [c.get("id") for c in candidates if c.get("id") is not None]

        return f"""You are a medical lecture classifier for second-pass re-judging.

## Question
{question_content}

## Choices
{choices_text}

## Candidate Lectures (rich evidence + optional parent context)
{candidates_text}

## Instructions
1. Candidate lecture IDs: {candidate_ids}
2. Select only one lecture_id from candidate IDs, or choose no_match.
3. decision_mode must be one of: strict_match, weak_match, no_match.
4. If decision_mode=no_match, lecture_id must be null and evidence must be [].
5. If decision_mode is strict_match or weak_match, provide 1~3 evidence items from selected lecture only.
6. evidence.quote must be verbatim from provided snippet/parent context.
7. page_start/page_end/chunk_id must match provided candidate evidence.
8. why_not_no_match should explain why no_match is not selected.
9. Return valid JSON only.

## Response JSON
{{
  "decision_mode": "strict_match | weak_match | no_match",
  "lecture_id": (selected lecture ID or null),
  "confidence": (0.0~1.0),
  "reason": "short reason in Korean",
  "evidence": [
    {{
      "lecture_id": 123,
      "page_start": 12,
      "page_end": 13,
      "quote": "copied snippet text",
      "chunk_id": 991
    }}
  ],
  "why_not_no_match": "short reason in Korean"
}}
"""

    def _run_rejudge(
        self,
        question: Question,
        choices: List[str],
        candidates: List[Dict],
    ) -> Dict[str, Any]:
        content = question.content or "(image-only question)"
        prompt = self._build_rejudge_prompt(content, choices, candidates)
        result = self._invoke_json_prompt(prompt, temperature=0.1)

        if _env_flag("CLASSIFIER_DEBUG_LOG", False):
            logger.warning(
                "CLASSIFIER_REJUDGE_TRACE qid=%s model=%s mode=%s lecture_id=%s confidence=%s keys=%s",
                question.id if question else "unknown",
                self.model_name,
                result.get("decision_mode"),
                result.get("lecture_id"),
                result.get("confidence"),
                ",".join(sorted(result.keys())),
            )

        cfg = get_config().experiment
        allow_id_from_text = _env_flag(
            "CLASSIFIER_ALLOW_ID_FROM_TEXT",
            bool(cfg.classifier_allow_id_from_text),
        )
        valid_ids = {c.get("id") for c in candidates if c.get("id") is not None}

        decision_mode = self._normalize_decision_mode(result.get("decision_mode"))
        lecture_id = result.get("lecture_id")
        if lecture_id is not None:
            try:
                lecture_id = int(lecture_id)
            except (TypeError, ValueError):
                if isinstance(lecture_id, str):
                    matches = re.findall(r"\d+", lecture_id)
                    if len(matches) == 1:
                        lecture_id = int(matches[0])
                    else:
                        lecture_id = None
                else:
                    lecture_id = None

        if lecture_id is None and allow_id_from_text:
            lecture_id = _extract_lecture_id_from_text(result.get("reason"), valid_ids)
            if lecture_id is None:
                lecture_id = _extract_lecture_id_from_text(
                    result.get("why_not_no_match"), valid_ids
                )

        if lecture_id is not None and lecture_id not in valid_ids:
            lecture_id = None
        if decision_mode == "no_match":
            lecture_id = None
        elif lecture_id is None:
            decision_mode = "no_match"

        confidence = _coerce_confidence(
            result.get("confidence")
            or result.get("score")
            or result.get("certainty")
            or result.get("probability")
            or 0.0
        )
        reason = str(result.get("reason") or "")
        why_not_no_match = str(result.get("why_not_no_match") or "")
        evidence_raw = (
            result.get("evidence")
            if isinstance(result.get("evidence"), list)
            else []
        )
        evidence: List[Dict] = []
        if lecture_id and decision_mode != "no_match":
            evidence = self._normalize_evidence(
                lecture_id,
                candidates,
                evidence_raw,
                max_items=3,
            )
            if not evidence:
                lecture_id = None
                decision_mode = "no_match"
        if decision_mode == "no_match":
            evidence = []

        return {
            "decision_mode": decision_mode,
            "lecture_id": lecture_id,
            "confidence": confidence,
            "reason": reason,
            "evidence": evidence,
            "why_not_no_match": why_not_no_match,
            "no_match": decision_mode == "no_match" or lecture_id is None,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
    )
    def classify_single(self, question: Question, candidates: List[Dict]) -> Dict:
        """
        단일 문제 분류 (LLM 호출)

        Returns:
            {
                'lecture_id': int or None,
                'confidence': float,
                'reason': str,
                'study_hint': str,
                'evidence': list,
                'no_match': bool,
                'model_name': str
            }
        """
        choices = [c.content for c in question.choices.order_by("choice_number").all()]
        content = question.content or "(image-only question)"

        if not candidates:
            return {
                "lecture_id": None,
                "confidence": 0.0,
                "reason": "No lecture candidates available.",
                "study_hint": "",
                "evidence": [],
                "no_match": True,
                "model_name": self.model_name,
                "decision_mode": "no_match",
                "rejudge_attempted": False,
                "rejudge_decision_mode": None,
                "rejudge_confidence": None,
                "rejudge_reason": None,
                "final_decision_source": "pass1",
            }

        prompt = self._build_classification_prompt(content, choices, candidates)

        try:
            result = self._invoke_json_prompt(prompt, temperature=0.2)

            if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                logger.warning(
                    "CLASSIFIER_PARSE_TRACE qid=%s model=%s lecture_id=%s no_match=%s confidence=%s keys=%s",
                    question.id if question else "unknown",
                    self.model_name,
                    result.get("lecture_id"),
                    result.get("no_match"),
                    result.get("confidence"),
                    ",".join(sorted(result.keys())),
                )

            cfg = get_config().experiment
            allow_id_from_text = _env_flag(
                "CLASSIFIER_ALLOW_ID_FROM_TEXT",
                bool(cfg.classifier_allow_id_from_text),
            )

            lecture_id = result.get("lecture_id")
            no_match = parse_bool(result.get("no_match"), False)
            valid_ids = {c["id"] for c in candidates if c.get("id") is not None}
            if lecture_id is not None:
                try:
                    lecture_id = int(lecture_id)
                except (TypeError, ValueError):
                    if isinstance(lecture_id, str):
                        matches = re.findall(r"\d+", lecture_id)
                        if len(matches) == 1:
                            lecture_id = int(matches[0])
                        else:
                            lecture_id = None
                    else:
                        lecture_id = None
                if lecture_id is None:
                    no_match = True
            if lecture_id is None and allow_id_from_text:
                lecture_id = _extract_lecture_id_from_text(
                    result.get("reason"), valid_ids
                )
                if lecture_id is None:
                    lecture_id = _extract_lecture_id_from_text(
                        result.get("study_hint"), valid_ids
                    )
                if lecture_id is not None:
                    no_match = False
            if no_match:
                lecture_id = None
            if lecture_id is not None and lecture_id not in valid_ids:
                lecture_id = None
                no_match = True
            if lecture_id is None and not no_match:
                no_match = True

            raw_conf = (
                result.get("confidence")
                or result.get("score")
                or result.get("certainty")
                or result.get("probability")
                or 0.0
            )
            confidence = _coerce_confidence(raw_conf)
            reason = result.get("reason", "")
            study_hint = result.get("study_hint", "")
            evidence_raw = (
                result.get("evidence")
                if isinstance(result.get("evidence"), list)
                else []
            )
            evidence = []
            if lecture_id and not no_match:
                evidence = self._normalize_evidence(
                    lecture_id, candidates, evidence_raw
                )
                if not evidence:
                    lecture_id = None
                    no_match = True

            if no_match:
                evidence = []

            final_result: Dict[str, Any] = {
                "lecture_id": lecture_id,
                "confidence": confidence,
                "reason": reason,
                "study_hint": study_hint,
                "evidence": evidence,
                "no_match": no_match,
                "model_name": self.model_name,
                "decision_mode": "no_match" if no_match else "strict_match",
                "rejudge_attempted": False,
                "rejudge_decision_mode": None,
                "rejudge_confidence": None,
                "rejudge_reason": None,
                "final_decision_source": "pass1",
            }

            if self._should_attempt_rejudge(candidates, no_match):
                rejudge_candidates = self._prepare_rejudge_candidates(
                    question, choices, candidates
                )
                rejudge_result = self._run_rejudge(
                    question,
                    choices,
                    rejudge_candidates or candidates,
                )
                final_result["rejudge_attempted"] = True
                final_result["rejudge_decision_mode"] = rejudge_result.get("decision_mode")
                final_result["rejudge_confidence"] = rejudge_result.get("confidence")
                final_result["rejudge_reason"] = rejudge_result.get("reason")

                strict_min = _env_float(
                    "CLASSIFIER_REJUDGE_MIN_CONFIDENCE_STRICT",
                    float(cfg.classifier_rejudge_min_confidence_strict),
                )
                weak_allow = _env_flag(
                    "CLASSIFIER_REJUDGE_ALLOW_WEAK_MATCH",
                    bool(cfg.classifier_rejudge_allow_weak_match),
                )
                weak_min = _env_float(
                    "CLASSIFIER_REJUDGE_MIN_CONFIDENCE_WEAK",
                    float(cfg.classifier_rejudge_min_confidence_weak),
                )

                rejudge_mode = rejudge_result.get("decision_mode")
                rejudge_conf = _coerce_confidence(rejudge_result.get("confidence"))
                rejudge_lecture_id = rejudge_result.get("lecture_id")
                adopt_pass2 = False
                if (
                    rejudge_mode == "strict_match"
                    and rejudge_lecture_id
                    and rejudge_conf >= strict_min
                ):
                    adopt_pass2 = True
                elif (
                    rejudge_mode == "weak_match"
                    and rejudge_lecture_id
                    and weak_allow
                    and rejudge_conf >= weak_min
                ):
                    adopt_pass2 = True

                if adopt_pass2:
                    final_result.update(
                        {
                            "lecture_id": rejudge_lecture_id,
                            "confidence": rejudge_conf,
                            "reason": rejudge_result.get("reason") or final_result.get("reason", ""),
                            "evidence": rejudge_result.get("evidence") or [],
                            "no_match": False,
                            "decision_mode": rejudge_mode,
                            "final_decision_source": "pass2",
                        }
                    )

            return final_result

        except json.JSONDecodeError as e:
            return {
                "lecture_id": None,
                "confidence": 0.0,
                "reason": f"JSON parse error: {str(e)}",
                "study_hint": "",
                "evidence": [],
                "no_match": True,
                "model_name": self.model_name,
                "decision_mode": "no_match",
                "rejudge_attempted": False,
                "rejudge_decision_mode": None,
                "rejudge_confidence": None,
                "rejudge_reason": None,
                "final_decision_source": "pass1",
            }
        except Exception:
            raise  # tenacity가 재시도 처리


# ============================================================
# 비동기 배치 처리
# ============================================================


class AsyncBatchProcessor:
    """비동기 배치 분류 처리기"""

    _executor = ThreadPoolExecutor(max_workers=2)

    @classmethod
    def start_classification_job(
        cls,
        question_ids: List[int],
        request_meta: Optional[Dict] = None,
    ) -> int:
        """
        분류 작업 시작 (비동기)

        Returns:
            job_id: 생성된 작업 ID
        """
        # Job 생성
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING, total_count=len(question_ids)
        )
        job.result_json = json.dumps(
            build_job_payload(request_meta, []),
            ensure_ascii=False,
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id
        if _env_flag("CLASSIFIER_DEBUG_LOG", False):
            logger.warning(
                "CLASSIFIER_JOB_ENQUEUED job_id=%s total=%s request_signature=%s",
                job_id,
                len(question_ids),
                (request_meta or {}).get("signature"),
            )

        # 백그라운드 처리 시작
        cls._executor.submit(cls._process_job, job_id, question_ids)

        return job_id

    @classmethod
    def _process_job(cls, job_id: int, question_ids: List[int]):
        """백그라운드에서 분류 작업 수행"""
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
            if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                logger.warning(
                    "CLASSIFIER_JOB_STARTED job_id=%s total=%s request_signature=%s",
                    job_id,
                    len(question_ids),
                    request_meta.get("signature"),
                )

            retriever = LectureRetriever()
            retriever.refresh_cache()

            scope = normalize_classification_scope(request_meta.get("scope"))
            if scope:
                request_meta["scope"] = scope
            block_id = scope.get("block_id")
            folder_id = scope.get("folder_id")
            include_descendants = scope.get("include_descendants", True)
            has_stored_lecture_ids = "lecture_ids" in scope
            lecture_ids = scope.get("lecture_ids") if has_stored_lecture_ids else None
            if (not has_stored_lecture_ids) and (
                block_id is not None or folder_id is not None
            ):
                scope_user = None
                scope_user_id = normalize_scope_user_id(request_meta.get("scope_user_id"))
                if scope_user_id is not None:
                    scope_user = db.session.get(User, scope_user_id)
                lecture_ids = resolve_lecture_ids(
                    block_id,
                    folder_id,
                    include_descendants,
                    user=scope_user,
                    include_public=True,
                )
                if lecture_ids is not None:
                    scope["lecture_ids"] = sorted(set(lecture_ids))
                    request_meta["scope"] = scope

            results = []
            subject_scope_cache: Dict[str, Optional[List[int]]] = {}

            try:
                classifier = GeminiClassifier()
                cancelled = False

                for qid in question_ids:
                    db.session.refresh(job)
                    if job.status == ClassificationJob.STATUS_CANCELLED:
                        cancelled = True
                        break

                    question = db.session.get(Question, qid)
                    if not question:
                        job.failed_count += 1
                        job.processed_count += 1
                        continue

                    try:
                        choices = [
                            c.content
                            for c in question.choices.order_by("choice_number").all()
                        ]
                        question_text = question.content or ""
                        if choices:
                            question_text = f"{question_text}\n" + " ".join(choices)
                        question_text = question_text.strip()
                        if len(question_text) > 4000:
                            question_text = question_text[:4000]

                        effective_lecture_ids = lecture_ids
                        if effective_lecture_ids is None:
                            effective_lecture_ids = resolve_exam_subject_lecture_ids(
                                question, cache=subject_scope_cache
                            )

                        candidates = retriever.find_candidates(
                            question_text,
                            top_k=8,
                            question_id=question.id,
                            lecture_ids=effective_lecture_ids,
                        )

                        # Expand context only when unstable
                        if current_app.config.get("PARENT_ENABLED", False):
                            from app.services.context_expander import expand_candidates
                            from app.services import retrieval_features

                            artifacts = retrieval_features.build_retrieval_artifacts(
                                question_text,
                                question.id,
                                lecture_ids=effective_lecture_ids,
                            )
                            features = artifacts.features
                            auto_confirm = False
                            if current_app.config.get("AUTO_CONFIRM_V2_ENABLED", True):
                                auto_confirm = retrieval_features.auto_confirm_v2(
                                    features,
                                    delta=float(
                                        current_app.config.get(
                                            "AUTO_CONFIRM_V2_DELTA", 0.05
                                        )
                                    ),
                                    max_bm25_rank=int(
                                        current_app.config.get(
                                            "AUTO_CONFIRM_V2_MAX_BM25_RANK", 5
                                        )
                                    ),
                                )
                            uncertain = retrieval_features.is_uncertain(
                                features,
                                delta_uncertain=float(
                                    current_app.config.get(
                                        "AUTO_CONFIRM_V2_DELTA_UNCERTAIN", 0.03
                                    )
                                ),
                                min_chunk_len=int(
                                    current_app.config.get(
                                        "AUTO_CONFIRM_V2_MIN_CHUNK_LEN", 200
                                    )
                                ),
                                auto_confirm=auto_confirm,
                            )
                            if uncertain:
                                candidates = expand_candidates(candidates)

                        result = classifier.classify_single(question, candidates)
                        result["question_content"] = question.content or ""
                        result["question_choices"] = choices
                        result["candidate_ids"] = [
                            c.get("id") for c in candidates if c.get("id") is not None
                        ]
                        result["candidate_top_id"] = (
                            result["candidate_ids"][0]
                            if result["candidate_ids"]
                            else None
                        )

                        # 결과 저장 (DB에는 아직 반영하지 않음 - preview용)
                        result["question_id"] = qid
                        result["question_number"] = question.question_number
                        result["exam_title"] = (
                            question.exam.title if question.exam else ""
                        )

                        current_lecture = question.lecture
                        result["current_lecture_id"] = question.lecture_id
                        result["current_lecture_title"] = (
                            f"{current_lecture.block.name} > {current_lecture.title}"
                            if current_lecture
                            else None
                        )
                        result["current_block_name"] = (
                            current_lecture.block.name if current_lecture else None
                        )

                        if result["lecture_id"]:
                            lecture = db.session.get(Lecture, result["lecture_id"])
                            if lecture:
                                result["lecture_title"] = lecture.title
                                result["block_name"] = lecture.block.name
                            else:
                                result["lecture_title"] = None
                                result["block_name"] = None

                        suggested_id = result.get("lecture_id")
                        result["will_change"] = bool(
                            suggested_id and suggested_id != question.lecture_id
                        )

                        results.append(result)
                        job.success_count += 1
                        if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                            logger.warning(
                                "CLASSIFIER_JOB_TRACE job_id=%s qid=%s candidates=%s suggestion=%s no_match=%s conf=%.3f evidence=%s",
                                job_id,
                                qid,
                                len(candidates),
                                result.get("lecture_id"),
                                result.get("no_match"),
                                _coerce_confidence(result.get("confidence")),
                                len(result.get("evidence") or []),
                            )

                    except Exception as e:
                        results.append(
                            {
                                "question_id": qid,
                                "question_number": question.question_number,
                                "exam_title": question.exam.title
                                if question.exam
                                else "",
                                "question_content": question.content or "",
                                "question_choices": choices,
                                "current_lecture_id": question.lecture_id,
                                "current_lecture_title": (
                                    f"{question.lecture.block.name} > {question.lecture.title}"
                                    if question.lecture
                                    else None
                                ),
                                "current_block_name": (
                                    question.lecture.block.name
                                    if question.lecture
                                    else None
                                ),
                                "lecture_id": None,
                                "confidence": 0.0,
                                "reason": f"Error: {str(e)}",
                                "study_hint": "",
                                "evidence": [],
                                "no_match": True,
                                "decision_mode": "no_match",
                                "rejudge_attempted": False,
                                "rejudge_decision_mode": None,
                                "rejudge_confidence": None,
                                "rejudge_reason": None,
                                "final_decision_source": "pass1",
                                "error": True,
                                "will_change": False,
                            }
                        )
                        job.failed_count += 1
                        logger.exception(
                            "CLASSIFIER_JOB_QUESTION_FAILED job_id=%s qid=%s",
                            job_id,
                            qid,
                        )

                    job.processed_count += 1
                    db.session.commit()

                # 완료 / 취소
                db.session.refresh(job)
                if cancelled or job.status == ClassificationJob.STATUS_CANCELLED:
                    job.status = ClassificationJob.STATUS_CANCELLED
                    if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                        logger.warning(
                            "CLASSIFIER_JOB_CANCELLED job_id=%s processed=%s success=%s failed=%s",
                            job_id,
                            job.processed_count,
                            job.success_count,
                            job.failed_count,
                        )
                else:
                    job.status = ClassificationJob.STATUS_COMPLETED
                    if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                        logger.warning(
                            "CLASSIFIER_JOB_COMPLETED job_id=%s processed=%s success=%s failed=%s",
                            job_id,
                            job.processed_count,
                            job.success_count,
                            job.failed_count,
                        )
                job.result_json = json.dumps(
                    build_job_payload(request_meta, results),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.utcnow()

            except Exception as e:
                db.session.refresh(job)
                if job.status == ClassificationJob.STATUS_CANCELLED:
                    job.status = ClassificationJob.STATUS_CANCELLED
                else:
                    job.status = ClassificationJob.STATUS_FAILED
                    job.error_message = str(e)
                job.result_json = json.dumps(
                    build_job_payload(request_meta, results),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.utcnow()
                if job.status == ClassificationJob.STATUS_FAILED:
                    logger.exception(
                        "CLASSIFIER_JOB_FAILED job_id=%s processed=%s success=%s failed=%s",
                        job_id,
                        job.processed_count,
                        job.success_count,
                        job.failed_count,
                    )

            db.session.commit()


# ============================================================
# 유틸리티 함수
# ============================================================


def apply_classification_results(
    question_ids: List[int],
    job_id: int,
    apply_mode: str = "all",
    *,
    return_report: bool = False,
) -> int | tuple[int, Dict[str, Any]]:
    """
    분류 결과를 실제 DB에 적용

    Args:
        question_ids: 적용할 문제 ID 목록
        job_id: 분류 작업 ID
        apply_mode: 적용 모드 ('all', 'changed', 'high_confidence' 등)

    Returns:
        return_report=False: 적용된 문제 수
        return_report=True: (적용된 문제 수, 적용 진단 정보)
    """
    diagnostics: Dict[str, Any] = {
        "mode": apply_mode,
        "requested_count": len(question_ids),
        "with_result_count": 0,
        "missing_result_count": 0,
        "missing_question_count": 0,
        "out_of_candidates_count": 0,
        "no_match_count": 0,
        "no_final_id_count": 0,
        "config_disabled_count": 0,
        "low_confidence_count": 0,
        "weak_match_skip_count": 0,
        "weak_match_policy": (
            "decision_mode=weak_match is excluded from auto-apply and kept for review"
        ),
        "missing_final_lecture_count": 0,
        "applied_count": 0,
    }

    job = db.session.get(ClassificationJob, job_id)
    if not job or not job.result_json:
        return (0, diagnostics) if return_report else 0

    _, results = parse_job_payload(job.result_json)
    if not results:
        return (0, diagnostics) if return_report else 0

    def _safe_int(value: object) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    normalized_question_ids: List[int] = []
    for raw_qid in question_ids:
        qid = _safe_int(raw_qid)
        if qid is not None:
            normalized_question_ids.append(qid)

    results_map: Dict[int, Dict[str, Any]] = {}
    for result in results:
        qid = _safe_int(result.get("question_id"))
        if qid is None:
            continue
        results_map[qid] = result

    auto_apply = current_app.config.get("AI_AUTO_APPLY", False)
    threshold = float(current_app.config.get("AI_CONFIDENCE_THRESHOLD", 0.7))
    margin = float(current_app.config.get("AI_AUTO_APPLY_MARGIN", 0.2))
    auto_apply_min = threshold + margin

    hard_action = current_app.config.get("HARD_CANDIDATE_ACTION", "needs_review")
    cfg = get_config().experiment
    require_page_span = _env_flag(
        "CLASSIFIER_REQUIRE_PAGE_SPAN",
        bool(cfg.classifier_require_page_span),
    )

    unique_question_ids = sorted(set(normalized_question_ids))
    question_rows = (
        Question.query.filter(Question.id.in_(unique_question_ids)).all()
        if unique_question_ids
        else []
    )
    question_map = {question.id: question for question in question_rows}

    processing_rows: List[tuple[int, Question, Dict[str, Any]]] = []
    lecture_lookup_ids: set[int] = set()
    chunk_lookup_ids: set[int] = set()
    questions_to_reset: set[int] = set()

    for qid in normalized_question_ids:
        result = results_map.get(qid)
        if not result:
            diagnostics["missing_result_count"] += 1
            continue
        diagnostics["with_result_count"] += 1

        question = question_map.get(qid)
        if not question:
            diagnostics["missing_question_count"] += 1
            continue

        processing_rows.append((qid, question, result))
        questions_to_reset.add(question.id)

        lecture_lookup_id = _safe_int(result.get("lecture_id"))
        if lecture_lookup_id is not None:
            lecture_lookup_ids.add(lecture_lookup_id)

        candidate_ids = result.get("candidate_ids") or []
        if hard_action == "clamp_top1" and candidate_ids:
            top1_id = _safe_int(candidate_ids[0])
            if top1_id is not None:
                lecture_lookup_ids.add(top1_id)

        evidence_list = result.get("evidence") or []
        if not isinstance(evidence_list, list):
            continue
        for evidence in evidence_list:
            chunk_id = _safe_int(evidence.get("chunk_id"))
            if chunk_id is not None:
                chunk_lookup_ids.add(chunk_id)

    lecture_map: Dict[int, Dict[str, object]] = {}
    if lecture_lookup_ids:
        lecture_rows = (
            db.session.query(Lecture.id, Lecture.title, Block.name)
            .join(Block, Lecture.block_id == Block.id)
            .filter(Lecture.id.in_(lecture_lookup_ids))
            .all()
        )
        lecture_map = {
            int(lecture_id): {
                "id": int(lecture_id),
                "title": lecture_title or "",
                "block_name": block_name or "",
            }
            for lecture_id, lecture_title, block_name in lecture_rows
            if lecture_id is not None
        }

    chunk_map: Dict[int, LectureChunk] = {}
    if chunk_lookup_ids:
        chunk_rows = LectureChunk.query.filter(LectureChunk.id.in_(chunk_lookup_ids)).all()
        chunk_map = {chunk.id: chunk for chunk in chunk_rows}

    if questions_to_reset:
        QuestionChunkMatch.query.filter(
            QuestionChunkMatch.question_id.in_(questions_to_reset)
        ).delete(synchronize_session=False)

    applied_count = 0
    for qid, question, result in processing_rows:
        raw_lecture_id = result.get("lecture_id")
        lecture_id = _safe_int(raw_lecture_id)
        candidate_ids = result.get("candidate_ids") or []
        out_of_candidates = (
            raw_lecture_id is not None
            and bool(candidate_ids)
            and raw_lecture_id not in candidate_ids
        )

        no_match = bool(result.get("no_match", False))
        decision_mode = str(
            result.get("decision_mode") or ("no_match" if no_match else "strict_match")
        ).strip().lower()
        is_weak_match = decision_mode == "weak_match"
        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        lecture = lecture_map.get(lecture_id) if lecture_id is not None else None

        # --- Always persist AI suggested info ---
        if lecture and not no_match:
            question.ai_suggested_lecture_id = lecture["id"]
            block_name = str(lecture.get("block_name") or "")
            title = str(lecture.get("title") or "")
            question.ai_suggested_lecture_title_snapshot = (
                f"{block_name} > {title}" if block_name else title
            )
            if not question.is_classified:
                question.classification_status = "ai_suggested"
        else:
            question.ai_suggested_lecture_id = None
            question.ai_suggested_lecture_title_snapshot = None
            if not question.is_classified:
                question.classification_status = "manual"

        question.ai_confidence = confidence
        question.ai_reason = result.get("reason", "") or ""
        question.ai_model_name = result.get("model_name", "") or ""
        question.ai_classified_at = datetime.utcnow()

        # --- Hard candidate constraint (out-of-candidate handling) ---
        final_lecture_id = raw_lecture_id
        if out_of_candidates:
            if hard_action == "clamp_top1" and candidate_ids:
                final_lecture_id = candidate_ids[0]
            else:
                final_lecture_id = None
            question.classification_status = "needs_review"

        final_lecture_lookup_id = _safe_int(final_lecture_id)
        question.ai_final_lecture_id = final_lecture_lookup_id

        # --- Always persist evidence (QuestionChunkMatch) ---
        evidence_list = result.get("evidence") or []
        if isinstance(evidence_list, list) and evidence_list:
            matches: List[QuestionChunkMatch] = []
            seen_match_keys: set[tuple[int, int, str]] = set()
            for evidence in evidence_list:
                chunk_id = _safe_int(evidence.get("chunk_id"))
                if chunk_id is None:
                    continue

                chunk = chunk_map.get(chunk_id)
                if not chunk:
                    # Postgres enforces FK(question_chunk_matches.chunk_id -> lecture_chunks.id).
                    # Skip orphan evidence entries instead of failing the whole apply transaction.
                    continue

                evidence_lecture_id = _safe_int(
                    evidence.get("lecture_id")
                    or (lecture["id"] if lecture else None)
                    or (chunk.lecture_id if chunk else None)
                )
                if evidence_lecture_id is None:
                    continue

                snippet = (
                    evidence.get("quote")
                    or evidence.get("snippet")
                    or (chunk.content if chunk else "")
                )
                snippet = (snippet or "").strip()
                if len(snippet) > 500:
                    snippet = snippet[:497] + "..."

                page_start = evidence.get("page_start") or (chunk.page_start if chunk else None)
                page_end = evidence.get("page_end") or (chunk.page_end if chunk else None)
                if require_page_span and (page_start is None or page_end is None):
                    continue

                source = "ai"
                match_key = (question.id, chunk_id, source)
                if match_key in seen_match_keys:
                    continue
                seen_match_keys.add(match_key)

                matches.append(
                    QuestionChunkMatch(
                        question_id=question.id,
                        lecture_id=evidence_lecture_id,
                        chunk_id=chunk_id,
                        material_id=(chunk.material_id if chunk else None),
                        page_start=page_start,
                        page_end=page_end,
                        snippet=snippet,
                        score=evidence.get("score") or confidence,
                        source=source,
                        job_id=job_id,
                        is_primary=(len(matches) == 0),
                    )
                )

            if matches:
                db.session.add_all(matches)

        # --- If out-of-candidates, never auto-apply; keep for review ---
        if out_of_candidates:
            diagnostics["out_of_candidates_count"] += 1
            if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                logger.warning(
                    "CLASSIFIER_APPLY_SKIP job_id=%s qid=%s reason=out_of_candidates lecture_id=%s candidates=%s",
                    job_id,
                    qid,
                    raw_lecture_id,
                    candidate_ids,
                )
            continue

        # --- Auto-confirm decision logging ---
        # When apply_mode is 'all', user explicitly clicked apply so bypass auto_apply config
        force_apply = apply_mode == "all"
        is_pass = (
            (force_apply or auto_apply)
            and final_lecture_id
            and (not no_match)
            and (force_apply or not is_weak_match)
            and (force_apply or confidence >= auto_apply_min)
        )
        fail_reason = []
        if not force_apply and not auto_apply:
            fail_reason.append("config_disabled")
        if not final_lecture_id:
            fail_reason.append("no_final_id")
        if no_match:
            fail_reason.append("is_no_match")
        if not force_apply and is_weak_match:
            fail_reason.append("weak_match_not_auto_apply")
        if not force_apply and confidence < auto_apply_min:
            fail_reason.append(f"low_conf({confidence:.2f}<{auto_apply_min:.2f})")

        if no_match:
            diagnostics["no_match_count"] += 1
        if not final_lecture_id:
            diagnostics["no_final_id_count"] += 1
        if not force_apply and not auto_apply:
            diagnostics["config_disabled_count"] += 1
        if not force_apply and is_weak_match:
            diagnostics["weak_match_skip_count"] += 1
        if not force_apply and confidence < auto_apply_min:
            diagnostics["low_confidence_count"] += 1

        if _env_flag("CLASSIFIER_DEBUG_LOG", False):
            logger.warning(
                "CLASSIFIER_APPLY_DECISION job_id=%s qid=%s model=%s conf=%.2f threshold=%.2f pass=%s reason=%s mode=%s",
                job_id,
                qid,
                result.get("model_name"),
                confidence,
                auto_apply_min,
                is_pass,
                ",".join(fail_reason) or "none",
                apply_mode,
            )

        # --- Apply to question only when all conditions satisfied ---
        if is_pass:
            final_lecture = (
                lecture_map.get(final_lecture_lookup_id)
                if final_lecture_lookup_id is not None
                else None
            )
            if not final_lecture:
                diagnostics["missing_final_lecture_count"] += 1
                continue
            question.lecture_id = final_lecture["id"]
            question.is_classified = True
            question.classification_status = "ai_confirmed"
            applied_count += 1
            if _env_flag("CLASSIFIER_DEBUG_LOG", False):
                logger.warning(
                    "CLASSIFIER_APPLY_CONFIRMED job_id=%s qid=%s lecture_id=%s conf=%.2f",
                    job_id,
                    qid,
                    final_lecture["id"],
                    confidence,
                )

    db.session.commit()
    diagnostics["applied_count"] = applied_count
    return (applied_count, diagnostics) if return_report else applied_count
