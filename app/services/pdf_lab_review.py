from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.services.pdf_lab_parser import parse_pdf_to_lab_questions
from app.services.pdf_parser_factory import parse_pdf

REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_OK = "ok"
REVIEW_STATUS_ISSUE = "issue"
VALID_REVIEW_STATUSES = {
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_OK,
    REVIEW_STATUS_ISSUE,
}

_MERGED_CROP_RE = re.compile(r"^Q(?P<qnum>\d+)_merged\.png$")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def resolve_lab_root(root_dir: str | Path | None = None) -> Path:
    if root_dir is not None:
        return Path(root_dir).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "parse_lab" / "review_sessions"


def resolve_session_dir(
    session_id: str,
    root_dir: str | Path | None = None,
) -> Path:
    root = resolve_lab_root(root_dir)
    session_dir = (root / session_id).resolve()
    if session_dir.parent != root:
        raise ValueError("Invalid session id.")
    return session_dir


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_question_number(question: dict[str, Any], fallback: int) -> int:
    try:
        return int(question.get("question_number") or fallback)
    except (TypeError, ValueError):
        return fallback


def _normalize_questions(parsed_questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, question in enumerate(parsed_questions, start=1):
        item = dict(question)
        item["review_index"] = index
        item["question_number"] = _safe_question_number(item, index)
        normalized.append(item)
    return normalized


def _initial_review_payload(questions: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for question in questions:
        items.append(
            {
                "review_index": question["review_index"],
                "question_number": question["question_number"],
                "status": REVIEW_STATUS_PENDING,
                "comment": "",
                "updated_at": None,
            }
        )
    return {
        "updated_at": _utcnow_iso(),
        "items": items,
    }


def _ensure_review_integrity(
    review_payload: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    items = review_payload.get("items")
    if not isinstance(items, list):
        return _initial_review_payload(questions)

    item_map: dict[int, dict[str, Any]] = {}
    for item in items:
        try:
            review_index = int(item.get("review_index"))
        except (TypeError, ValueError):
            continue
        item_map[review_index] = {
            "review_index": review_index,
            "question_number": int(item.get("question_number") or review_index),
            "status": item.get("status")
            if item.get("status") in VALID_REVIEW_STATUSES
            else REVIEW_STATUS_PENDING,
            "comment": (item.get("comment") or "").strip(),
            "updated_at": item.get("updated_at"),
        }

    merged_items = []
    for question in questions:
        review_index = int(question["review_index"])
        current = item_map.get(review_index)
        if current is None:
            current = {
                "review_index": review_index,
                "question_number": int(question["question_number"]),
                "status": REVIEW_STATUS_PENDING,
                "comment": "",
                "updated_at": None,
            }
        merged_items.append(current)

    return {
        "updated_at": review_payload.get("updated_at") or _utcnow_iso(),
        "items": merged_items,
    }


def _content_excerpt(question: dict[str, Any], limit: int = 140) -> str:
    text = " ".join(str(question.get("content") or "").split())
    if not text:
        return "(empty)"
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_crop_lookup(crops_dir: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    meta = _read_json(crops_dir / "bboxes.json", {})
    if isinstance(meta, dict):
        counts: dict[int, int] = {}
        for item in meta.get("questions", []):
            try:
                qnum = int(item.get("qnum"))
            except (TypeError, ValueError):
                continue
            counts[qnum] = counts.get(qnum, 0) + 1
        duplicate_qnums = {
            int(qnum)
            for qnum in meta.get("duplicate_qnums", [])
            if isinstance(qnum, int)
        }
        duplicate_qnums.update(
            qnum for qnum, count in counts.items() if count > 1
        )

        for item in meta.get("questions", []):
            try:
                qnum = int(item.get("qnum"))
            except (TypeError, ValueError):
                continue
            if str(qnum) in lookup:
                continue
            candidates: list[str] = []
            final_image = item.get("final_image")
            if isinstance(final_image, str) and final_image:
                candidates.append(final_image)

            if qnum not in duplicate_qnums:
                candidates.extend(
                    [
                        f"Q{qnum:02d}_merged.png",
                        f"Q{qnum}_merged.png",
                    ]
                )

            parts = item.get("parts") or []
            if len(parts) == 1:
                image = parts[0].get("image")
                if image:
                    candidates.append(str(image))
            for part in parts:
                image = part.get("image")
                if image:
                    candidates.append(str(image))

            for filename in candidates:
                if not filename:
                    continue
                if (crops_dir / filename).exists():
                    lookup[str(qnum)] = str(filename)
                    break

    for image_path in crops_dir.glob("Q*_merged.png"):
        match = _MERGED_CROP_RE.match(image_path.name)
        if not match:
            continue
        try:
            qnum = int(match.group("qnum"))
        except ValueError:
            continue
        lookup.setdefault(str(qnum), image_path.name)

    return lookup


def _build_report_payload(
    meta: dict[str, Any],
    questions: list[dict[str, Any]],
    review_payload: dict[str, Any],
) -> dict[str, Any]:
    review_items = _ensure_review_integrity(review_payload, questions)["items"]
    review_map = {int(item["review_index"]): item for item in review_items}

    question_rows = []
    for question in questions:
        review = review_map[int(question["review_index"])]
        question_rows.append(
            {
                "review_index": int(question["review_index"]),
                "question_number": int(question["question_number"]),
                "status": review["status"],
                "comment": review["comment"],
                "updated_at": review["updated_at"],
                "excerpt": _content_excerpt(question),
            }
        )

    pending_count = sum(
        1 for item in question_rows if item["status"] == REVIEW_STATUS_PENDING
    )
    ok_count = sum(1 for item in question_rows if item["status"] == REVIEW_STATUS_OK)
    issue_count = sum(
        1 for item in question_rows if item["status"] == REVIEW_STATUS_ISSUE
    )
    reviewed_count = len(question_rows) - pending_count
    issues = [item for item in question_rows if item["status"] == REVIEW_STATUS_ISSUE]

    return {
        "session": {
            "id": meta["id"],
            "title": meta["title"],
            "parser_mode": meta["parser_mode"],
            "source_filename": meta["source_filename"],
            "created_at": meta["created_at"],
            "created_by": meta.get("created_by"),
        },
        "summary": {
            "question_count": len(question_rows),
            "reviewed_count": reviewed_count,
            "pending_count": pending_count,
            "ok_count": ok_count,
            "issue_count": issue_count,
        },
        "issues": issues,
        "questions": question_rows,
    }


def _build_report_markdown(
    meta: dict[str, Any],
    report_payload: dict[str, Any],
) -> str:
    summary = report_payload["summary"]
    lines = [
        "# PDF Lab Review Report",
        "",
        f"- Session ID: {meta['id']}",
        f"- Title: {meta['title']}",
        f"- Source PDF: {meta['source_filename']}",
        f"- Parser Mode: {meta['parser_mode']}",
        f"- Created At: {meta['created_at']}",
        f"- Created By: {meta.get('created_by') or '-'}",
        (
            "- Review Progress: "
            f"{summary['reviewed_count']}/{summary['question_count']} reviewed"
        ),
        f"- Issue Count: {summary['issue_count']}",
        f"- Pending Count: {summary['pending_count']}",
        "",
        "## Flagged Questions",
        "",
    ]

    issues = report_payload.get("issues") or []
    if not issues:
        lines.append("- None")
    else:
        for item in issues:
            lines.extend(
                [
                    f"### Review {item['review_index']} (Q{item['question_number']})",
                    f"- Excerpt: {item['excerpt']}",
                    f"- Comment: {item['comment'] or '-'}",
                    f"- Updated At: {item['updated_at'] or '-'}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def refresh_session_report(
    session_id: str,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session_id, root_dir=root_dir)
    meta = _read_json(session_dir / "session.json", None)
    if not isinstance(meta, dict):
        raise FileNotFoundError("Session metadata not found.")
    questions = _read_json(session_dir / "questions.json", {}).get("questions") or []
    review_payload = _ensure_review_integrity(
        _read_json(session_dir / "review.json", {}),
        questions,
    )
    _write_json(session_dir / "review.json", review_payload)

    report_payload = _build_report_payload(meta, questions, review_payload)
    _write_json(session_dir / "report.json", report_payload)
    (session_dir / "report.md").write_text(
        _build_report_markdown(meta, report_payload),
        encoding="utf-8",
    )
    return report_payload


def create_session(
    *,
    file_storage: FileStorage,
    title: str | None,
    parser_mode: str,
    created_by: str | None,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    original_name = Path(file_storage.filename or "upload.pdf").name
    safe_name = secure_filename(original_name) or "upload"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    session_title = (title or "").strip() or Path(original_name).stem or "PDF Lab Session"
    session_id = (
        datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    )

    root = resolve_lab_root(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    session_dir = resolve_session_dir(session_id, root_dir=root)
    parser_media_dir = session_dir / "parser_media"
    crops_dir = session_dir / "crops"
    source_pdf_path = session_dir / safe_name
    session_dir.mkdir(parents=True, exist_ok=False)
    parser_media_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_storage.save(source_pdf_path)
        exam_prefix = secure_filename(session_title.replace(" ", "_"))[:20] or "lab"
        if parser_mode == "legacy":
            parsed_questions = parse_pdf_to_lab_questions(
                pdf_path=source_pdf_path,
                upload_dir=parser_media_dir,
                exam_prefix=exam_prefix,
            )
        else:
            parsed_questions = parse_pdf(
                pdf_path=source_pdf_path,
                upload_dir=parser_media_dir,
                exam_prefix=exam_prefix,
                mode=parser_mode,
            )
        normalized_questions = _normalize_questions(parsed_questions)
        if not normalized_questions:
            raise ValueError("문제를 추출할 수 없습니다. PDF 형식을 확인해주세요.")

        crop_error = None
        crop_lookup: dict[str, str] = {}
        try:
            from app.routes.crop import crop_with_merge_contentaware

            crop_with_merge_contentaware(
                pdf_path=str(source_pdf_path),
                out_dir=str(crops_dir),
            )
            crop_lookup = _build_crop_lookup(crops_dir)
        except Exception as exc:  # noqa: BLE001
            crop_error = str(exc)

        meta = {
            "id": session_id,
            "title": session_title,
            "source_filename": original_name,
            "stored_pdf_name": safe_name,
            "parser_mode": parser_mode,
            "created_at": _utcnow_iso(),
            "created_by": created_by,
            "question_count": len(normalized_questions),
            "choice_count": sum(
                len(question.get("options", [])) for question in normalized_questions
            ),
            "crop_image_count": len(crop_lookup),
            "crop_error": crop_error,
            "crop_images": crop_lookup,
        }
        _write_json(session_dir / "session.json", meta)
        _write_json(session_dir / "questions.json", {"questions": normalized_questions})
        _write_json(
            session_dir / "review.json",
            _initial_review_payload(normalized_questions),
        )
        refresh_session_report(session_id, root_dir=root)
        return meta
    except Exception:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise


def delete_session(
    session_id: str,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session_id, root_dir=root_dir)
    if not session_dir.exists() or not session_dir.is_dir():
        raise FileNotFoundError("Session not found.")

    meta = _read_json(session_dir / "session.json", None)
    if not isinstance(meta, dict):
        raise FileNotFoundError("Session metadata not found.")

    shutil.rmtree(session_dir)
    return meta


def list_sessions(
    root_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    root = resolve_lab_root(root_dir)
    if not root.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for session_dir in sorted(root.iterdir(), reverse=True):
        if not session_dir.is_dir():
            continue
        meta = _read_json(session_dir / "session.json", None)
        report = _read_json(session_dir / "report.json", None)
        if not isinstance(meta, dict):
            continue
        summary = report.get("summary") if isinstance(report, dict) else {}
        sessions.append(
            {
                **meta,
                "summary": summary or {
                    "question_count": meta.get("question_count", 0),
                    "reviewed_count": 0,
                    "pending_count": meta.get("question_count", 0),
                    "ok_count": 0,
                    "issue_count": 0,
                },
            }
        )
    return sessions


def load_session_bundle(
    session_id: str,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    session_dir = resolve_session_dir(session_id, root_dir=root_dir)
    if not session_dir.exists():
        raise FileNotFoundError("Session not found.")

    meta = _read_json(session_dir / "session.json", None)
    if not isinstance(meta, dict):
        raise FileNotFoundError("Session metadata not found.")

    questions_payload = _read_json(session_dir / "questions.json", {})
    questions = questions_payload.get("questions") or []
    review_payload = _ensure_review_integrity(
        _read_json(session_dir / "review.json", {}),
        questions,
    )
    _write_json(session_dir / "review.json", review_payload)
    report_payload = refresh_session_report(session_id, root_dir=root_dir)
    return {
        "meta": meta,
        "questions": questions,
        "review": review_payload,
        "report": report_payload,
        "session_dir": session_dir,
    }


def update_question_review(
    *,
    session_id: str,
    review_index: int,
    status: str,
    comment: str,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid review status.")

    bundle = load_session_bundle(session_id, root_dir=root_dir)
    review_payload = bundle["review"]
    updated = False
    for item in review_payload["items"]:
        if int(item["review_index"]) != int(review_index):
            continue
        item["status"] = status
        item["comment"] = comment.strip()
        item["updated_at"] = _utcnow_iso()
        updated = True
        break
    if not updated:
        raise FileNotFoundError("Question review entry not found.")

    review_payload["updated_at"] = _utcnow_iso()
    _write_json(bundle["session_dir"] / "review.json", review_payload)
    report_payload = refresh_session_report(session_id, root_dir=root_dir)
    return {
        "review": review_payload,
        "report": report_payload,
    }


def resolve_session_file(
    session_id: str,
    relative_path: str,
    root_dir: str | Path | None = None,
) -> Path:
    session_dir = resolve_session_dir(session_id, root_dir=root_dir)
    target = (session_dir / relative_path).resolve()
    if session_dir not in target.parents and target != session_dir:
        raise ValueError("Invalid asset path.")
    return target
