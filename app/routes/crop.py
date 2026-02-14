# crop_exam_by_graylines_merge_pages_contentaware.py
# pip install pymupdf

import os
import json
import argparse
import re
import fitz  # PyMuPDF

QUESTION_NUM_RE = re.compile(r"^\s*(\d{1,3})\.(?!\d)(?:\s+.*)?$")
WHITESPACE_RE = re.compile(r"\s+")


def is_grayish(col, gray_min=0.70, gray_max=0.95, equal_tol=0.06):
    if not col:
        return False
    r, g, b = col
    if max(abs(r-g), abs(g-b), abs(r-b)) > equal_tol:
        return False
    return (gray_min <= r <= gray_max) and (gray_min <= g <= gray_max) and (gray_min <= b <= gray_max)


def get_horiz_gray_lines(page: fitz.Page,
                         gray_min=0.70, gray_max=0.95,
                         equal_tol=0.06,
                         min_span_ratio=0.60,
                         y_eps=0.6):
    W = page.rect.width
    ys = []

    for d in page.get_drawings():
        col = d.get("color")
        if not is_grayish(col, gray_min, gray_max, equal_tol):
            continue

        for item in d.get("items", []):
            if item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            if abs(p1.y - p2.y) > y_eps:
                continue
            span_ratio = abs(p1.x - p2.x) / W
            if span_ratio < min_span_ratio:
                continue
            ys.append((p1.y + p2.y) / 2)

    ys.sort()
    dedup = []
    for y in ys:
        if not dedup or abs(y - dedup[-1]) > 1.0:
            dedup.append(y)
    return dedup


def count_text_chars_in_rect(page: fitz.Page, rect: fitz.Rect) -> int:
    """Count non-space characters in rect (works well when text layer exists)."""
    txt = page.get_text("text", clip=rect) or ""
    txt = re.sub(r"\s+", "", txt)
    return len(txt)


def has_image_block_in_rect(page: fitz.Page, rect: fitz.Rect) -> bool:
    """Return True when at least one image block exists in the clipped rect."""
    d = page.get_text("dict", clip=rect) or {}
    for block in d.get("blocks", []):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return True
    return False


def find_question_markers(page: fitz.Page, rect: fitz.Rect) -> list[tuple[int, float]]:
    """
    Find question-number line markers inside a segment.
    Returns [(qnum, y0), ...] sorted by y.
    """
    data = page.get_text("dict", clip=rect) or {}
    markers: list[tuple[int, float]] = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans") or []
            if not spans:
                continue
            text = "".join((span.get("text") or "") for span in spans)
            text = WHITESPACE_RE.sub(" ", text).strip()
            if not text:
                continue
            m = QUESTION_NUM_RE.match(text)
            if not m:
                continue
            y0 = min(float(span["bbox"][1]) for span in spans)
            markers.append((int(m.group(1)), y0))

    markers.sort(key=lambda item: item[1])
    dedup: list[tuple[int, float]] = []
    for qnum, y0 in markers:
        if dedup and abs(y0 - dedup[-1][1]) < 1.0:
            continue
        dedup.append((qnum, y0))
    return dedup


def split_segment_by_markers(
    rect: fitz.Rect,
    markers: list[tuple[int, float]],
    start_pad: float = 2.0,
    split_pad: float = 1.0,
    min_height: float = 8.0,
) -> list[tuple[fitz.Rect, int | None]]:
    """
    Split one grayline segment into multiple question segments when
    multiple question-number markers are detected.
    """
    if not markers:
        return [(rect, None)]

    if len(markers) == 1:
        qnum, y0 = markers[0]
        start_y = max(rect.y0, y0 - start_pad)
        return [(fitz.Rect(rect.x0, start_y, rect.x1, rect.y1), qnum)]

    split_points = [rect.y0]
    for _, y0 in markers[1:]:
        split_points.append(max(rect.y0, min(rect.y1, y0 - split_pad)))
    split_points.append(rect.y1)

    result: list[tuple[fitz.Rect, int | None]] = []
    marker_idx = 0
    for i in range(len(split_points) - 1):
        y0 = split_points[i]
        y1 = split_points[i + 1]
        if y1 <= y0 + min_height:
            continue
        qnum = markers[min(marker_idx, len(markers) - 1)][0]
        result.append((fitz.Rect(rect.x0, y0, rect.x1, y1), qnum))
        marker_idx += 1

    return result or [(rect, markers[0][0])]


