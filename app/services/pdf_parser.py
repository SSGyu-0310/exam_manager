#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 문제 파서 - 프로젝트 통합 버전
PDF를 파싱하여 직접 DB에 저장하고 이미지는 static/uploads/에 저장
"""

import re
import hashlib
from pathlib import Path
from collections import Counter
from io import BytesIO

import pdfplumber


CID_RE = re.compile(r"\(cid:\d+\)")
Q_HEADER = re.compile(r"^\s*(\d{1,3})\.(?!\d)\s*(.*)$")     # 1. 문항 시작
OPT_RE = re.compile(r"^([1-5])\)\s*(.+)$")         # 1) 선지 시작


def clean_text(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = CID_RE.sub("", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def detect_answer_color(pdf: pdfplumber.PDF, max_pages=None):
    """
    PDF에서 가장 많이 등장하는 RGB(3원소) 색 중 검정/흰색이 아닌 것을 '정답색'으로 추정.
    """
    counter = Counter()
    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]

    for page in pages:
        for c in page.chars:
            col = c.get("non_stroking_color")
            if isinstance(col, (list, tuple)) and len(col) == 3:
                col = tuple(round(float(x), 5) for x in col)
                counter[col] += 1

    if not counter:
        return None

    for col, _ in counter.most_common():
        if sum(abs(x) for x in col) < 0.001:        # black-ish
            continue
        if sum(abs(x - 1) for x in col) < 0.001:    # white-ish
            continue
        return col

    return counter.most_common(1)[0][0]


def color_distance(c1, c2) -> float:
    return float(sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5)


def extract_events(pdf, answer_color, y_tol=3, min_image_area=2000):
    """
    페이지를 위->아래 순서로 '텍스트 라인' + '이미지' 이벤트로 뽑는다.
    """
    events = []

    for pno, page in enumerate(pdf.pages, start=1):
        # --- text lines ---
        words = page.extract_words(extra_attrs=["non_stroking_color"]) or []
        for w in words:
            col = w.get("non_stroking_color")
            if isinstance(col, (list, tuple)) and len(col) == 3:
                w["color"] = tuple(round(float(x), 5) for x in col)
            else:
                w["color"] = None

        words_sorted = sorted(words, key=lambda w: (w["top"], w["x0"]))

        # 라인 클러스터링
        clusters = []
        cur = []
        cur_top = None
        for w in words_sorted:
            if cur_top is None or abs(w["top"] - cur_top) <= y_tol:
                cur.append(w)
                cur_top = w["top"] if cur_top is None else (cur_top + w["top"]) / 2
            else:
                clusters.append(cur)
                cur = [w]
                cur_top = w["top"]
        if cur:
            clusters.append(cur)

        for ws in clusters:
            ws = sorted(ws, key=lambda w: w["x0"])
            text = clean_text(" ".join(w["text"] for w in ws))
            if not text:
                continue

            total_chars = sum(len(clean_text(w["text"])) for w in ws) or 1
            key_chars = 0
            for w in ws:
                col = w.get("color")
                if isinstance(col, tuple) and answer_color and color_distance(col, answer_color) < 0.02:
                    key_chars += len(clean_text(w["text"]))

            has_key = (key_chars / total_chars) > 0.2

            events.append(
                {
                    "type": "text",
                    "page": pno,
                    "top": float(min(w["top"] for w in ws)),
                    "x0": float(min(w["x0"] for w in ws)),
                    "text": text,
                    "has_key": has_key,
                }
            )

        # --- images ---
        for img in page.images or []:
            w = float(img["x1"] - img["x0"])
            h = float(img["bottom"] - img["top"])
            if w * h < min_image_area:
                continue

            events.append(
                {
                    "type": "image",
                    "page": pno,
                    "top": float(img["top"]),
                    "x0": float(img["x0"]),
                    "x1": float(img["x1"]),
                    "bottom": float(img["bottom"]),
                    "page_obj": page,
                }
            )

    events.sort(key=lambda d: (d["page"], d["top"], d["x0"], 0 if d["type"] == "text" else 1))
    return events


def save_image_crop(page, bbox, upload_dir: Path, exam_prefix: str, resolution=200) -> str:
    """
    bbox 영역을 PNG로 래스터라이즈한 뒤 sha1 해시로 파일명 생성.
    파일은 upload_dir에 저장하고 파일명만 반환 (DB 저장용)
    """
    cropped = page.crop(bbox)
    page_image = cropped.to_image(resolution=resolution)

    buf = BytesIO()
    page_image.original.save(buf, format="PNG")
    data = buf.getvalue()

    h = hashlib.sha1(data).hexdigest()[:16]
    fname = f"{exam_prefix}_{h}.png"
    out_path = upload_dir / fname
    if not out_path.exists():
        out_path.write_bytes(data)
    return fname


def parse_pdf_to_questions(pdf_path, upload_dir: Path, exam_prefix: str):
    """
    PDF를 파싱하여 문제 데이터 리스트 반환
    
    Returns:
        list of dict: 각 문제의 데이터
        {
            'question_number': int,
            'content': str,
            'image_path': str or None,  # 문제 이미지 (첫번째만)
            'options': [
                {'number': 1, 'content': str, 'image_path': str or None, 'is_correct': bool},
                ...
            ],
            'answer_options': [int],  # 정답 번호 리스트
            'answer_text': str,
        }
    """
    pdf_path = Path(pdf_path)
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    questions = []
    
    with pdfplumber.open(str(pdf_path)) as pdf:
        answer_color = detect_answer_color(pdf)
        events = extract_events(pdf, answer_color)
        
        cur = None
        cur_opt = None
        
        for ev in events:
            if ev["type"] == "text":
                txt = ev["text"]

                m_q = Q_HEADER.match(txt)
                if m_q:
                    if cur:
                        questions.append(cur)
                    cur = {
                        "question_number": int(m_q.group(1)),
                        "content": m_q.group(2).strip(),
                        "image_path": None,
                        "options": [
                            {"number": i, "content": "", "image_path": None, "is_correct": False}
                            for i in range(1, 6)
                        ],
                    }
                    cur_opt = None
                    continue

                if not cur:
                    continue

                m_opt = OPT_RE.match(txt)
                if m_opt:
                    idx = int(m_opt.group(1)) - 1
                    cur_opt = idx
                    cur["options"][idx]["content"] = m_opt.group(2).strip()
                    cur["options"][idx]["is_correct"] = cur["options"][idx]["is_correct"] or ev["has_key"]
                    continue

                # 이어지는 줄 처리
                if cur_opt is not None:
                    cur["options"][cur_opt]["content"] = (cur["options"][cur_opt]["content"] + " " + txt).strip()
                    cur["options"][cur_opt]["is_correct"] = cur["options"][cur_opt]["is_correct"] or ev["has_key"]
                else:
                    cur["content"] = (cur["content"] + " " + txt).strip()

            else:  # image
                if not cur:
                    continue

                page = ev["page_obj"]
                bbox = (ev["x0"], ev["top"], ev["x1"], ev["bottom"])
                fname = save_image_crop(page, bbox, upload_dir, exam_prefix)

                if cur_opt is not None:
                    # 선택지 이미지
                    if not cur["options"][cur_opt]["image_path"]:
                        cur["options"][cur_opt]["image_path"] = fname
                else:
                    # 문제 이미지
                    if not cur["image_path"]:
                        cur["image_path"] = fname

        if cur:
            questions.append(cur)
    
    # 정답 옵션 정리
    for q in questions:
        q["answer_options"] = [opt["number"] for opt in q["options"] if opt["is_correct"]]
        q["answer_text"] = " | ".join(
            opt["content"] for opt in q["options"] if opt["is_correct"] and opt["content"]
        )
        # 빈 옵션 제거
        q["options"] = [opt for opt in q["options"] if opt["content"] or opt["image_path"]]
    
    return questions
