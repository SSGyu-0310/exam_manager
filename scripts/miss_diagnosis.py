#!/usr/bin/env python3
"""
Miss Diagnosis Report Generator for P1 retrieval improvement.

Reads a run_log.jsonl from an evaluation run, extracts all miss cases
(gold_in_candidates == false), and generates a detailed diagnostic report.

Usage:
  docker compose exec api bash -lc '
    python scripts/miss_diagnosis.py \
      --db "$DATABASE_URL" \
      --run-log reports/p1_scope_filter/run_log.jsonl \
      --output-dir reports/p1_miss_diagnosis
  '
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import text as sa_text
from app import create_app, db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MATH_SYMBOL_RE = re.compile(r"[^\w\s가-힣]")
_CJK_RE = re.compile(r"[\u3000-\u9fff\uac00-\ud7ff]")
_TOKEN_RE = re.compile(
    r"""
    [A-Za-z]+[+-]?
    |[가-힣]+
    |\d+
    """,
    re.VERBOSE,
)


def _rough_token_count(text: str) -> int:
    if not text:
        return 0
    return len(_TOKEN_RE.findall(text))


def _extract_tokens(text: str) -> set:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


def _math_symbol_ratio(text: str) -> float:
    if not text:
        return 0.0
    total = len(text.strip())
    if total == 0:
        return 0.0
    symbols = len(_MATH_SYMBOL_RE.findall(text))
    return symbols / total


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------

def get_gold_lecture_chunks(gold_lecture_id: int) -> List[Dict]:
    """Get all chunks for the gold lecture."""
    sql = sa_text("""
        SELECT c.id, c.lecture_id, c.page_start, c.page_end,
               c.char_len, LENGTH(c.content) AS content_len,
               LEFT(regexp_replace(c.content, '\\s+', ' ', 'g'), 200) AS content_preview
        FROM lecture_chunks c
        WHERE c.lecture_id = :lecture_id
        ORDER BY c.page_start
    """)
    rows = db.session.execute(sql, {"lecture_id": gold_lecture_id}).mappings().all()
    return [dict(r) for r in rows]


def get_lecture_info(lecture_id: int) -> Dict:
    """Get lecture title and block info."""
    sql = sa_text("""
        SELECT l.id, l.title, l.block_id, b.name AS block_name
        FROM lectures l
        JOIN blocks b ON l.block_id = b.id
        WHERE l.id = :lid
    """)
    row = db.session.execute(sql, {"lid": lecture_id}).mappings().first()
    return dict(row) if row else {}


def get_question_text(question_id: int) -> str:
    """Get question text with choices."""
    sql = sa_text("""
        SELECT q.content,
               (SELECT string_agg(c.content, ' ' ORDER BY c.choice_number)
                FROM choices c WHERE c.question_id = q.id) AS choices_text
        FROM questions q WHERE q.id = :qid
    """)
    row = db.session.execute(sql, {"qid": question_id}).mappings().first()
    if not row:
        return ""
    text = (row.get("content") or "")
    choices = (row.get("choices_text") or "")
    if choices:
        text = f"{text}\n{choices}"
    return text.strip()


# ---------------------------------------------------------------------------
# Miss classification
# ---------------------------------------------------------------------------

def classify_miss(
    question_text: str,
    gold_chunks: List[Dict],
    top_candidates: List[Dict],
    fp_counter: Counter,
) -> str:
    """Classify miss type using rule-based heuristics."""

    # 1. indexing_gap: no chunks or very short
    if not gold_chunks:
        return "indexing_gap"
    total_chars = sum(c.get("content_len", 0) or c.get("char_len", 0) or 0 for c in gold_chunks)
    if total_chars < 100:
        return "indexing_gap"

    # 2. query_noise: high symbol ratio
    if _math_symbol_ratio(question_text) > 0.40:
        return "query_noise"

    # 3. vocabulary_shift: low token overlap between question and chunks
    q_tokens = _extract_tokens(question_text)
    chunk_text = " ".join(c.get("content_preview", "") for c in gold_chunks)
    c_tokens = _extract_tokens(chunk_text)
    if q_tokens and c_tokens:
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
        if overlap < 0.10:
            return "vocabulary_shift"

    # 4. fp_dominance: top-1 candidate appears too often across misses
    if top_candidates:
        top1_id = top_candidates[0].get("lecture_id")
        if top1_id and fp_counter.get(top1_id, 0) >= 5:
            return "fp_dominance"

    return "other"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_diagnosis(run_log_path: str, output_dir: str):
    """Read run_log.jsonl and generate miss diagnosis report."""
    records = []
    with open(run_log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    misses = [r for r in records if not r.get("gold_in_candidates", True)]
    print(f"[miss_diagnosis] Total records: {len(records)}, misses: {len(misses)}")

    if not misses:
        print("[miss_diagnosis] No misses found. Nothing to diagnose.")
        return

    # First pass: count FP occurrences
    fp_counter: Counter = Counter()
    for m in misses:
        cands = m.get("candidates", [])
        if cands:
            top1_id = cands[0].get("lecture_id")
            if top1_id is not None:
                fp_counter[top1_id] += 1

    # Second pass: detailed analysis
    diagnoses: List[Dict] = []
    type_counter: Counter = Counter()

    for m in misses:
        qid = m["question_id"]
        gold_id = m["gold_lecture_id"]
        top_cands = m.get("candidates", [])[:5]

        # DB queries
        question_text = get_question_text(qid)
        gold_chunks = get_gold_lecture_chunks(gold_id)
        gold_info = get_lecture_info(gold_id)

        # Classify miss type
        miss_type = classify_miss(question_text, gold_chunks, top_cands, fp_counter)
        type_counter[miss_type] += 1

        # Build snippet for top-5 candidates
        cand_summaries = []
        for c in top_cands:
            cand_info = get_lecture_info(c.get("lecture_id", 0))
            cand_summaries.append({
                "lecture_id": c.get("lecture_id"),
                "title": cand_info.get("title", ""),
                "block_name": cand_info.get("block_name", ""),
                "rank": c.get("rank"),
                "score": c.get("score"),
            })

        diagnoses.append({
            "question_id": qid,
            "gold_lecture_id": gold_id,
            "gold_lecture_title": gold_info.get("title", ""),
            "gold_block_name": gold_info.get("block_name", ""),
            "gold_chunk_count": len(gold_chunks),
            "gold_total_chars": sum(c.get("content_len") or c.get("char_len") or 0 for c in gold_chunks),
            "question_text_len": len(question_text),
            "question_token_count": _rough_token_count(question_text),
            "math_symbol_ratio": round(_math_symbol_ratio(question_text), 3),
            "miss_type": miss_type,
            "top5_candidates": cand_summaries,
            "question_preview": question_text[:120].replace("\n", " "),
        })

    # Write JSONL
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "miss_report.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for d in diagnoses:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(diagnoses)} diagnoses to {jsonl_path}")

    # Write markdown report
    md_path = out_dir / "miss_report.md"
    lines = []
    lines.append("# Miss Diagnosis Report")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append(f"Source: `{run_log_path}`")
    lines.append("")
    lines.append(f"**Total records**: {len(records)}  ")
    lines.append(f"**Total misses**: {len(misses)}")
    lines.append("")

    # Type distribution
    lines.append("## Miss Type Distribution")
    lines.append("")
    lines.append("| Type | Count | % |")
    lines.append("|---|---|---|")
    for mtype, cnt in type_counter.most_common():
        pct = round(cnt / len(misses) * 100, 1)
        lines.append(f"| {mtype} | {cnt} | {pct}% |")
    lines.append("")

    # FP dominance
    lines.append("## FP Lecture Frequency (Top-1 in miss cases)")
    lines.append("")
    lines.append("| Lecture ID | Title | FP Count |")
    lines.append("|---|---|---|")
    for lid, cnt in fp_counter.most_common(10):
        info = get_lecture_info(lid)
        title = info.get("title", "?")
        lines.append(f"| {lid} | {title} | {cnt} |")
    lines.append("")

    # Per-question detail
    lines.append("## Per-Question Details")
    lines.append("")

    for d in diagnoses:
        qid = d["question_id"]
        lines.append(f"### Q{qid}")
        lines.append(f"- **Gold**: lecture {d['gold_lecture_id']} — {d['gold_lecture_title']} ({d['gold_block_name']})")
        lines.append(f"- **Miss type**: `{d['miss_type']}`")
        lines.append(f"- **Gold chunks**: {d['gold_chunk_count']} (total {d['gold_total_chars']} chars)")
        lines.append(f"- **Question**: {d['question_preview']}...")
        lines.append(f"- **Math symbol ratio**: {d['math_symbol_ratio']}")
        lines.append("- **Top-5 candidates**:")
        for c in d["top5_candidates"]:
            lines.append(f"  - rank {c['rank']}: L{c['lecture_id']} ({c['title']}) score={c['score']}")
        lines.append("")

    # Recommended next actions
    lines.append("---")
    lines.append("")
    lines.append("## Recommended Actions")
    lines.append("")

    if type_counter.get("indexing_gap", 0) > 0:
        lines.append(f"1. **인덱싱 재생성** — indexing_gap {type_counter['indexing_gap']}건: "
                      "gold lecture의 chunk가 없거나 빈약. 강의 노트 PDF를 재업로드/재파싱.")
    if type_counter.get("vocabulary_shift", 0) > 0:
        lines.append(f"2. **동의어 사전** — vocabulary_shift {type_counter['vocabulary_shift']}건: "
                      "문제 텍스트와 강의 노트의 용어 불일치. "
                      "동의어 매핑(예: '심박출량'↔'cardiac output')을 BM25 쿼리에 추가.")
    if type_counter.get("query_noise", 0) > 0:
        lines.append(f"3. **쿼리 정규화** — query_noise {type_counter['query_noise']}건: "
                      "수식/기호 과다. 전처리에서 수식 제거 또는 LaTeX→텍스트 변환 적용.")
    if type_counter.get("fp_dominance", 0) > 0:
        top_fp_id, top_fp_cnt = fp_counter.most_common(1)[0]
        top_fp_info = get_lecture_info(top_fp_id)
        lines.append(f"4. **FP 억제** — fp_dominance {type_counter['fp_dominance']}건: "
                      f"lecture {top_fp_id} ({top_fp_info.get('title', '?')})가 "
                      f"miss 중 {top_fp_cnt}건에서 top-1. "
                      "해당 강의 chunk 품질 점검 또는 BM25 boost 조정 고려.")
    if type_counter.get("other", 0) > 0:
        lines.append(f"5. **기타** — other {type_counter['other']}건: "
                      "TRGM score blending(P1-2)으로 개선 가능성 확인.")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote report to {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Miss diagnosis report generator.")
    parser.add_argument("--run-log", required=True, help="Path to run_log.jsonl")
    parser.add_argument("--output-dir", default="reports/p1_miss_diagnosis", help="Output directory")
    parser.add_argument("--db", default=None, help="DATABASE_URL override")

    args = parser.parse_args()

    config_name = os.environ.get("FLASK_CONFIG") or "default"
    db_url = args.db or os.environ.get("DATABASE_URL")
    app = create_app(config_name, db_uri_override=db_url, skip_migration_check=True)

    with app.app_context():
        run_diagnosis(args.run_log, args.output_dir)


if __name__ == "__main__":
    main()
