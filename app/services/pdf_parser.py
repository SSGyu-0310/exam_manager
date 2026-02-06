#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF parser for question extraction.
Uses pdfplumber to detect question blocks, options, and answer hints.
"""

import re
import hashlib
from pathlib import Path
from collections import Counter
from io import BytesIO

import pdfplumber


CID_RE = re.compile(r"\(cid:\d+\)")
Q_HEADER = re.compile(r"^\s*(\d{1,3})\.(?!\d)\s*(.*)$")
OPT_RE = re.compile(r"^([1-9]|1[0-6])([)\.])\s*(.*)$")
EMBEDDED_OPT_RE = re.compile(r"^(?P<prefix>.*)\s+(?P<num>[1-9]|1[0-6])\s*[)\.](?P<suffix>\s+.*)?$")
ANSWER_LABEL_RE = re.compile(r"^(?:\uC815\uB2F5|\uB2F5|answer)\s*[:\uFF1A]\s*(.*)$", re.IGNORECASE)

INDENT_TOL = 6.0
WORD_X_TOL = 0.5

# Post-clean rules to avoid label token splits like "1 )" or "A )"
LABEL_SPACE_FIX_NUM = re.compile(r"(\d)\s+([)\.])")
LABEL_SPACE_FIX_ALPHA = re.compile(r"([A-Za-z])\s+([)\.])")


def clean_text(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = CID_RE.sub(" ", s)
    s = re.sub(r"[\x00-\x1F\x7F]", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = s.strip()
    # Fix accidental splits for labels
    s = LABEL_SPACE_FIX_NUM.sub(r"\1\2", s)
    s = LABEL_SPACE_FIX_ALPHA.sub(r"\1\2", s)
    return s


def detect_answer_color(pdf: pdfplumber.PDF, max_pages=None):
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
        if sum(abs(x) for x in col) < 0.001:
            continue
        if sum(abs(x - 1) for x in col) < 0.001:
            continue
        return col

    return counter.most_common(1)[0][0]


def color_distance(c1, c2) -> float:
    return float(sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5)


def get_vertical_overlap(w1, w2):
    """Calculate vertical overlap ratio between two objects (word vs word/row-proxy)."""
    top1, bottom1 = w1["top"], w1["bottom"]
    top2, bottom2 = w2["top"], w2["bottom"]

    overlap_top = max(top1, top2)
    overlap_bottom = min(bottom1, bottom2)

    if overlap_top >= overlap_bottom:
        return 0.0

    overlap_h = overlap_bottom - overlap_top
    h1 = bottom1 - top1
    h2 = bottom2 - top2

    min_h = min(h1, h2)
    if min_h <= 0:
        return 0.0

    return overlap_h / min_h


def cluster_words_into_rows(words, overlap_threshold=0.4):
    """Cluster words into rows based on vertical overlap (greedy)."""
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: w["top"])
    rows = []
    row_bounds = []

    for word in sorted_words:
        best_idx = None
        best_overlap = -1.0

        for idx in range(len(rows) - 1, -1, -1):
            proxy = row_bounds[idx]
            overlap = get_vertical_overlap(word, proxy)
            if overlap > overlap_threshold and overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx

        if best_idx is not None:
            rows[best_idx].append(word)
            rb = row_bounds[best_idx]
            rb["top"] = min(rb["top"], word["top"])
            rb["bottom"] = max(rb["bottom"], word["bottom"])
        else:
            rows.append([word])
            row_bounds.append({"top": word["top"], "bottom": word["bottom"]})

    return rows


def _join_words_with_gap(ws, gap_threshold=1.5):
    """Join words in x-order; only insert a space when there's a visible gap."""
    if not ws:
        return ""
    ws = sorted(ws, key=lambda w: w["x0"])
    parts = [ws[0]["text"]]
    prev_x1 = ws[0].get("x1", ws[0]["x0"])
    for w in ws[1:]:
        x0 = w.get("x0", 0.0)
        if x0 - prev_x1 > gap_threshold:
            parts.append(" ")
        parts.append(w["text"])
        prev_x1 = w.get("x1", x0)
    return "".join(parts)


