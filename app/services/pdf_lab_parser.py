from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

from app.services.pdf_parser import (
    ANSWER_LABEL_RE,
    EXAMINER_RE,
    INDENT_TOL,
    Q_HEADER,
    WORD_X_TOL,
    clean_text,
    cluster_words_into_rows,
    color_distance,
    detect_answer_color,
    save_image_crop,
)

LAB_OPT_RE = re.compile(r"^([1-9]\d?)([)\.])\s*(.*)$")
LAB_EMBEDDED_OPT_RE = re.compile(
    r"^(?P<prefix>.*)\s+(?P<num>[1-9]\d?)\s*(?P<sep>[)\.])(?P<suffix>\s+.*)?$"
)
OPTION_LABEL_WORD_RE = re.compile(r"^\d+[)\.]$")
SUBITEM_LINE_RE = re.compile(r"^[가-힣A-Za-z][)\.:](?:\s*|$)")
NUMBERED_SUBITEM_LINE_RE = re.compile(r"^\d+[)\.]\s+")
BRACKET_HEADER_RE = re.compile(r"^\[[^\]]+\]$")
MAPPING_PROMPT_LINE_RE = re.compile(r"^(?:[A-Z]|[가-힣])[:\.]\s*")
MAPPING_ANSWER_RE = re.compile(
    r"^(?:[A-Za-z가-힣]\s*\d+(?:\s+\d+)*)(?:\s+[A-Za-z가-힣]\s*\d+(?:\s+\d+)*)+$"
)
INSTRUCTION_TAIL_RE = re.compile(
    r"(?:고르시오|찾아보시오|설명으로|조합으로|무엇인가|들어갈|짝지어진)",
)
QUESTION_PROMPT_HINT_RE = re.compile(
    r"(?:고르시오|찾아보시오|설명으로|무엇인가|다음|select|choose|which of the following|most appropriate|most correct|except)",
    re.IGNORECASE,
)
COMPOUND_SUBQUESTION_RE = re.compile(
    r"(?:\d+[)\.]\s*,?\s*){2,}.*문항에\s*답하시오"
)
COMPOUND_ANSWER_START_RE = re.compile(
    r"(?:정답|판정\s*기준)\s*[:：]",
    re.IGNORECASE,
)
COMPLETE_SENTENCE_END_RE = re.compile(
    r"(?:[.!?]|[가-힣A-Za-z0-9\)\]](?:다|요|함))$"
)
DUPLICATE_RANK_PREFIX_RE = re.compile(r"^(?P<rank>[1-9]\d?)\.\s+(?P<body>.+)$")
PRELABEL_TOP_GAP_TOL = 12.0
PRELABEL_SHORT_REMAINDER_MAX_CHARS = 12
SENTENCE_TAIL_TOKENS = {
    "다",
    "이다",
    "것이다",
    "한다",
    "된다",
    "있다",
    "없다",
}
LEFT_ANCHOR_X_TOL = 4.0
LEFT_ANCHOR_MIN_TOP_GAP = 7.0
PANEL_COORD_TOL = 1.5
PANEL_MIN_WIDTH = 180.0
PANEL_MIN_HEIGHT = 22.0
PANEL_MAX_LIGHT_GRAY = 0.82
BANNER_PANEL_MAX_HEIGHT = 42.0
BANNER_PANEL_MIN_ASPECT_RATIO = 8.0
PANEL_OVERLAP_MIN_RATIO = 0.55
PANEL_OVERLAP_FALLBACK_RATIO = 0.25
PANEL_CENTER_PADDING = 4.0


def _join_row_words_with_gap(words: list[dict[str, Any]], gap_threshold: float = 1.5) -> str:
    if not words:
        return ""
    words = sorted(words, key=lambda item: item["x0"])
    parts = [words[0]["text"]]
    prev_x1 = words[0].get("x1", words[0]["x0"])
    for word in words[1:]:
        x0 = word.get("x0", 0.0)
        if x0 - prev_x1 > gap_threshold:
            parts.append(" ")
        parts.append(word["text"])
        prev_x1 = word.get("x1", x0)
    return "".join(parts)


def _split_row_by_left_anchors(
    words: list[dict[str, Any]],
    anchor_x_tol: float = LEFT_ANCHOR_X_TOL,
    min_anchor_top_gap: float = LEFT_ANCHOR_MIN_TOP_GAP,
) -> list[list[dict[str, Any]]]:
    if len(words) < 4:
        return [words]

    min_x0 = min(word["x0"] for word in words)
    anchors = [
        word
        for word in sorted(words, key=lambda item: (item["top"], item["x0"]))
        if abs(word["x0"] - min_x0) <= anchor_x_tol
    ]
    if len(anchors) < 2:
        return [words]

    anchor_tops: list[float] = []
    for anchor in anchors:
        if not anchor_tops or abs(anchor["top"] - anchor_tops[-1]) > min_anchor_top_gap:
            anchor_tops.append(anchor["top"])
    if len(anchor_tops) < 2:
        return [words]

    groups = [[] for _ in anchor_tops]
    for word in words:
        best_idx = min(
            range(len(anchor_tops)),
            key=lambda idx: (abs(word["top"] - anchor_tops[idx]), idx),
        )
        groups[best_idx].append(word)

    if any(not group for group in groups):
        return [words]
    return [group for group in groups if group]


def _coerce_gray_value(color: Any) -> float | None:
    if isinstance(color, (list, tuple)) and len(color) == 3:
        try:
            values = [float(component) for component in color]
        except (TypeError, ValueError):
            return None
        if max(values) - min(values) > 0.08:
            return None
        return sum(values) / 3.0
    if isinstance(color, (int, float)):
        try:
            return float(color)
        except (TypeError, ValueError):
            return None
    return None


def _is_candidate_panel_border(line: dict[str, Any]) -> bool:
    gray = _coerce_gray_value(line.get("stroking_color"))
    if gray is not None and gray > PANEL_MAX_LIGHT_GRAY:
        return False
    linewidth = float(line.get("linewidth") or 0.0)
    return linewidth >= 0.5


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, top, x1, bottom = bbox
    return max(0.0, x1 - x0) * max(0.0, bottom - top)


