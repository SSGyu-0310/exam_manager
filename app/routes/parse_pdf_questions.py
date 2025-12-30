#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import hashlib
from pathlib import Path
from collections import Counter
from io import BytesIO

import pdfplumber
import pandas as pd


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
    텍스트 라인에는 has_key(정답색 포함 여부)도 같이 붙임.
    """
    events = []

    for pno, page in enumerate(pdf.pages, start=1):
        # --- text lines ---
        words = page.extract_words(extra_attrs=["non_stroking_color"]) or []
        for w in words:
            col = w.get("non_stroking_color")
            # grayscale(len==1)는 정답색 비교에서 제외
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


def save_image_crop(page, bbox, media_dir: Path, resolution=200) -> str:
    """
    bbox 영역을 PNG로 래스터라이즈한 뒤 sha1 해시로 파일명 생성.
    """
    cropped = page.crop(bbox)
    page_image = cropped.to_image(resolution=resolution)

    buf = BytesIO()
    page_image.original.save(buf, format="PNG")
    data = buf.getvalue()

    h = hashlib.sha1(data).hexdigest()[:16]
    fname = f"{h}.png"
    out_path = media_dir / fname
    if not out_path.exists():
        out_path.write_bytes(data)
    return fname


def parse_events(events, media_dir: Path, media_ref_prefix="media/") -> pd.DataFrame:
    """
    이벤트 스트림을 스캔하며:
      - 문항/선지 텍스트 구성
      - 파란색(정답색) 선지 번호 추출
      - 이미지가 나오면 현재 문맥(선지 우선, 없으면 지문)에 ![]() 형태로 삽입
    """
    questions = []
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
                    "ID": m_q.group(1),
                    "Question": m_q.group(2).strip(),
                    "Options": [""] * 5,
                    "OptKey": [False] * 5,
                }
                cur_opt = None
                continue

            if not cur:
                continue

            m_opt = OPT_RE.match(txt)
            if m_opt:
                idx = int(m_opt.group(1)) - 1
                cur_opt = idx
                cur["Options"][idx] = m_opt.group(2).strip()
                cur["OptKey"][idx] = cur["OptKey"][idx] or ev["has_key"]
                continue

            # 이어지는 줄 처리
            if cur_opt is not None:
                cur["Options"][cur_opt] = (cur["Options"][cur_opt] + " " + txt).strip()
                cur["OptKey"][cur_opt] = cur["OptKey"][cur_opt] or ev["has_key"]
            else:
                cur["Question"] = (cur["Question"] + " " + txt).strip()

        else:  # image
            if not cur:
                continue

            page = ev["page_obj"]
            bbox = (ev["x0"], ev["top"], ev["x1"], ev["bottom"])
            fname = save_image_crop(page, bbox, media_dir)

            tag = f" ![]({media_ref_prefix}{fname})"
            if cur_opt is not None:
                cur["Options"][cur_opt] = (cur["Options"][cur_opt] + tag).strip()
            else:
                cur["Question"] = (cur["Question"] + tag).strip()

    if cur:
        questions.append(cur)

    rows = []
    for q in questions:
        ans_opts = [str(i + 1) for i, b in enumerate(q["OptKey"]) if b]
        ans_text = " | ".join(q["Options"][int(i) - 1] for i in ans_opts if q["Options"][int(i) - 1])

        rows.append(
            {
                "ID": q["ID"],
                "Question": q["Question"],
                "Option 1": q["Options"][0],
                "Option 2": q["Options"][1],
                "Option 3": q["Options"][2],
                "Option 4": q["Options"][3],
                "Option 5": q["Options"][4],
                "AnswerOption": ",".join(ans_opts),
                "AnswerText": ans_text,
            }
        )

    return pd.DataFrame(rows)


def pdf_to_csv(pdf_path: str, output_csv: str | None = None):
    pdf_path = Path(pdf_path)

    if output_csv is None:
        output_csv = str(pdf_path.with_suffix(".csv"))
    else:
        output_csv = str(Path(output_csv))

    out_dir = Path(output_csv).resolve().parent
    media_root = out_dir / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    media_subdir = media_root / pdf_path.stem
    media_subdir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(str(pdf_path)) as pdf:
        answer_color = detect_answer_color(pdf)
        events = extract_events(pdf, answer_color)
        df = parse_events(events, media_subdir, media_ref_prefix="media/")

    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"✅ 변환 완료: {output_csv} ({len(df)}문항)")
    print(f"🖼️ 이미지 폴더: {media_subdir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python pdf_to_csv_with_images.py input.pdf [output.csv]")
        sys.exit(1)

    in_pdf = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) >= 3 else None
    pdf_to_csv(in_pdf, out_csv)