def merge_orphan_labels(events):
    """Merge label-only rows (e.g. '2)') with adjacent text rows."""
    text_events = [e for e in events if e["type"] == "text"]
    other_events = [e for e in events if e["type"] != "text"]

    orphan_pattern = re.compile(r"^\s*\d+\s*[)\.]\s*$")

    for ev in text_events:
        ev["_merged"] = False

    for i, ev in enumerate(text_events):
        if ev["_merged"]:
            continue

        text = (ev.get("text") or "").strip()
        if not orphan_pattern.match(text):
            continue

        label = LABEL_SPACE_FIX_NUM.sub(r"\1\2", text)
        label = LABEL_SPACE_FIX_ALPHA.sub(r"\1\2", label)

        candidates = []
        for offset in (-2, -1, 1, 2):
            idx = i + offset
            if not (0 <= idx < len(text_events)):
                continue
            target = text_events[idx]
            if target["_merged"]:
                continue
            if target["page"] != ev["page"]:
                continue

            ttext = (target.get("text") or "").strip()
            if not ttext:
                continue
            if not (target["x0"] > ev["x0"] + 2.0):
                continue

            score = abs(offset)
            if re.match(r"^[A-Za-z\uAC00-\uD7A3]", ttext):
                score -= 0.2
            if len(ttext) <= 12:
                score += 0.5

            candidates.append((score, idx))

        if not candidates:
            continue

        candidates.sort(key=lambda x: (x[0], x[1]))
        _, j = candidates[0]
        target = text_events[j]

        if j > 0:
            prev = text_events[j - 1]
            if (
                prev["page"] == ev["page"]
                and not prev.get("_merged", False)
                and prev["x0"] > ev["x0"] + 2.0
            ):
                prev_text = (prev.get("text") or "").strip()
                tgt_text = (target.get("text") or "").strip()
                if prev_text and tgt_text and len(tgt_text) <= 12:
                    if re.match(r"^[A-Za-z\uAC00-\uD7A3]", prev_text):
                        target = prev

        new_text = f"{label} {target['text']}".strip()
        ev["text"] = new_text
        ev["top"] = min(ev["top"], target["top"])
        ev["bottom"] = max(ev["bottom"], target["bottom"])
        ev["x0"] = min(ev["x0"], target["x0"])
        ev["x1"] = max(ev["x1"], target["x1"])
        ev["has_key"] = ev.get("has_key", False) or target.get("has_key", False)

        target["_merged"] = True

    final_text_events = []
    for ev in text_events:
        if not ev["_merged"]:
            ev.pop("_merged", None)
            final_text_events.append(ev)

    all_events = final_text_events + other_events
    all_events.sort(key=lambda d: (d["page"], d["top"], d["x0"], 0 if d["type"] == "text" else 1))
    return all_events


def extract_events(pdf, answer_color, y_tol=3, min_image_area=2000):
    events = []

    for pno, page in enumerate(pdf.pages, start=1):
        words = page.extract_words(
            extra_attrs=["non_stroking_color"],
            x_tolerance=WORD_X_TOL,
            y_tolerance=y_tol,
            keep_blank_chars=True,
        ) or []
        for w in words:
            col = w.get("non_stroking_color")
            if isinstance(col, (list, tuple)) and len(col) == 3:
                w["color"] = tuple(round(float(x), 5) for x in col)
            else:
                w["color"] = None

        rows = cluster_words_into_rows(words, overlap_threshold=0.4)
        rows.sort(key=lambda r: min(w["top"] for w in r))

        for ws in rows:
            ws = sorted(ws, key=lambda w: w["x0"])
            text = clean_text(_join_words_with_gap(ws))
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
                    "x1": float(max(w["x1"] for w in ws)),
                    "bottom": float(max(w["bottom"] for w in ws)),
                    "text": text,
                    "has_key": has_key,
                }
            )

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


def match_option_line(text, max_option_number):
    m_opt = OPT_RE.match(text)
    if not m_opt:
        return None

    opt_num = int(m_opt.group(1))
    if opt_num > max_option_number:
        return None

    return opt_num, m_opt.group(2), m_opt.group(3).strip()


def normalize_embedded_option(text, cur, max_option_number):
    if not cur:
        return [text]
    if OPT_RE.match(text.lstrip()):
        return [text]

    m = EMBEDDED_OPT_RE.match(text)
    if not m:
        return [text]

    prefix = (m.group("prefix") or "").rstrip()
    if not prefix:
        return [text]

    num = int(m.group("num"))
    if num > max_option_number:
        return [text]

    if cur.get("options_map"):
        expected = max(cur["options_map"]) + 1
        if num < expected:
            return [text]
    else:
        if num != 1:
            return [text]

    if not re.search(r"[A-Za-z\uAC00-\uD7A3]", prefix):
        return [text]

    suffix = (m.group("suffix") or "").strip()
    rebuilt = f"{num}) {prefix}".strip()
    if suffix:
        return [rebuilt, suffix]
    return [rebuilt]


def save_image_crop(page, bbox, upload_dir: Path, exam_prefix: str, resolution=200) -> str:
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


