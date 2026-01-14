from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

import pdfplumber
from sqlalchemy import text

from flask import current_app

from app import db
from app.models import LectureMaterial, LectureChunk

FTS_TABLE = "lecture_chunks_fts"


def extract_pdf_pages(pdf_path: os.PathLike) -> List[Tuple[int, str]]:
    pages: List[Tuple[int, str]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text_content = page.extract_text() or ""
            text_content = text_content.replace("\u00A0", " ")
            text_content = re.sub(r"[ \t]+", " ", text_content)
            text_content = re.sub(r"\n{3,}", "\n\n", text_content)
            text_content = text_content.strip()
            if not text_content:
                continue
            pages.append((page_num, text_content))
    return pages


def chunk_pages(
    pages: List[Tuple[int, str]],
    target_chars: int = 1800,
    max_chars: int = 2600,
) -> List[Dict]:
    chunks: List[Dict] = []
    pending_short: List[Tuple[int, str]] = []
    current_text = ""
    current_start = None
    current_end = None

    def _flush():
        nonlocal current_text, current_start, current_end
        if not current_text:
            return
        content = current_text.strip()
        if not content:
            current_text = ""
            current_start = None
            current_end = None
            return
        chunks.append({
            "page_start": current_start,
            "page_end": current_end,
            "content": content,
            "char_len": len(content),
        })
        current_text = ""
        current_start = None
        current_end = None

    for page_num, text_content in pages:
        if len(text_content) < 20:
            if current_text:
                current_text = f"{current_text}\n{text_content}".strip()
                current_end = page_num
            else:
                pending_short.append((page_num, text_content))
            continue

        if not current_text and pending_short:
            current_start = pending_short[0][0]
            current_end = pending_short[-1][0]
            current_text = "\n".join([t for _, t in pending_short if t]).strip()
            pending_short = []

        if not current_text:
            current_start = page_num
            current_text = text_content
        else:
            current_text = f"{current_text}\n{text_content}"
        current_end = page_num

        if len(current_text) >= max_chars or len(current_text) >= target_chars:
            _flush()

    if current_text:
        _flush()

    return chunks


def _resolve_material_path(file_path: str) -> Path:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        upload_folder = Path(current_app.static_folder) / 'uploads'
    return Path(upload_folder) / file_path


def _delete_fts_rows(chunk_ids: List[int]) -> None:
    if not chunk_ids:
        return
    placeholders = ", ".join([f":id_{idx}" for idx in range(len(chunk_ids))])
    params = {f"id_{idx}": cid for idx, cid in enumerate(chunk_ids)}
    db.session.execute(
        text(f"DELETE FROM {FTS_TABLE} WHERE chunk_id IN ({placeholders})"),
        params,
    )


def _insert_fts_rows(chunks: List[LectureChunk]) -> None:
    if not chunks:
        return
    payload = [
        {
            "content": chunk.content,
            "chunk_id": chunk.id,
            "lecture_id": chunk.lecture_id,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }
        for chunk in chunks
    ]
    db.session.execute(
        text(
            f"""
            INSERT INTO {FTS_TABLE}
                (content, chunk_id, lecture_id, page_start, page_end)
            VALUES
                (:content, :chunk_id, :lecture_id, :page_start, :page_end)
            """
        ),
        payload,
    )


def index_material(
    material: LectureMaterial,
    target_chars: int = 1800,
    max_chars: int = 2600,
) -> Dict[str, int]:
    try:
        material_path = _resolve_material_path(material.file_path)
        pages = extract_pdf_pages(material_path)
        chunk_defs = chunk_pages(pages, target_chars=target_chars, max_chars=max_chars)

        existing_chunks = LectureChunk.query.filter_by(material_id=material.id).all()
        existing_ids = [c.id for c in existing_chunks]
        if existing_ids:
            _delete_fts_rows(existing_ids)
            LectureChunk.query.filter_by(material_id=material.id).delete(synchronize_session=False)

        chunk_rows = []
        for chunk in chunk_defs:
            chunk_rows.append(
                LectureChunk(
                    lecture_id=material.lecture_id,
                    material_id=material.id,
                    page_start=chunk["page_start"],
                    page_end=chunk["page_end"],
                    content=chunk["content"],
                    char_len=chunk["char_len"],
                )
            )
        db.session.add_all(chunk_rows)
        db.session.flush()
        _insert_fts_rows(chunk_rows)

        material.status = LectureMaterial.STATUS_INDEXED
        material.indexed_at = datetime.utcnow()
        db.session.commit()

        return {"chunks": len(chunk_rows), "pages": len(pages)}
    except Exception:
        db.session.rollback()
        material.status = LectureMaterial.STATUS_FAILED
        material.indexed_at = None
        db.session.add(material)
        db.session.commit()
        raise