def is_choices_only_segment(page: fitz.Page, rect: fitz.Rect) -> bool:
    """
    선지만 있는 세그먼트인지 확인.
    문제 번호 없이 1) 2) 3) 등의 선지 패턴으로 시작하는 경우 True 반환.
    지문이 이전 페이지에 있고 선지만 이번 페이지에 있는 경우를 감지.
    """
    txt = page.get_text("text", clip=rect) or ""
    txt = txt.strip()
    if not txt:
        return False
    
    # 문제 번호 패턴: "1." "12." "123." 등 (번호 + 점)
    question_num_pattern = re.compile(r'^\s*\d+\.\s')
    
    # 선지 패턴: "1)" "2)" 또는 "①" "②" 등으로 시작
    choices_pattern = re.compile(r'^\s*([1-5]\)|[①②③④⑤]|[ㄱㄴㄷㄹㅁ])')
    
    # 문제 번호가 있으면 선지만 있는 게 아님
    if question_num_pattern.match(txt):
        return False
    
    # 선지 패턴으로 시작하면 선지만 있는 세그먼트
    if choices_pattern.match(txt):
        return True
    
    return False


def extract_question_number(
    page: fitz.Page,
    rect: fitz.Rect,
    expected_qnum: int | None = None,
) -> int | None:
    """
    세그먼트에서 PDF 원본 문제 번호 추출.
    "1. 다음 중..." 형태에서 1을 추출.
    문제 번호가 없으면 None 반환.
    """
    markers = find_question_markers(page, rect)
    if not markers:
        return None

    nums = [qnum for qnum, _ in markers]
    if expected_qnum is None:
        return nums[0]

    if expected_qnum in nums:
        return expected_qnum

    forward = [n for n in nums if expected_qnum <= n <= expected_qnum + 12]
    if forward:
        return min(forward)

    backward = [n for n in nums if expected_qnum - 3 <= n < expected_qnum]
    if backward:
        return max(backward)

    return nums[0]


def content_bbox_in_rect(page: fitz.Page, rect: fitz.Rect) -> fitz.Rect | None:
    """
    Compute union bbox of text/image content within rect.
    If there is no content in rect, return None.
    """
    d = page.get_text("dict", clip=rect)
    boxes = []

    for b in d.get("blocks", []):
        btype = b.get("type")
        if btype == 1:
            bbox = b.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                boxes.append(fitz.Rect(*bbox))
            continue
        if btype != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                x0, y0, x1, y1 = span["bbox"]
                # ignore empty-ish spans
                if (span.get("text") or "").strip():
                    boxes.append(fitz.Rect(x0, y0, x1, y1))

    if not boxes:
        return None

    u = boxes[0]
    for bx in boxes[1:]:
        u |= bx
    # intersect with input rect for safety
    u &= rect
    return u


def build_segments_from_boundaries(page: fitz.Page, boundaries: list[float], pad_top=2.0, pad_bottom=2.0):
    """Convert y-boundaries into Rect segments."""
    H = page.rect.height
    W = page.rect.width
    segs = []
    for i in range(len(boundaries) - 1):
        y0 = max(0.0, boundaries[i] - pad_top)
        y1 = min(H, boundaries[i + 1] - pad_bottom)
        if y1 <= y0 + 2.0:
            continue
        segs.append(fitz.Rect(0.0, y0, W, y1))
    return segs