def _bbox_intersection_area(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    ix0 = max(left[0], right[0])
    itop = max(left[1], right[1])
    ix1 = min(left[2], right[2])
    ibottom = min(left[3], right[3])
    if ix0 >= ix1 or itop >= ibottom:
        return 0.0
    return (ix1 - ix0) * (ibottom - itop)


def _bbox_contains_point(
    bbox: tuple[float, float, float, float],
    x: float,
    y: float,
    padding: float = PANEL_CENTER_PADDING,
) -> bool:
    return (
        bbox[0] - padding <= x <= bbox[2] + padding
        and bbox[1] - padding <= y <= bbox[3] + padding
    )


def _panel_kind_for_bbox(bbox: tuple[float, float, float, float]) -> str:
    width = max(0.0, bbox[2] - bbox[0])
    height = max(0.0, bbox[3] - bbox[1])
    aspect_ratio = width / height if height > 0 else 0.0
    if height <= BANNER_PANEL_MAX_HEIGHT and aspect_ratio >= BANNER_PANEL_MIN_ASPECT_RATIO:
        return "banner"
    return "panel"


def _normalize_segment(
    line: dict[str, Any],
    *,
    coord_tol: float,
) -> dict[str, float] | None:
    x0 = float(line.get("x0") or 0.0)
    x1 = float(line.get("x1") or 0.0)
    top = float(line.get("top") or 0.0)
    bottom = float(line.get("bottom") or 0.0)

    if abs(top - bottom) <= coord_tol:
        return {
            "orientation": "h",
            "x0": min(x0, x1),
            "x1": max(x0, x1),
            "y": (top + bottom) / 2.0,
        }
    if abs(x0 - x1) <= coord_tol:
        return {
            "orientation": "v",
            "x": (x0 + x1) / 2.0,
            "top": min(top, bottom),
            "bottom": max(top, bottom),
        }
    return None


def _line_covers_horizontal(
    line: dict[str, float],
    *,
    y: float,
    x0: float,
    x1: float,
    coord_tol: float,
) -> bool:
    return (
        line.get("orientation") == "h"
        and abs(float(line["y"]) - y) <= coord_tol
        and float(line["x0"]) <= x0 + coord_tol
        and float(line["x1"]) >= x1 - coord_tol
    )


def _detect_page_panels(
    page: Any,
    *,
    coord_tol: float = PANEL_COORD_TOL,
    min_width: float = PANEL_MIN_WIDTH,
    min_height: float = PANEL_MIN_HEIGHT,
) -> list[dict[str, Any]]:
    raw_lines = list(page.lines or [])
    raw_rects = list(page.rects or [])

    horizontal_lines: list[dict[str, float]] = []
    vertical_lines: list[dict[str, float]] = []
    panels: dict[tuple[float, float, float, float], dict[str, Any]] = {}

    for line in raw_lines:
        if not _is_candidate_panel_border(line):
            continue
        segment = _normalize_segment(line, coord_tol=coord_tol)
        if not segment:
            continue
        if segment["orientation"] == "h" and (segment["x1"] - segment["x0"]) >= min_width:
            horizontal_lines.append(segment)
        elif segment["orientation"] == "v" and (segment["bottom"] - segment["top"]) >= min_height:
            vertical_lines.append(segment)

    def _register_panel(bbox: tuple[float, float, float, float]) -> None:
        if (bbox[2] - bbox[0]) < min_width or (bbox[3] - bbox[1]) < min_height:
            return
        key = tuple(round(value, 2) for value in bbox)
        panels[key] = {
            "bbox": bbox,
            "x0": float(bbox[0]),
            "top": float(bbox[1]),
            "x1": float(bbox[2]),
            "bottom": float(bbox[3]),
            "kind": _panel_kind_for_bbox(bbox),
        }

    for rect in raw_rects:
        if not _is_candidate_panel_border(rect):
            continue
        bbox = (
            float(rect.get("x0") or 0.0),
            float(rect.get("top") or 0.0),
            float(rect.get("x1") or 0.0),
            float(rect.get("bottom") or 0.0),
        )
        _register_panel(bbox)

    for left_index, left in enumerate(vertical_lines):
        for right in vertical_lines[left_index + 1 :]:
            x0 = min(float(left["x"]), float(right["x"]))
            x1 = max(float(left["x"]), float(right["x"]))
            if x1 - x0 < min_width:
                continue

            top = (float(left["top"]) + float(right["top"])) / 2.0
            bottom = (float(left["bottom"]) + float(right["bottom"])) / 2.0
            if (
                abs(float(left["top"]) - float(right["top"])) > coord_tol
                or abs(float(left["bottom"]) - float(right["bottom"])) > coord_tol
                or (bottom - top) < min_height
            ):
                continue

            if not any(
                _line_covers_horizontal(
                    candidate,
                    y=top,
                    x0=x0,
                    x1=x1,
                    coord_tol=coord_tol,
                )
                for candidate in horizontal_lines
            ):
                continue
            if not any(
                _line_covers_horizontal(
                    candidate,
                    y=bottom,
                    x0=x0,
                    x1=x1,
                    coord_tol=coord_tol,
                )
                for candidate in horizontal_lines
            ):
                continue

            _register_panel((x0, top, x1, bottom))

    sorted_panels = sorted(
        panels.values(),
        key=lambda item: (item["top"], item["x0"], item["bottom"], item["x1"]),
    )
    for index, panel in enumerate(sorted_panels, start=1):
        panel["panel_id"] = f"p{int(getattr(page, 'page_number', 0) or 0)}-panel{index}"
    return sorted_panels


def _panel_metadata_for_bbox(
    bbox: tuple[float, float, float, float],
    panels: list[dict[str, Any]],
) -> dict[str, Any]:
    if not panels:
        return {
            "inside_panel": False,
            "panel_id": None,
            "panel_kind": None,
            "panel_bbox": None,
        }

    area = _bbox_area(bbox)
    center_x = (bbox[0] + bbox[2]) / 2.0
    center_y = (bbox[1] + bbox[3]) / 2.0
    best_panel: dict[str, Any] | None = None
    best_score: tuple[float, float, float] = (-1.0, -1.0, float("-inf"))

    for panel in panels:
        panel_bbox = tuple(panel[axis] for axis in ("x0", "top", "x1", "bottom"))
        overlap_area = _bbox_intersection_area(bbox, panel_bbox)
        overlap_ratio = (overlap_area / area) if area > 0 else 0.0
        center_inside = _bbox_contains_point(panel_bbox, center_x, center_y)
        line_within_width = (
            bbox[0] >= panel["x0"] - 8.0 and bbox[2] <= panel["x1"] + 8.0
        )

        if not center_inside and overlap_ratio < PANEL_OVERLAP_MIN_RATIO:
            continue
        if overlap_ratio < PANEL_OVERLAP_FALLBACK_RATIO and not line_within_width:
            continue

        panel_area = _bbox_area(panel_bbox)
        score = (
            1.0 if center_inside else 0.0,
            overlap_ratio,
            -panel_area,
        )
        if score > best_score:
            best_panel = panel
            best_score = score

    if best_panel is None:
        return {
            "inside_panel": False,
            "panel_id": None,
            "panel_kind": None,
            "panel_bbox": None,
        }

    return {
        "inside_panel": True,
        "panel_id": best_panel["panel_id"],
        "panel_kind": best_panel["kind"],
        "panel_bbox": tuple(
            best_panel[axis] for axis in ("x0", "top", "x1", "bottom")
        ),
    }


def _extract_lab_events(
    pdf: pdfplumber.PDF,
    answer_color: tuple[float, float, float] | None,
    y_tol: int = 3,
    min_image_area: int = 2000,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for page_number, page in enumerate(pdf.pages, start=1):
        panels = _detect_page_panels(page)
        words = page.extract_words(
            extra_attrs=["non_stroking_color"],
            x_tolerance=WORD_X_TOL,
            y_tolerance=y_tol,
            keep_blank_chars=True,
        ) or []
        for word in words:
            color = word.get("non_stroking_color")
            if isinstance(color, (list, tuple)) and len(color) == 3:
                word["color"] = tuple(round(float(value), 5) for value in color)
            else:
                word["color"] = None

        rows: list[list[dict[str, Any]]] = []
        for row in cluster_words_into_rows(words, overlap_threshold=0.4):
            rows.extend(_split_row_by_left_anchors(row))
        rows.sort(key=lambda row: min(word["top"] for word in row))

        for row_words in rows:
            row_words = sorted(row_words, key=lambda word: word["x0"])
            text = clean_text(_join_row_words_with_gap(row_words))
            if not text:
                continue

            total_chars = sum(len(clean_text(word["text"])) for word in row_words) or 1
            key_chars = 0
            label_has_key = False

            for index, word in enumerate(row_words):
                color = word.get("color")
                is_key = bool(
                    isinstance(color, tuple)
                    and answer_color
                    and color_distance(color, answer_color) < 0.02
                )
                if is_key:
                    key_chars += len(clean_text(word["text"]))
                if index == 0 and is_key and OPTION_LABEL_WORD_RE.match(clean_text(word["text"])):
                    label_has_key = True

            body_has_key = (key_chars / total_chars) > 0.2
            has_key = body_has_key or label_has_key
            row_bbox = (
                float(min(word["x0"] for word in row_words)),
                float(min(word["top"] for word in row_words)),
                float(max(word["x1"] for word in row_words)),
                float(max(word["bottom"] for word in row_words)),
            )
            panel_meta = _panel_metadata_for_bbox(row_bbox, panels)
            events.append(
                {
                    "type": "text",
                    "page": page_number,
                    "top": row_bbox[1],
                    "x0": row_bbox[0],
                    "x1": row_bbox[2],
                    "bottom": row_bbox[3],
                    "text": text,
                    "has_key": has_key,
                    "body_has_key": body_has_key,
                    "label_has_key": label_has_key,
                    **panel_meta,
                }
            )

        for image in page.images or []:
            width = float(image["x1"] - image["x0"])
            height = float(image["bottom"] - image["top"])
            if width * height < min_image_area:
                continue

            bbox = (
                float(image["x0"]),
                float(image["top"]),
                float(image["x1"]),
                float(image["bottom"]),
            )
            panel_meta = _panel_metadata_for_bbox(bbox, panels)
            events.append(
                {
                    "type": "image",
                    "page": page_number,
                    "top": bbox[1],
                    "x0": bbox[0],
                    "x1": bbox[2],
                    "bottom": bbox[3],
                    "page_obj": page,
                    **panel_meta,
                }
            )

    events.sort(
        key=lambda item: (
            item["page"],
            item["top"],
            item["x0"],
            0 if item["type"] == "text" else 1,
        )
    )
    return events


def _merge_lab_orphan_labels(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text_events = [event for event in events if event["type"] == "text"]
    other_events = [event for event in events if event["type"] != "text"]
    orphan_pattern = re.compile(r"^\s*\d+\s*[)\.]\s*$")

    for event in text_events:
        event["_merged"] = False

    for index, event in enumerate(text_events):
        if event["_merged"]:
            continue
        text = clean_text(str(event.get("text") or ""))
        if not orphan_pattern.match(text):
            continue

        label = clean_text(text)
        candidates: list[tuple[float, int]] = []
        for offset in (-2, -1, 1, 2):
            target_index = index + offset
            if not (0 <= target_index < len(text_events)):
                continue
            target = text_events[target_index]
            if target["_merged"] or target["page"] != event["page"]:
                continue
            target_text = clean_text(str(target.get("text") or ""))
            if not target_text:
                continue
            if not (target["x0"] > event["x0"] + 2.0):
                continue

            score = abs(offset)
            if re.match(r"^[A-Za-z\uAC00-\uD7A3]", target_text):
                score -= 0.2
            if len(target_text) <= 12:
                score += 0.5
            candidates.append((score, target_index))

        if not candidates:
            continue

        candidates.sort(key=lambda item: (item[0], item[1]))
        _, target_index = candidates[0]
        target = text_events[target_index]

        if target_index > 0:
            prev = text_events[target_index - 1]
            if (
                prev["page"] == event["page"]
                and not prev.get("_merged", False)
                and prev["x0"] > event["x0"] + 2.0
            ):
                prev_text = clean_text(str(prev.get("text") or ""))
                target_text = clean_text(str(target.get("text") or ""))
                if prev_text and target_text and len(target_text) <= 12:
                    if re.match(r"^[A-Za-z\uAC00-\uD7A3]", prev_text):
                        target = prev

        event["text"] = f"{label} {target['text']}".strip()
        event["top"] = min(event["top"], target["top"])
        event["bottom"] = max(event["bottom"], target["bottom"])
        event["x0"] = min(event["x0"], target["x0"])
        event["x1"] = max(event["x1"], target["x1"])
        event["body_has_key"] = bool(event.get("body_has_key")) or bool(
            target.get("body_has_key")
        )
        event["label_has_key"] = bool(event.get("label_has_key")) or bool(
            target.get("label_has_key")
        )
        event["has_key"] = bool(event["body_has_key"]) or bool(event["label_has_key"])
        target["_merged"] = True

    final_text_events = []
    for event in text_events:
        if not event["_merged"]:
            event.pop("_merged", None)
            final_text_events.append(event)

    merged = final_text_events + other_events
    merged.sort(
        key=lambda item: (
            item["page"],
            item["top"],
            item["x0"],
            0 if item["type"] == "text" else 1,
        )
    )
    return merged


def _match_option_line(text: str, max_option_number: int) -> tuple[int, str, str] | None:
    match = LAB_OPT_RE.match(text)
    if not match:
        return None

    option_number = int(match.group(1))
    separator = match.group(2)
    remainder = match.group(3)
    if separator == "." and re.match(r"^\d+\.\d", text):
        return None
    if option_number > max_option_number:
        return None

    return option_number, separator, remainder.strip()


def _normalize_embedded_option(
    text: str,
    question: dict[str, Any] | None,
    max_option_number: int,
) -> list[str]:
    if not question:
        return [text]
    if LAB_OPT_RE.match(text.lstrip()):
        return [text]

    match = LAB_EMBEDDED_OPT_RE.match(text)
    if not match:
        return [text]

    prefix = (match.group("prefix") or "").rstrip()
    if not prefix:
        return [text]

    option_number = int(match.group("num"))
    separator = match.group("sep")
    if separator == ".":
        sep_index = match.start("sep")
        if sep_index + 1 < len(text) and text[sep_index + 1].isdigit():
            return [text]
    if option_number > max_option_number:
        return [text]

    if question.get("options_map"):
        expected = max(question["options_map"]) + 1
        if option_number < expected:
            return [text]
    elif option_number != 1:
        return [text]

    if not re.search(r"[A-Za-z\uAC00-\uD7A3]", prefix):
        return [text]

    suffix = (match.group("suffix") or "").strip()
    rebuilt = f"{option_number}) {prefix}".strip()
    if suffix:
        return [rebuilt, suffix]
    return [rebuilt]


def _new_option(number: int) -> dict[str, Any]:
    return {
        "number": int(number),
        "content": "",
        "image_path": None,
        "is_correct": False,
        "chunks": [],
        "label_has_key": False,
    }


def _strip_duplicate_rank_prefix(text: str) -> tuple[str, bool]:
    normalized = clean_text(text)
    if not normalized:
        return "", False
    match = DUPLICATE_RANK_PREFIX_RE.match(normalized)
    if not match:
        return normalized, False
    return clean_text(match.group("body") or ""), True


def _merge_prelabel_option_continuations(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    text_events = [event for event in events if event["type"] == "text"]
    other_events = [event for event in events if event["type"] != "text"]
    if len(text_events) < 2:
        return events

    for event in text_events:
        event["_merged_into_next"] = False

    for index in range(len(text_events) - 1):
        current = text_events[index]
        following = text_events[index + 1]
        if current.get("_merged_into_next"):
            continue
        if current["page"] != following["page"]:
            continue
        if following["top"] - current["top"] > PRELABEL_TOP_GAP_TOL:
            continue

        option_match = _match_option_line(
            clean_text(str(following.get("text") or "")),
            99,
        )
        if not option_match:
            continue

        if current["x0"] <= following["x0"] + (INDENT_TOL / 2):
            continue

        current_text = clean_text(str(current.get("text") or ""))
        if not current_text:
            continue

        current_body, stripped_rank_prefix = _strip_duplicate_rank_prefix(current_text)
        if not current_body:
            continue

        previous_is_option = False
        if index > 0:
            previous = text_events[index - 1]
            if previous["page"] == current["page"] and _match_option_line(
                clean_text(str(previous.get("text") or "")),
                99,
            ):
                previous_is_option = True

        option_number, separator, option_remainder = option_match
        short_remainder = len(option_remainder) <= PRELABEL_SHORT_REMAINDER_MAX_CHARS
        if not stripped_rank_prefix and not previous_is_option:
            continue
        if not stripped_rank_prefix and not short_remainder:
            continue

        merged_remainder = _join_text_parts([current_body, option_remainder])
        following["text"] = f"{option_number}{separator} {merged_remainder}".strip()
        following["top"] = min(current["top"], following["top"])
        following["bottom"] = max(
            float(current.get("bottom") or current["top"]),
            float(following.get("bottom") or following["top"]),
        )
        following["x0"] = float(following["x0"])
        following["x1"] = max(
            float(current.get("x1") or current["x0"]),
            float(following.get("x1") or following["x0"]),
        )
        following["body_has_key"] = bool(current.get("body_has_key")) or bool(
            following.get("body_has_key")
        )
        following["label_has_key"] = bool(following.get("label_has_key"))
        following["has_key"] = (
            bool(following["label_has_key"])
            or bool(following["body_has_key"])
            or bool(current.get("has_key"))
            or bool(following.get("has_key"))
        )
        current["_merged_into_next"] = True

    final_text_events = []
    for event in text_events:
        if not event.get("_merged_into_next"):
            event.pop("_merged_into_next", None)
            final_text_events.append(event)

    merged = final_text_events + other_events
    merged.sort(
        key=lambda item: (
            item["page"],
            item["top"],
            item["x0"],
            0 if item["type"] == "text" else 1,
        )
    )
    return merged


def _get_option(question: dict[str, Any], number: int) -> dict[str, Any]:
    options_map = question.setdefault("options_map", {})
    option = options_map.get(number)
    if option is None:
        option = _new_option(number)
        options_map[number] = option
    return option


def _question_text_block_type(
    *,
    inside_panel: bool = False,
    panel_kind: str | None = None,
) -> str:
    if inside_panel and panel_kind == "banner":
        return "banner_text"
    if inside_panel:
        return "panel_text"
    return "stem_text"


def _question_image_block_type(
    *,
    inside_panel: bool = False,
) -> str:
    if inside_panel:
        return "panel_image"
    return "stem_image"


def _append_question_line(
    question: dict[str, Any],
    text: str,
    *,
    inside_panel: bool = False,
    panel_id: str | None = None,
    panel_kind: str | None = None,
) -> None:
    normalized = clean_text(text)
    if normalized:
        normalized = re.sub(r"^([가-힣A-Za-z][)\.:])(?=\S)", r"\1 ", normalized)
        question.setdefault("content_lines", []).append(normalized)
        block_type = _question_text_block_type(
            inside_panel=inside_panel,
            panel_kind=panel_kind,
        )
        question.setdefault("content_line_meta", []).append(
            {
                "type": block_type,
                "panel_id": panel_id,
            }
        )
        question.setdefault("content_items", []).append(
            {
                "kind": "text",
                "type": block_type,
                "panel_id": panel_id,
                "text": normalized,
            }
        )


def _append_question_image(
    question: dict[str, Any],
    image_path: str,
    *,
    inside_panel: bool = False,
    panel_id: str | None = None,
) -> None:
    if not image_path:
        return
    question.setdefault("content_items", []).append(
        {
            "kind": "image",
            "type": _question_image_block_type(inside_panel=inside_panel),
            "panel_id": panel_id,
            "image_path": image_path,
        }
    )


def _pop_last_question_line(question: dict[str, Any]) -> str | None:
    lines = question.get("content_lines") or []
    if not lines:
        return None

    line = lines.pop()
    meta = question.get("content_line_meta") or []
    if meta:
        meta.pop()

    items = question.get("content_items") or []
    for index in range(len(items) - 1, -1, -1):
        if items[index].get("kind") == "text":
            items.pop(index)
            break
    return clean_text(str(line)) or None


def _append_answer_line(question: dict[str, Any], text: str) -> None:
    normalized = clean_text(text)
    if normalized:
        question.setdefault("answer_lines", []).append(normalized)


def _append_option_chunk(
    option: dict[str, Any],
    text: str,
    *,
    has_key: bool,
    x0: float,
    from_label: bool = False,
) -> None:
    normalized = clean_text(text)
    if not normalized:
        return
    option.setdefault("chunks", []).append(
        {
            "text": normalized,
            "has_key": bool(has_key),
            "x0": float(x0),
            "from_label": bool(from_label),
        }
    )


def _prepend_option_chunk(option: dict[str, Any], chunk: dict[str, Any]) -> None:
    normalized = clean_text(str(chunk.get("text") or ""))
    if not normalized:
        return
    option.setdefault("chunks", []).insert(
        0,
        {
            "text": normalized,
            "has_key": bool(chunk.get("has_key")),
            "x0": float(chunk.get("x0") or 0.0),
            "from_label": bool(chunk.get("from_label")),
        },
    )


def _join_text_parts(parts: list[str]) -> str:
    merged = ""
    for part in parts:
        normalized = clean_text(part)
        if not normalized:
            continue
        if not merged:
            merged = normalized
            continue
        if re.match(r"^[)\],.;:!?]", normalized):
            merged += normalized
            continue
        if re.fullmatch(r"[가-힣]{1,2}", normalized):
            merged += normalized
            continue
        if merged[-1] in "([/-":
            merged += normalized
            continue
        merged += f" {normalized}"
    return clean_text(merged)


def _content_entries(question: dict[str, Any]) -> list[dict[str, Any]]:
    items = list(question.get("content_items") or [])
    if items:
        return items

    lines = [clean_text(str(line)) for line in question.get("content_lines") or []]
    lines = [line for line in lines if line]
    metas = list(question.get("content_line_meta") or [])
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        meta = metas[index] if index < len(metas) else {}
        entries.append(
            {
                "kind": "text",
                "type": meta.get("type") or "stem_text",
                "panel_id": meta.get("panel_id"),
                "text": line,
            }
        )
    return entries


def _render_text_lines(
    lines: list[str],
    *,
    preserve_alpha_subitems: bool,
    preserve_numbered_subitems: bool,
) -> str:
    normalized_lines = [clean_text(line) for line in lines]
    normalized_lines = [line for line in normalized_lines if line]
    if not normalized_lines:
        return ""

    parts: list[str] = []
    for line in normalized_lines:
        if not parts:
            parts.append(line)
            continue
        if preserve_alpha_subitems and SUBITEM_LINE_RE.match(line):
            parts.append("\n" + line)
        elif preserve_numbered_subitems and NUMBERED_SUBITEM_LINE_RE.match(line):
            parts.append("\n" + line)
        elif BRACKET_HEADER_RE.match(line):
            parts.append("\n" + line)
        else:
            parts.append(" " + line)
    return "".join(parts).strip()


def _build_content_blocks(question: dict[str, Any]) -> list[dict[str, Any]]:
    entries = _content_entries(question)
    if not entries:
        return []

    blocks: list[dict[str, Any]] = []
    current_text_block: dict[str, Any] | None = None

    for entry in entries:
        if entry.get("kind") == "text":
            block_type = str(entry.get("type") or "stem_text")
            panel_id = entry.get("panel_id")
            text = clean_text(str(entry.get("text") or ""))
            if not text:
                continue
            if (
                current_text_block is not None
                and current_text_block.get("type") == block_type
                and (
                    current_text_block.get("panel_id") == panel_id
                    or block_type == "panel_text"
                )
            ):
                current_text_block.setdefault("lines", []).append(text)
                continue

            current_text_block = {
                "type": block_type,
                "panel_id": panel_id,
                "lines": [text],
            }
            blocks.append(current_text_block)
            continue

        current_text_block = None
        image_path = str(entry.get("image_path") or "").strip()
        if not image_path:
            continue
        blocks.append(
            {
                "type": str(entry.get("type") or "stem_image"),
                "panel_id": entry.get("panel_id"),
                "image_path": image_path,
            }
        )

    text_lines = [
        clean_text(str(line))
        for line in question.get("content_lines") or []
        if clean_text(str(line))
    ]
    preserve_alpha_subitems = sum(
        1 for line in text_lines if SUBITEM_LINE_RE.match(line)
    ) >= 2
    preserve_numbered_subitems = bool(question.get("compound_mode")) or (
        sum(1 for line in text_lines if NUMBERED_SUBITEM_LINE_RE.match(line)) >= 2
    )

    for block in blocks:
        if block.get("type") in {"stem_text", "panel_text", "banner_text"}:
            block["content"] = _render_text_lines(
                list(block.get("lines") or []),
                preserve_alpha_subitems=preserve_alpha_subitems,
                preserve_numbered_subitems=preserve_numbered_subitems,
            )
    return blocks


def _rebuild_option(option: dict[str, Any]) -> None:
    chunks = option.get("chunks") or []
    option["content"] = _join_text_parts(
        [str(chunk.get("text") or "") for chunk in chunks]
    )
    option["is_correct"] = bool(option.get("label_has_key")) or any(
        bool(chunk.get("has_key")) for chunk in chunks
    )


def _is_compound_subquestion_stem(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    if COMPOUND_SUBQUESTION_RE.search(normalized):
        return True
    if "문항에" not in normalized or "답하시오" not in normalized:
        return False
    return len(re.findall(r"\d+[)\.]", normalized)) >= 2


def _count_numbered_subitems(question: dict[str, Any]) -> int:
    return sum(
        1
        for line in question.get("content_lines") or []
        if NUMBERED_SUBITEM_LINE_RE.match(clean_text(str(line)))
    )


def _looks_like_mapping_answer(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    compact = re.sub(r"[,:;/]", " ", normalized)
    compact = re.sub(r"\s+", " ", compact).strip()
    return bool(MAPPING_ANSWER_RE.fullmatch(compact))


def _is_compound_answer_start(
    question: dict[str, Any],
    text: str,
    *,
    has_key: bool,
) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    if COMPOUND_ANSWER_START_RE.search(normalized):
        return True
    if _looks_like_mapping_answer(normalized):
        return True
    if not has_key:
        return False
    if NUMBERED_SUBITEM_LINE_RE.match(normalized):
        return False
    if SUBITEM_LINE_RE.match(normalized):
        return False
    return _count_numbered_subitems(question) >= 2


def _build_question_content(question: dict[str, Any]) -> str:
    blocks = _build_content_blocks(question)
    text_blocks = [
        block for block in blocks if block.get("type") in {"stem_text", "panel_text", "banner_text"}
    ]
    if not text_blocks:
        return ""
    rendered_blocks = []
    for block in text_blocks:
        rendered = str(block.get("content") or "").strip()
        if rendered:
            rendered_blocks.append(rendered)
    return "\n\n".join(rendered_blocks).strip()


def _looks_complete_statement(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    return bool(COMPLETE_SENTENCE_END_RE.search(normalized))


def _split_trailing_continuation_chunks(
    option: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chunks = list(option.get("chunks") or [])
    split_at = len(chunks)
    while split_at > 0 and not bool(chunks[split_at - 1].get("from_label")):
        split_at -= 1
    return chunks[:split_at], chunks[split_at:]


def _repair_incomplete_trailing_chunks(question: dict[str, Any]) -> bool:
    options_map = question.get("options_map") or {}
    ordered = sorted(options_map)
    changed = False

    for index in range(1, len(ordered)):
        prev_option = options_map[ordered[index - 1]]
        curr_option = options_map[ordered[index]]

        prefix_chunks, trailing_chunks = _split_trailing_continuation_chunks(prev_option)
        curr_chunks = list(curr_option.get("chunks") or [])
        if not prefix_chunks or not trailing_chunks or not curr_chunks:
            continue

        last_trailing_text = clean_text(str(trailing_chunks[-1].get("text") or ""))
        if not last_trailing_text or _looks_complete_statement(last_trailing_text):
            continue

        best_split: int | None = None
        for split_index in range(len(trailing_chunks)):
            left_chunks = prefix_chunks + trailing_chunks[:split_index]
            right_chunks = trailing_chunks[split_index:] + curr_chunks
            left_text = _join_text_parts(
                [str(chunk.get("text") or "") for chunk in left_chunks]
            )
            right_text = _join_text_parts(
                [str(chunk.get("text") or "") for chunk in right_chunks]
            )
            if not left_text or not right_text:
                continue
            if not _looks_complete_statement(left_text):
                continue
            if not _looks_complete_statement(right_text):
                continue
            best_split = split_index
            break

        if best_split is None:
            continue

        prev_option["chunks"] = prefix_chunks + trailing_chunks[:best_split]
        curr_option["chunks"] = trailing_chunks[best_split:] + curr_chunks
        _rebuild_option(prev_option)
        _rebuild_option(curr_option)
        changed = True

    return changed


def _repair_sentence_tail_splits(question: dict[str, Any]) -> None:
    options_map = question.get("options_map") or {}
    ordered = sorted(options_map)
    for index in range(1, len(ordered)):
        prev_option = options_map[ordered[index - 1]]
        curr_option = options_map[ordered[index]]

        prev_chunks = prev_option.get("chunks") or []
        curr_chunks = curr_option.get("chunks") or []
        if not prev_chunks or not curr_chunks:
            continue

        first_text = clean_text(str(curr_chunks[0].get("text") or ""))
        prev_text = _join_text_parts(
            [str(chunk.get("text") or "") for chunk in prev_chunks]
        )
        if not first_text or not prev_text:
            continue
        if first_text not in SENTENCE_TAIL_TOKENS:
            continue
        if prev_text.endswith((".", "?", "!", "다.", "요.")):
            continue

        prev_chunks.append(curr_chunks.pop(0))
        _rebuild_option(prev_option)
        _rebuild_option(curr_option)

        if curr_option.get("content") or curr_option.get("image_path"):
            continue
        if index + 1 >= len(ordered):
            continue

        for shift_index in range(index, len(ordered) - 1):
            dst_option = options_map[ordered[shift_index]]
            src_option = options_map[ordered[shift_index + 1]]
            dst_option["chunks"] = [dict(chunk) for chunk in src_option.get("chunks") or []]
            dst_option["image_path"] = src_option.get("image_path")
            dst_option["label_has_key"] = bool(src_option.get("label_has_key"))
            _rebuild_option(dst_option)

        last_option = options_map[ordered[-1]]
        last_option["chunks"] = []
        last_option["image_path"] = None
        last_option["label_has_key"] = False
        _rebuild_option(last_option)


def _looks_like_continuation_start(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    stripped = normalized.lstrip("([\'\"“”")
    if not stripped:
        return False
    if stripped[0] in ",;:-/)":
        return True
    first_token = re.split(r"\s+", stripped, maxsplit=1)[0]
    return bool(first_token and first_token[0].islower())


def _looks_like_sentence_start(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    stripped = normalized.lstrip("([\'\"“”")
    if not stripped:
        return False
    first = stripped[0]
    if first.isdigit() or first.isupper():
        return True
    if "가" <= first <= "힣":
        return True
    return first in {"[", "(", "<"}


def _looks_like_question_prompt(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    if _looks_like_instruction_tail(normalized):
        return True
    if normalized.endswith(("?", "？", ":")):
        return True
    return bool(QUESTION_PROMPT_HINT_RE.search(normalized))


def _repair_leading_stem_continuations(question: dict[str, Any]) -> bool:
    options_map = question.get("options_map") or {}
    content_lines = question.get("content_lines") or []
    if not options_map or len(content_lines) < 2:
        return False

    structured_subitems = sum(
        1 for line in content_lines if SUBITEM_LINE_RE.match(clean_text(str(line)))
    )
    if structured_subitems >= 2:
        return False

    first_option = options_map[sorted(options_map)[0]]
    first_chunks = first_option.get("chunks") or []
    if not first_chunks:
        return False

    first_text = clean_text(str(first_chunks[0].get("text") or ""))
    if not _looks_like_continuation_start(first_text):
        return False
    if len(first_text) < 16 and len(first_text.split()) < 4:
        return False

    changed = False
    while len(question.get("content_lines") or []) >= 2 and (first_option.get("chunks") or []):
        first_text = clean_text(str((first_option.get("chunks") or [])[0].get("text") or ""))
        if not _looks_like_continuation_start(first_text):
            break

        moved_text = clean_text(str(question["content_lines"][-1]))
        previous_line = clean_text(str(question["content_lines"][-2]))
        if not moved_text:
            _pop_last_question_line(question)
            continue
        if not _looks_like_sentence_start(moved_text):
            break
        if not _looks_like_question_prompt(previous_line):
            break
        if SUBITEM_LINE_RE.match(moved_text) or NUMBERED_SUBITEM_LINE_RE.match(moved_text):
            break
        if re.search(r"_{2,}", moved_text) or moved_text.endswith(("?", "？", ".", ":")):
            break
        if _looks_like_instruction_tail(moved_text):
            break

        _prepend_option_chunk(
            first_option,
            {
                "text": _pop_last_question_line(question),
                "has_key": False,
                "x0": float(question.get("option_x0") or question.get("question_x0") or 0.0),
                "from_label": False,
            },
        )
        _rebuild_option(first_option)
        changed = True

    return changed


def _repair_orphan_answer_prefixes(question: dict[str, Any]) -> bool:
    options_map = question.get("options_map") or {}
    answer_lines = [clean_text(str(line)) for line in question.get("answer_lines") or []]
    answer_lines = [line for line in answer_lines if line]
    if not options_map or not answer_lines or question.get("compound_mode"):
        return False

    first_option = options_map[sorted(options_map)[0]]
    first_chunks = first_option.get("chunks") or []
    if not first_chunks:
        return False

    first_text = clean_text(str(first_chunks[0].get("text") or ""))
    if not (_looks_like_continuation_start(first_text) or not question.get("content_lines")):
        return False
    if any(not _looks_like_sentence_start(line) or len(line) < 20 for line in answer_lines):
        return False

    for line in reversed(answer_lines):
        _prepend_option_chunk(
            first_option,
            {
                "text": line,
                "has_key": True,
                "x0": float(question.get("option_x0") or question.get("question_x0") or 0.0),
                "from_label": False,
            },
        )
    question["answer_lines"] = []
    _rebuild_option(first_option)
    return True


def _repair_continuation_led_options(question: dict[str, Any]) -> bool:
    options_map = question.get("options_map") or {}
    ordered = sorted(options_map)
    if not ordered:
        return False

    changed = _repair_orphan_answer_prefixes(question)
    changed = _repair_leading_stem_continuations(question) or changed

    for index in range(1, len(ordered)):
        prev_option = options_map[ordered[index - 1]]
        curr_option = options_map[ordered[index]]

        while curr_option.get("chunks"):
            first_text = clean_text(str(curr_option["chunks"][0].get("text") or ""))
            if not _looks_like_continuation_start(first_text):
                break

            prefix_chunks, trailing_chunks = _split_trailing_continuation_chunks(prev_option)
            if not prefix_chunks or not trailing_chunks:
                break

            best_split: int | None = None
            for split_index in range(len(trailing_chunks) - 1, -1, -1):
                moved_chunks = trailing_chunks[split_index:]
                candidate_text = clean_text(str(moved_chunks[0].get("text") or ""))
                candidate_x0 = float(moved_chunks[0].get("x0") or 0.0)
                current_x0 = float((curr_option.get("chunks") or [])[0].get("x0") or 0.0)
                if not _looks_like_sentence_start(candidate_text):
                    continue
                if _looks_like_continuation_start(candidate_text):
                    continue
                if candidate_x0 <= current_x0 + (INDENT_TOL / 2):
                    continue
                best_split = split_index
                break

            if best_split is None:
                break

            moved_chunks = trailing_chunks[best_split:]
            prev_option["chunks"] = prefix_chunks + trailing_chunks[:best_split]
            curr_option["chunks"] = [dict(chunk) for chunk in moved_chunks] + list(
                curr_option.get("chunks") or []
            )
            _rebuild_option(prev_option)
            _rebuild_option(curr_option)
            changed = True

    return changed


def _repair_mapping_choice_bank(question: dict[str, Any]) -> bool:
    if question.get("compound_mode"):
        return False

    options_map = question.get("options_map") or {}
    if len(options_map) < 2:
        return False

    content_lines = [
        clean_text(str(line))
        for line in question.get("content_lines") or []
        if clean_text(str(line))
    ]
    has_choice_bank = any("보기" in line for line in content_lines)
    mapping_prompt_count = sum(
        1 for line in content_lines if MAPPING_PROMPT_LINE_RE.match(line)
    )

    last_option = options_map[max(options_map)]
    chunks = list(last_option.get("chunks") or [])
    if not chunks:
        return False

    split_index: int | None = None
    for index, chunk in enumerate(chunks[1:], start=1):
        chunk_text = clean_text(str(chunk.get("text") or ""))
        if MAPPING_PROMPT_LINE_RE.match(chunk_text) or _looks_like_mapping_answer(chunk_text):
            split_index = index
            break

    if split_index is None:
        last_text = clean_text(str(chunks[-1].get("text") or ""))
        if (
            mapping_prompt_count >= 2
            and bool(chunks[-1].get("has_key"))
            and _looks_like_mapping_answer(last_text)
        ):
            split_index = len(chunks) - 1
        else:
            return False

    moved_chunks = chunks[split_index:]
    moved_prompt_count = sum(
        1
        for chunk in moved_chunks
        if MAPPING_PROMPT_LINE_RE.match(clean_text(str(chunk.get("text") or "")))
    )
    moved_answer_count = sum(
        1
        for chunk in moved_chunks
        if bool(chunk.get("has_key"))
        and _looks_like_mapping_answer(clean_text(str(chunk.get("text") or "")))
    )
    if not has_choice_bank and (mapping_prompt_count + moved_prompt_count) < 2:
        return False
    if moved_answer_count == 0:
        return False

    last_option["chunks"] = chunks[:split_index]
    _rebuild_option(last_option)

    _promote_existing_options_to_compound_content(question)
    question["compound_mode"] = True
    question["compound_answer_mode"] = True

    for chunk in moved_chunks:
        chunk_text = clean_text(str(chunk.get("text") or ""))
        if not chunk_text:
            continue
        if bool(chunk.get("has_key")) and _looks_like_mapping_answer(chunk_text):
            _append_answer_line(question, chunk_text)
        elif MAPPING_PROMPT_LINE_RE.match(chunk_text):
            _append_question_line(question, chunk_text)
        elif bool(chunk.get("has_key")) and moved_answer_count:
            _append_answer_line(question, chunk_text)
        else:
            _append_question_line(question, chunk_text)

    return True


def _looks_like_instruction_tail(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    if len(normalized) > 64:
        return False
    return bool(INSTRUCTION_TAIL_RE.search(normalized))


def _repair_sparse_image_options(question: dict[str, Any], max_option_number: int) -> None:
    options_map = question.get("options_map") or {}
    image_events = sorted(
        question.get("image_events") or [],
        key=lambda item: (item.get("page", 0), item.get("top", 0.0)),
    )
    if len(image_events) < 2 or not options_map:
        return
    if question.get("image_path"):
        return

    ordered = sorted(options_map)
    expected_count = len(image_events)
    if expected_count > max_option_number:
        return
    if ordered[0] != 1:
        return
    if ordered[-1] > expected_count:
        return

    textful = []
    for number in ordered:
        option = options_map[number]
        _rebuild_option(option)
        text = clean_text(option.get("content") or "")
        if text:
            textful.append((number, text))

    if any(
        number != 1 or not _looks_like_instruction_tail(text)
        for number, text in textful
    ):
        return

    for number in range(1, expected_count + 1):
        option = _get_option(question, number)
        option["image_path"] = image_events[number - 1]["image_path"]

    first_option = options_map.get(1)
    if first_option:
        first_text = clean_text(first_option.get("content") or "")
        if first_text and _looks_like_instruction_tail(first_text):
            _append_question_line(question, first_text)
            first_option["chunks"] = []
            first_option["content"] = ""
            _rebuild_option(first_option)


def _promote_existing_options_to_compound_content(question: dict[str, Any]) -> None:
    options_map = question.get("options_map") or {}
    if not options_map:
        return

    for number in sorted(options_map):
        option = options_map[number]
        _rebuild_option(option)
        text = clean_text(option.get("content") or "")
        label_line = f"{number}) {text}".strip() if text else f"{number})"
        _append_question_line(question, label_line)
        if option.get("image_path"):
            _append_question_image(question, option["image_path"])
            if not question.get("image_path"):
                question["image_path"] = option["image_path"]

    question["options_map"] = {}
    question["option_x0"] = None


def _maybe_enable_compound_mode(question: dict[str, Any], text: str) -> bool:
    if question.get("compound_mode"):
        return True

    candidate_lines = [
        clean_text(str(line))
        for line in question.get("content_lines") or []
        if clean_text(str(line))
    ]

    options_map = question.get("options_map") or {}
    for number in sorted(options_map):
        option = options_map[number]
        _rebuild_option(option)
        option_text = clean_text(option.get("content") or "")
        candidate_lines.append(
            f"{number}) {option_text}".strip() if option_text else f"{number})"
        )

    normalized_text = clean_text(text)
    if normalized_text:
        candidate_lines.append(normalized_text)

    if not _is_compound_subquestion_stem(" ".join(candidate_lines)):
        return False

    _promote_existing_options_to_compound_content(question)
    question["compound_mode"] = True
    question["compound_answer_mode"] = False
    return True


def _finalize_question(question: dict[str, Any], max_option_number: int) -> dict[str, Any]:
    _repair_continuation_led_options(question)
    for _ in range(max(1, len(question.get("options_map") or {}))):
        if not _repair_incomplete_trailing_chunks(question):
            break
    _repair_continuation_led_options(question)
    _repair_sentence_tail_splits(question)
    _repair_sparse_image_options(question, max_option_number)
    _repair_mapping_choice_bank(question)

    for option in (question.get("options_map") or {}).values():
        _rebuild_option(option)

    question["content_blocks"] = _build_content_blocks(question)
    question["content"] = _build_question_content(question)

    options = [
        question["options_map"][number]
        for number in sorted(question.get("options_map") or {})
    ]
    question["options"] = [
        {
            "number": option["number"],
            "content": option.get("content", ""),
            "image_path": option.get("image_path"),
            "is_correct": bool(option.get("is_correct")),
        }
        for option in options
        if option.get("content") or option.get("image_path")
    ]
    question["answer_options"] = [
        option["number"] for option in question["options"] if option.get("is_correct")
    ]

    if question["options"]:
        question["answer_text"] = " | ".join(
            option.get("content", "")
            for option in question["options"]
            if option.get("is_correct") and option.get("content")
        )
    else:
        question["answer_text"] = " ".join(question.get("answer_lines") or []).strip()

    return {
        "question_number": int(question["question_number"]),
        "content": question.get("content", ""),
        "content_blocks": question.get("content_blocks") or [],
        "image_path": question.get("image_path"),
        "examiner": question.get("examiner"),
        "options": question["options"],
        "answer_options": question["answer_options"],
        "answer_text": question.get("answer_text", ""),
    }


def parse_pdf_to_lab_questions(
    pdf_path: str | Path,
    upload_dir: Path,
    exam_prefix: str,
    max_option_number: int = 20,
) -> list[dict[str, Any]]:
    pdf_path = Path(pdf_path)
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    questions: list[dict[str, Any]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        answer_color = detect_answer_color(pdf)
        events = _merge_prelabel_option_continuations(
            _merge_lab_orphan_labels(_extract_lab_events(pdf, answer_color))
        )

        current: dict[str, Any] | None = None
        current_option_number: int | None = None
        pending_examiner: str | None = None

        for event in events:
            if event["type"] == "text":
                normalized_lines = _normalize_embedded_option(
                    event["text"],
                    current,
                    max_option_number,
                )
                for text in normalized_lines:
                    examiner_match = EXAMINER_RE.match(text)
                    if examiner_match:
                        examiner_name = (examiner_match.group(1) or "").strip()
                        pending_examiner = examiner_name or None
                        continue

                    question_match = Q_HEADER.match(text)
                    if question_match:
                        if current:
                            option_match = _match_option_line(text, max_option_number)
                            if option_match and not current.get("compound_mode"):
                                option_number, _, option_text = option_match
                                question_x0 = current.get("question_x0")
                                option_x0 = current.get("option_x0")
                                indented = (
                                    question_x0 is not None
                                    and event["x0"] > question_x0 + INDENT_TOL
                                )
                                aligned_to_option = (
                                    option_x0 is not None
                                    and abs(event["x0"] - option_x0) <= INDENT_TOL
                                )
                                if indented or (
                                    option_x0 is not None
                                    and question_x0 is not None
                                    and (option_x0 - question_x0) > INDENT_TOL
                                    and aligned_to_option
                                ):
                                    option = _get_option(current, option_number)
                                    if current.get("option_x0") is None:
                                        current["option_x0"] = event["x0"]
                                    current_option_number = option_number
                                    option["label_has_key"] = (
                                        bool(option.get("label_has_key"))
                                        or bool(event.get("label_has_key"))
                                        or bool(event["has_key"])
                                    )
                                    option_text, _ = _strip_duplicate_rank_prefix(
                                        option_text
                                    )
                                    if option_text:
                                        _append_option_chunk(
                                            option,
                                            option_text,
                                            has_key=bool(
                                                event.get("body_has_key", event["has_key"])
                                            ),
                                            x0=event["x0"],
                                            from_label=True,
                                        )
                                    continue
                        if current:
                            questions.append(
                                _finalize_question(current, max_option_number)
                            )
                        initial_text = (question_match.group(2) or "").strip()
                        current = {
                            "question_number": int(question_match.group(1)),
                            "content_lines": [],
                            "content_line_meta": [],
                            "content_items": [],
                            "image_path": None,
                            "examiner": pending_examiner,
                            "options_map": {},
                            "answer_lines": [],
                            "question_x0": event["x0"],
                            "option_x0": None,
                            "image_events": [],
                            "compound_mode": _is_compound_subquestion_stem(initial_text),
                            "compound_answer_mode": False,
                        }
                        if initial_text:
                            _append_question_line(
                                current,
                                initial_text,
                                inside_panel=bool(event.get("inside_panel")),
                                panel_id=event.get("panel_id"),
                                panel_kind=event.get("panel_kind"),
                            )
                        pending_examiner = None
                        current_option_number = None
                        continue

                    if not current:
                        continue

                    if not current.get("compound_mode") and _maybe_enable_compound_mode(
                        current,
                        text,
                    ):
                        current_option_number = None

                    if current.get("compound_mode"):
                        if current.get("compound_answer_mode"):
                            _append_answer_line(current, text)
                        elif _is_compound_answer_start(
                            current,
                            text,
                            has_key=bool(event["has_key"]),
                        ):
                            current["compound_answer_mode"] = True
                            _append_answer_line(current, text)
                        else:
                            _append_question_line(
                                current,
                                text,
                                inside_panel=bool(event.get("inside_panel")),
                                panel_id=event.get("panel_id"),
                                panel_kind=event.get("panel_kind"),
                            )
                        current_option_number = None
                        continue

                    option_match = _match_option_line(text, max_option_number)
                    if option_match:
                        option_number, _, option_text = option_match
                        option = _get_option(current, option_number)
                        if current.get("option_x0") is None:
                            current["option_x0"] = event["x0"]
                        current_option_number = option_number
                        option["label_has_key"] = (
                            bool(option.get("label_has_key"))
                            or bool(event.get("label_has_key"))
                            or bool(event["has_key"])
                        )
                        option_text, _ = _strip_duplicate_rank_prefix(option_text)
                        if option_text:
                            _append_option_chunk(
                                option,
                                option_text,
                                has_key=bool(event.get("body_has_key", event["has_key"])),
                                x0=event["x0"],
                                from_label=True,
                            )
                        continue

                    if current_option_number is None and not current["options_map"]:
                        label_match = ANSWER_LABEL_RE.match(text)
                        if label_match:
                            label_text = label_match.group(1).strip()
                            if label_text:
                                current["answer_lines"].append(label_text)
                            continue
                        if event["has_key"]:
                            current["answer_lines"].append(text)
                            continue

                    if current_option_number is not None:
                        option = _get_option(current, current_option_number)
                        _append_option_chunk(
                            option,
                            text,
                            has_key=bool(event.get("body_has_key", event["has_key"])),
                            x0=event["x0"],
                        )
                    else:
                        _append_question_line(
                            current,
                            text,
                            inside_panel=bool(event.get("inside_panel")),
                            panel_id=event.get("panel_id"),
                            panel_kind=event.get("panel_kind"),
                        )
                continue

            if not current:
                continue

            bbox = (event["x0"], event["top"], event["x1"], event["bottom"])
            try:
                image_name = save_image_crop(
                    event["page_obj"],
                    bbox,
                    upload_dir,
                    exam_prefix,
                )
            except Exception:
                continue
            if not image_name:
                continue

            if current.get("compound_mode"):
                if not current.get("image_path"):
                    current["image_path"] = image_name
                _append_question_image(
                    current,
                    image_name,
                    inside_panel=bool(event.get("inside_panel")),
                    panel_id=event.get("panel_id"),
                )
                continue

            current.setdefault("image_events", []).append(
                {
                    "page": event["page"],
                    "top": event["top"],
                    "image_path": image_name,
                    "option_hint": current_option_number,
                }
            )

            if current_option_number is not None:
                option = _get_option(current, current_option_number)
                if not option.get("image_path"):
                    option["image_path"] = image_name
            else:
                _append_question_image(
                    current,
                    image_name,
                    inside_panel=bool(event.get("inside_panel")),
                    panel_id=event.get("panel_id"),
                )
                if not current.get("image_path"):
                    current["image_path"] = image_name

        if current:
            questions.append(_finalize_question(current, max_option_number))

    return questions


__all__ = ["parse_pdf_to_lab_questions"]