def parse_pdf_to_questions(pdf_path, upload_dir: Path, exam_prefix: str, max_option_number=16):
    pdf_path = Path(pdf_path)
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    questions = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        answer_color = detect_answer_color(pdf)
        events = extract_events(pdf, answer_color)
        events = merge_orphan_labels(events)

        cur = None
        cur_opt = None

        for ev in events:
            if ev["type"] == "text":
                normalized_lines = normalize_embedded_option(ev["text"], cur, max_option_number)
                for txt in normalized_lines:
                    m_q = Q_HEADER.match(txt)
                    if m_q:
                        if cur:
                            opt_match = match_option_line(txt, max_option_number)
                            if opt_match:
                                opt_num, _, opt_text = opt_match
                                qx0 = cur.get("question_x0")
                                ox0 = cur.get("option_x0")
                                indented = qx0 is not None and ev["x0"] > qx0 + INDENT_TOL
                                aligned_to_option = ox0 is not None and abs(ev["x0"] - ox0) <= INDENT_TOL
                                if indented or (
                                    ox0 is not None
                                    and qx0 is not None
                                    and (ox0 - qx0) > INDENT_TOL
                                    and aligned_to_option
                                ):
                                    option = cur["options_map"].setdefault(
                                        opt_num,
                                        {"number": opt_num, "content": "", "image_path": None, "is_correct": False},
                                    )
                                    if cur.get("option_x0") is None:
                                        cur["option_x0"] = ev["x0"]
                                    cur_opt = opt_num
                                    if opt_text:
                                        option["content"] = (option["content"] + " " + opt_text).strip()
                                    option["is_correct"] = option["is_correct"] or ev["has_key"]
                                    continue
                        if cur:
                            questions.append(cur)
                        cur = {
                            "question_number": int(m_q.group(1)),
                            "content": m_q.group(2).strip(),
                            "image_path": None,
                            "options_map": {},
                            "answer_lines": [],
                            "question_x0": ev["x0"],
                            "option_x0": None,
                        }
                        cur_opt = None
                        continue

                    opt_match = match_option_line(txt, max_option_number)
                    if opt_match and cur:
                        opt_num, _, opt_text = opt_match
                        option = cur["options_map"].setdefault(
                            opt_num,
                            {"number": opt_num, "content": "", "image_path": None, "is_correct": False},
                        )
                        if cur.get("option_x0") is None:
                            cur["option_x0"] = ev["x0"]
                        cur_opt = opt_num
                        if opt_text:
                            option["content"] = (option["content"] + " " + opt_text).strip()
                        option["is_correct"] = option["is_correct"] or ev["has_key"]
                        continue

                    if not cur:
                        continue

                    if cur_opt is None and not cur["options_map"]:
                        label_match = ANSWER_LABEL_RE.match(txt)
                        if label_match:
                            label_text = label_match.group(1).strip()
                            if label_text:
                                cur["answer_lines"].append(label_text)
                            continue
                        if ev["has_key"]:
                            cur["answer_lines"].append(txt)
                            continue

                    if cur_opt is not None:
                        option = cur["options_map"].setdefault(
                            cur_opt,
                            {"number": cur_opt, "content": "", "image_path": None, "is_correct": False},
                        )
                        option["content"] = (option["content"] + " " + txt).strip()
                        option["is_correct"] = option["is_correct"] or ev["has_key"]
                    else:
                        cur["content"] = (cur["content"] + " " + txt).strip()
            else:
                if not cur:
                    continue

                page = ev["page_obj"]
                bbox = (ev["x0"], ev["top"], ev["x1"], ev["bottom"])
                fname = save_image_crop(page, bbox, upload_dir, exam_prefix)

                if cur_opt is not None:
                    option = cur["options_map"].setdefault(
                        cur_opt,
                        {"number": cur_opt, "content": "", "image_path": None, "is_correct": False},
                    )
                    if not option["image_path"]:
                        option["image_path"] = fname
                else:
                    if not cur["image_path"]:
                        cur["image_path"] = fname

        if cur:
            questions.append(cur)

    for q in questions:
        options = [q["options_map"][n] for n in sorted(q["options_map"])]
        q["options"] = [opt for opt in options if opt["content"] or opt["image_path"]]
        q["answer_options"] = [opt["number"] for opt in q["options"] if opt["is_correct"]]

        if q["options"]:
            q["answer_text"] = " | ".join(
                opt["content"] for opt in q["options"] if opt["is_correct"] and opt["content"]
            )
        else:
            q["answer_text"] = " ".join(q["answer_lines"]).strip()

        q.pop("options_map", None)
        q.pop("answer_lines", None)
        q.pop("question_x0", None)
        q.pop("option_x0", None)

    return questions