def crop_with_merge_contentaware(pdf_path: str,
                                 out_dir: str,
                                 dpi: int = 200,
                                 max_questions: int | None = None,
                                 # continuation detection
                                 top_gap: float = 40.0,
                                 bottom_gap: float = 40.0,
                                 # segment padding (boundary to crop)
                                 pad_top: float = 2.0,
                                 pad_bottom: float = 2.0,
                                 # content filtering
                                 min_chars: int = 20,
                                 min_height: float = 60.0,
                                 # tight crop padding around actual content bbox
                                 tight_pad: float = 6.0,
                                 # width option: full page width vs tight crop
                                 full_width: bool = True):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    last_page_index = len(doc) - 1

    questions = []
    current = None
    prev_page_open = False
    next_qnum = 1
    # Page 1 헤더 스킵을 위한 플래그
    first_question_found = False

    def save_part(qdict, page: fitz.Page, rect: fitz.Rect, page_index: int):
        part_idx = len(qdict["parts"]) + 1
        fname = f"Q{qdict['qnum']:02d}_p{page_index+1:02d}_part{part_idx}.png"
        fpath = os.path.join(out_dir, fname)
        pix = page.get_pixmap(clip=rect, dpi=dpi, alpha=False)
        pix.save(fpath)
        qdict["parts"].append({
            "page": page_index + 1,
            "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
            "image": fname
        })

    for pi in range(len(doc)):
        page = doc[pi]
        H = page.rect.height
        W = page.rect.width

        real_lines = get_horiz_gray_lines(page)

        # detect if there is a "real" separator near top/bottom
        top_missing_line = True
        bottom_missing_line = True
        if real_lines:
            if real_lines[0] <= top_gap:
                top_missing_line = False
            if (H - real_lines[-1]) <= bottom_gap:
                bottom_missing_line = False

        # boundaries: add synthetic top/bottom so last question on last page also works
        boundaries = list(real_lines)
        if not boundaries or boundaries[0] > top_gap:
            boundaries = [0.0] + boundaries
        if not boundaries or (H - boundaries[-1]) > bottom_gap:
            boundaries = boundaries + [H]

        raw_segments = build_segments_from_boundaries(page, boundaries, pad_top=pad_top, pad_bottom=pad_bottom)

        # ---- Content-aware filtering & tight crop ----
        segments = []
        is_first_content_found = False
        
        for rect in raw_segments:
            marker_based_segments = split_segment_by_markers(
                rect,
                find_question_markers(page, rect),
            )
            for seg_rect, marker_qnum in marker_based_segments:
                # PDF 원본 문제 번호 추출 (필터링 전에 확인하여 중요 세그먼트 보호)
                pdf_qnum = marker_qnum
                if pdf_qnum is None:
                    pdf_qnum = extract_question_number(
                        page, seg_rect, expected_qnum=next_qnum
                    )

                # Continuation filtering logic:
                is_continuation_candidate = (prev_page_open and not is_first_content_found)

                current_min_height = 15.0 if is_continuation_candidate else min_height
                current_min_chars = 10 if is_continuation_candidate else min_chars

                # 문제 번호가 있으면 필터링 무시하고 살림 (Q82 등 짧은 문제 보호)
                if pdf_qnum is None:
                    if seg_rect.height < current_min_height:
                        continue

                    n_chars = count_text_chars_in_rect(page, seg_rect)
                    if n_chars < current_min_chars and not has_image_block_in_rect(
                        page, seg_rect
                    ):
                        # 거의 공백(상/하단 여백)이라면 버림
                        continue

                # 유효한 컨텐츠를 찾았으므로 플래그 설정
                is_first_content_found = True

                cb = content_bbox_in_rect(page, seg_rect)
                if cb is None:
                    continue

                # crop rectangle: full width or tight crop
                if full_width:
                    crop_rect = fitz.Rect(
                        0.0,
                        max(0.0, cb.y0 - tight_pad),
                        W,
                        min(H, cb.y1 + tight_pad),
                    )
                else:
                    crop_rect = fitz.Rect(
                        max(0.0, cb.x0 - tight_pad),
                        max(0.0, cb.y0 - tight_pad),
                        min(W, cb.x1 + tight_pad),
                        min(H, cb.y1 + tight_pad),
                    )

                # 선지만 있는 세그먼트인지 확인
                is_choices_only = is_choices_only_segment(page, seg_rect)

                segments.append(
                    {
                        "rect": crop_rect,
                        "is_choices_only": is_choices_only,
                        "pdf_qnum": pdf_qnum,
                    }
                )

        if not segments:
            prev_page_open = False
            continue

        # continuation logic (page spanning):
        # If prev page was open (no bottom line) and this page has no top line,
        # then the FIRST segment continues the previous question.
        top_continuation = (pi > 0) and prev_page_open and top_missing_line

        # page is open-ended if there's no bottom line near bottom, except last page
        page_open = (pi < last_page_index) and bottom_missing_line

        seg_start_idx = 0
        
        # 첫 세그먼트 처리: top_continuation 여부와 is_choices_only 확인
        first_seg_is_choices_only = segments and segments[0]["is_choices_only"]
        first_seg_has_qnum = segments and segments[0]["pdf_qnum"] is not None
        
        if top_continuation and current is not None and not first_seg_has_qnum:
            # 이전 페이지에서 이어지는 문제 (회색선 없이 이어짐)
            # 단, 첫 세그먼트에 자체 문제 번호가 있으면 새 문제로 처리 (병합 안함)
            save_part(current, page, segments[0]["rect"], pi)
            seg_start_idx = 1
            
            # 이어지는 문제가 이번 페이지에서 완료되는지 확인
            only_one_segment = (len(segments) == 1)
            if not (only_one_segment and page_open):
                # 이어지는 문제가 이번 페이지에서 완료됨
                next_qnum = max(next_qnum, int(current.get("qnum") or 0) + 1)
                
        elif first_seg_is_choices_only and current is not None:
            # 이전 페이지에서 회색선으로 분리되었지만, 첫 세그먼트가 선지만 있음
            # 이전 문제(current)에 선지를 병합
            save_part(current, page, segments[0]["rect"], pi)
            seg_start_idx = 1
            
            # 이 문제가 완료되었는지 확인
            only_one_segment = (len(segments) == 1)
            if not (only_one_segment and page_open):
                # 이 문제가 완료됨
                next_qnum = max(next_qnum, int(current.get("qnum") or 0) + 1)

        # 중간 세그먼트들: 각각 새 문제 (마지막 세그먼트 제외)
        last_seg_idx = len(segments) - 1
        for si in range(seg_start_idx, len(segments)):
            if max_questions is not None and len(questions) >= max_questions:
                break
            
            seg = segments[si]
            seg_rect = seg["rect"]
            is_choices_only = seg["is_choices_only"]
            pdf_qnum = seg["pdf_qnum"]  # PDF 원본 문제 번호 (없으면 None)
            is_last_segment = (si == last_seg_idx)
            
            # Page 1 Header Skip Logic (시험 제목 등 제외)
            if pi == 0 and not first_question_found:
                if pdf_qnum is not None:
                    first_question_found = True
                else:
                    # pdf_qnum이 없으면 헤더일 수 있음.
                    # 하지만 "헤더 + 1번 문제"가 하나의 세그먼트로 묶여있는 경우(회색선 없음)를 처리해야 함.
                    # "1. " 패턴을 찾아서 그 위치부터 시작하도록 크롭 조정
                    hits = page.search_for("1. ", clip=seg_rect)
                    valid_hit = None
                    
                    # 가장 상단/좌측에 있는 "1. "을 찾음 (헤더 날짜 등 오인 방지 위해 x 좌표 체크 등 가능하나 "1. "은 드묾)
                    if hits:
                        # y 좌표 순 정렬
                        hits.sort(key=lambda r: (r.y0, r.x0))
                        
                        # 가장 첫 번째 hits가 Q1일 확률 높음. 
                        # 단, 너무 오른쪽에 있으면 아닐 수도? (보통 문제는 왼쪽 정렬)
                        for hit in hits:
                            if hit.x0 < W * 0.5: # 페이지 절반 왼쪽에 있어야 함
                                valid_hit = hit
                                break
                    
                    if valid_hit:
                        # 1번 문제 찾음!
                        # 세그먼트의 시작 y를 "1."의 y0로 조정 (약간의 패딩 -2.0)
                        new_y0 = max(seg_rect.y0, valid_hit.y0 - 2.0)
                        
                        # rect 재설정
                        # full_width/tight_crop 설정에 따라 x좌표는 유지하거나 조정해야 하지만
                        # 여기서는 y축만 잘라내면 됨 (상단 헤더 날림)
                        crop_rect = fitz.Rect(seg_rect.x0, new_y0, seg_rect.x1, seg_rect.y1)
                        seg["rect"] = crop_rect
                        seg_rect = crop_rect
                        
                        # qnum 강제 설정
                        seg["pdf_qnum"] = 1
                        pdf_qnum = 1
                        first_question_found = True
                        # 계속 진행 (save_part 호출됨)
                    else:
                        # 첫 문제가 나오기 전의 세그먼트(헤더)는 건너뜀
                        continue
            
            # 선지만 있는 세그먼트인 경우: 이전 문제에 병합
            if is_choices_only and current is not None:
                # 기존 문제에 파트 추가 (새 문제 생성 안함)
                save_part(current, page, seg_rect, pi)
                # 이 세그먼트를 추가해도 current는 유지
                continue
            
            # 새 문제 번호 결정: PDF 원본 번호 우선, 없으면 순차 번호 사용
            new_qnum = pdf_qnum if pdf_qnum is not None else next_qnum
            next_qnum = max(next_qnum, int(new_qnum) + 1)
            
            # 마지막 세그먼트가 다음 페이지로 이어지는 경우
            if is_last_segment and page_open:
                # 새 문제 시작
                current = {"qnum": new_qnum, "parts": []}
                questions.append(current)
                save_part(current, page, seg_rect, pi)
            else:
                # 일반 세그먼트: 완결된 문제
                current = {"qnum": new_qnum, "parts": []}
                questions.append(current)
                save_part(current, page, seg_rect, pi)
                # 완결된 문제이므로 current 유지 (선지만 있는 다음 세그먼트가 병합될 수 있도록)

        prev_page_open = page_open

        if max_questions is not None and len(questions) >= max_questions:
            break

    meta = {
        "pdf": os.path.basename(pdf_path),
        "dpi": dpi,
        "params": {
            "top_gap": top_gap, "bottom_gap": bottom_gap,
            "pad_top": pad_top, "pad_bottom": pad_bottom,
            "min_chars": min_chars, "min_height": min_height,
            "tight_pad": tight_pad
        },
        "questions": questions
    }
    with open(os.path.join(out_dir, "bboxes.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Saved questions: {len(questions)} to {out_dir}")
    if questions:
        multi = sum(1 for q in questions if len(q["parts"]) > 1)
        print(f"Multi-part(page-spanning): {multi}")
    
    # Merge multi-part questions
    merge_multipart_questions(questions, out_dir, dpi)


def merge_multipart_questions(questions, out_dir, dpi):
    """
    Find questions with multiple parts and merge them vertically into a single image.
    Uses a temporary PDF page to assemble images.
    Saves as Q{n}_merged.png
    """
    merged_count = 0
    # Create a temp doc once
    temp_doc = fitz.open()

    for q in questions:
        if len(q['parts']) <= 1:
            continue
            
        try:
            # First pass: calculate total dimensions
            parts_info = []
            total_height = 0
            max_width = 0
            
            for p in q['parts']:
                img_path = os.path.join(out_dir, p['image'])
                if not os.path.exists(img_path):
                    continue
                
                # Use Pixmap directly to get exact pixel dimensions
                pix = fitz.Pixmap(img_path)
                w, h = pix.width, pix.height
                parts_info.append({"path": img_path, "w": w, "h": h})
                total_height += h
                max_width = max(max_width, w)
                pix = None # Release
            
            if not parts_info:
                continue

            # Create a new page in temp_doc
            # width/height are in points. 
            # We treat them as pixels since we will render at 72 dpi default
            temp_page = temp_doc.new_page(width=max_width, height=total_height)
            
            current_y = 0
            for p in parts_info:
                # Center horizontally
                x_offset = (max_width - p["w"]) / 2
                rect = fitz.Rect(x_offset, current_y, x_offset + p["w"], current_y + p["h"])
                temp_page.insert_image(rect, filename=p["path"])
                current_y += p["h"]
            
            # Render to pixmap at 72 dpi to match points=pixels
            pix = temp_page.get_pixmap(dpi=72)
            
            merged_filename = f"Q{q['qnum']}_merged.png"
            if isinstance(q['qnum'], int):
                merged_filename = f"Q{q['qnum']:02d}_merged.png"
            
            pix.save(os.path.join(out_dir, merged_filename))
            merged_count += 1
            
            # Delete page to reset for next question
            temp_doc.delete_page(0)
            
            # Delete individual part files
            for p in q['parts']:
                try:
                    p_path = os.path.join(out_dir, p['image'])
                    if os.path.exists(p_path):
                        os.remove(p_path)
                except Exception as del_err:
                    print(f"Warning: Could not delete part file {p['image']}: {del_err}")
            
        except Exception as e:
            print(f"Error merging Q{q['qnum']}: {e}")
            
    temp_doc.close()
    
    if merged_count > 0:
        print(f"Merged {merged_count} multi-part questions into single images.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="exam_crops")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-questions", type=int, default=None)
    ap.add_argument("--min-chars", type=int, default=20, help="Segments with fewer chars are treated as margins and skipped")
    ap.add_argument("--min-height", type=float, default=60.0)
    ap.add_argument("--tight-pad", type=float, default=6.0)
    ap.add_argument("--top-gap", type=float, default=40.0)
    ap.add_argument("--bottom-gap", type=float, default=40.0)
    ap.add_argument("--pad-top", type=float, default=2.0)
    ap.add_argument("--pad-bottom", type=float, default=2.0)
    ap.add_argument("--full-width", action="store_true", default=True, 
                    help="Keep full page width (default: True)")
    ap.add_argument("--tight-crop", action="store_true", default=False,
                    help="Use tight crop instead of full width")
    args = ap.parse_args()

    # --tight-crop가 지정되면 full_width=False
    full_width = not args.tight_crop

    crop_with_merge_contentaware(
        pdf_path=args.pdf,
        out_dir=args.out,
        dpi=args.dpi,
        max_questions=args.max_questions,
        top_gap=args.top_gap,
        bottom_gap=args.bottom_gap,
        pad_top=args.pad_top,
        pad_bottom=args.pad_bottom,
        min_chars=args.min_chars,
        min_height=args.min_height,
        tight_pad=args.tight_pad,
        full_width=full_width
    )
