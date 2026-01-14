from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def _safe_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _merged_filename(qnum) -> str:
    if isinstance(qnum, int):
        return f"Q{qnum:02d}_merged.png"
    return f"Q{qnum}_merged.png"


def _union_bbox(parts) -> Optional[list[float]]:
    if not parts:
        return None
    bboxes = []
    for part in parts:
        bbox = part.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            bboxes.append(bbox)
    if not bboxes:
        return None
    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    y1 = max(b[3] for b in bboxes)
    return [x0, y0, x1, y1]


def _resolve_upload_folder(upload_folder: Optional[os.PathLike] = None) -> Path:
    if upload_folder is not None:
        return Path(upload_folder)
    try:
        from flask import current_app
    except RuntimeError:
        raise RuntimeError("Flask app context is required to resolve UPLOAD_FOLDER.")
    resolved = current_app.config.get("UPLOAD_FOLDER")
    if resolved:
        return Path(resolved)
    return Path(current_app.static_folder) / "uploads"


def _resolve_static_root(static_root: Optional[os.PathLike] = None) -> Path:
    if static_root is not None:
        return Path(static_root)
    try:
        from flask import current_app
    except RuntimeError:
        raise RuntimeError("Flask app context is required to resolve static folder.")
    return Path(current_app.static_folder)


def get_exam_crop_dir(exam_id: int, upload_folder: Optional[os.PathLike] = None) -> Path:
    upload_root = _resolve_upload_folder(upload_folder)
    return upload_root / "exam_crops" / f"exam_{exam_id}"


def crop_pdf_to_questions(
    pdf_path: os.PathLike,
    exam_id: int,
    upload_folder: Optional[os.PathLike] = None,
    dpi: int = 200,
    **kwargs: Any,
) -> Dict[str, Any]:
    output_dir = get_exam_crop_dir(exam_id, upload_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from app.routes.crop import crop_with_merge_contentaware
    except Exception as exc:  # pragma: no cover - import-time error surface
        raise RuntimeError("PyMuPDF is required for PDF cropping.") from exc

    crop_with_merge_contentaware(pdf_path=str(pdf_path), out_dir=str(output_dir), dpi=dpi, **kwargs)

    meta_path = output_dir / "bboxes.json"
    meta = None
    question_images: Dict[int, str] = {}

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for q in meta.get("questions", []):
            qnum = q.get("qnum")
            qnum_int = _safe_int(qnum)
            merged_name = _merged_filename(qnum_int if qnum_int is not None else qnum)
            final_name = _ensure_final_image(output_dir, q, merged_name)
            q["final_image"] = final_name
            q["final_bbox"] = _union_bbox(q.get("parts") or [])
            if qnum_int is not None and final_name:
                question_images[qnum_int] = final_name

        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output_dir": output_dir,
        "meta_path": meta_path if meta_path.exists() else None,
        "meta": meta,
        "question_images": question_images,
    }


def _ensure_final_image(output_dir: Path, q: Dict[str, Any], merged_name: str) -> Optional[str]:
    merged_path = output_dir / merged_name
    if merged_path.exists():
        return merged_name

    for part in q.get("parts") or []:
        image = part.get("image")
        if not image:
            continue
        src_path = output_dir / image
        if not src_path.exists():
            continue
        try:
            shutil.copyfile(src_path, merged_path)
            return merged_name
        except OSError:
            return image
    return None


def load_exam_crop_meta(
    exam_id: int, upload_folder: Optional[os.PathLike] = None
) -> Optional[Dict[str, Any]]:
    meta_path = get_exam_crop_dir(exam_id, upload_folder) / "bboxes.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def find_question_crop_image(
    exam_id: int,
    question_number: int,
    upload_folder: Optional[os.PathLike] = None,
) -> Optional[Path]:
    crop_dir = get_exam_crop_dir(exam_id, upload_folder)
    if not crop_dir.exists():
        return None

    meta = load_exam_crop_meta(exam_id, upload_folder)
    if meta:
        for q in meta.get("questions", []):
            qnum = _safe_int(q.get("qnum"))
            if qnum != question_number:
                continue
            final_image = q.get("final_image")
            if final_image:
                candidate = crop_dir / final_image
                if candidate.exists():
                    return candidate
            for part in q.get("parts") or []:
                image = part.get("image")
                if not image:
                    continue
                candidate = crop_dir / image
                if candidate.exists():
                    return candidate

    padded_name = _merged_filename(question_number)
    padded_path = crop_dir / padded_name
    if padded_path.exists():
        return padded_path

    raw_name = f"Q{question_number}_merged.png"
    raw_path = crop_dir / raw_name
    if raw_path.exists():
        return raw_path

    fallback = next(crop_dir.glob(f"Q{question_number:02d}_p*_part*.png"), None)
    if fallback:
        return fallback

    return None


def to_static_relative(
    path: os.PathLike, static_root: Optional[os.PathLike] = None
) -> Optional[str]:
    try:
        static_root_path = _resolve_static_root(static_root).resolve()
        target_path = Path(path).resolve()
        return target_path.relative_to(static_root_path).as_posix()
    except ValueError:
        return None
