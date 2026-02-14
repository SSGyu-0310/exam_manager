#!/usr/bin/env python3
"""
Enhanced classification pipeline evaluation with structured instrumentation.

Produces per-question JSONL logs, decomposed metrics (Recall@K, Judge Accuracy|Given-hit,
Apply Precision/Coverage), latency breakdown, and error taxonomy.

Usage:
  # Baseline run (retrieval-only, no LLM):
  python scripts/eval_classifier_run.py --output-dir reports/baseline

  # Full run with live LLM classification:
  python scripts/eval_classifier_run.py --run-classifier --output-dir reports/baseline

  # Sweep top-k:
  python scripts/eval_classifier_run.py --run-classifier --top-k-sweep 8,12,16

  # With question ID filter:
  python scripts/eval_classifier_run.py --run-classifier \
      --question-ids-file evalset_question_ids.txt --output-dir reports/baseline
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app import create_app, db
from app.models import EvaluationLabel, Question, Lecture, Block
from app.services import retrieval
from app.services.ai_classifier import GeminiClassifier
from app.services.classifier_cache import ClassifierResultCache, build_config_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_question_ids(path: str) -> set[int]:
    ids = set()
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            try:
                ids.add(int(raw))
            except ValueError:
                pass
    return ids


def _build_question_text(question: Question) -> str:
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    qt = question.content or ""
    if choices:
        qt = f"{qt}\n" + " ".join(choices)
    qt = qt.strip()
    if len(qt) > 4000:
        qt = qt[:4000]
    return qt


def _rough_token_count(text: str) -> int:
    """Rough token count (words + CJK chars)."""
    if not text:
        return 0
    eng_words = len(re.findall(r"[A-Za-z]+", text))
    cjk_chars = len(re.findall(r"[\u3000-\u9fff\uac00-\ud7ff]", text))
    digits = len(re.findall(r"\d+", text))
    return eng_words + cjk_chars + digits


def _classifier_config_hash(app, retrieval_mode, max_k, evidence_per_lecture):
    cfg = {
        "retrieval_mode": retrieval_mode,
        "max_k": max_k,
        "evidence_per_lecture": evidence_per_lecture,
        "parent_enabled": bool(app.config.get("PARENT_ENABLED", False)),
    }
    return build_config_hash(cfg)


# ---------------------------------------------------------------------------
# Single question classification with instrumentation
# ---------------------------------------------------------------------------


def _classify_one(
    app,
    question_id: int,
    candidates: List[Dict],
    expand_context: bool,
) -> Tuple[int, Dict, float, int]:
    """Classify one question, return (qid, result_dict, latency_ms, retry_count)."""
    from app.models import Question
    from app.services.context_expander import expand_candidates

    with app.app_context():
        question = db.session.get(Question, question_id)
        if not question:
            return question_id, {
                "lecture_id": None,
                "confidence": 0.0,
                "reason": "Missing question",
                "evidence": [],
                "no_match": True,
                "model_name": "",
            }, 0.0, 0

        if expand_context:
            candidates = expand_candidates(candidates)

        t0 = time.perf_counter()
        classifier = GeminiClassifier()
        result = classifier.classify_single(question, candidates)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        retry_count = 0
        return question_id, result, elapsed_ms, retry_count


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def run_evaluation(app, args) -> Dict[str, Any]:
    """Run the full evaluation pipeline and produce structured logs + metrics."""

    retrieval_mode = (args.retrieval_mode or os.environ.get("RETRIEVAL_MODE", "bm25")).strip().lower()
    if retrieval_mode != "bm25":
        retrieval_mode = "bm25"
    top_k = args.top_k
    evidence_per_lecture = args.evidence_per_lecture
    threshold = args.confidence_threshold
    margin_delta = args.apply_margin

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        # Load evaluation labels
        labels_query = (
            EvaluationLabel.query.join(Question)
            .order_by(EvaluationLabel.id.asc())
        )
        if args.labels_source:
            labels_query = labels_query.filter(
                EvaluationLabel.source == args.labels_source
            )
        if args.question_ids_file:
            ids = _load_question_ids(args.question_ids_file)
            if ids:
                labels_query = labels_query.filter(
                    EvaluationLabel.question_id.in_(ids)
                )

        labels = labels_query.all()
        if not labels:
            print("[error] No evaluation labels found. Run backfill_eval_labels.py first.")
            return {}

        if args.limit:
            labels = labels[: args.limit]

        # Build lecture ID -> title map for reporting
        all_lecture_ids = set()
        for label in labels:
            if label.gold_lecture_id:
                all_lecture_ids.add(label.gold_lecture_id)
        if all_lecture_ids:
            lectures = Lecture.query.filter(Lecture.id.in_(all_lecture_ids)).all()
        else:
            lectures = []
        lecture_title_map = {}
        for lec in lectures:
            if lec.block:
                lecture_title_map[lec.id] = f"{lec.block.name} > {lec.title}"
            else:
                lecture_title_map[lec.id] = lec.title

        # ---- Phase 1: Retrieval for all questions ----
        retrieval_records: List[Dict[str, Any]] = []
        total = len(labels)

        for idx, label in enumerate(labels):
            if not label.gold_lecture_id:
                continue
            if label.is_ambiguous and not args.include_ambiguous:
                continue

            question = label.question
            if not question:
                continue

            question_text = _build_question_text(question)
            scope_subject = question.exam.subject if question.exam else None
            scope_lecture_ids = getattr(args, '_resolved_scope_lecture_ids', None)

            # ----- RETRIEVE stage with timing -----
            t_retrieve_start = time.perf_counter()

            chunks = retrieval.search_chunks_bm25(
                question_text,
                top_n=80,
                question_id=question.id,
                lecture_ids=scope_lecture_ids,
            )
            candidates = retrieval.aggregate_candidates(
                chunks,
                top_k_lectures=top_k,
                evidence_per_lecture=evidence_per_lecture,
                agg_mode=getattr(args, 'lecture_agg_mode', 'sum') or 'sum',
                topm=getattr(args, 'lecture_topm', 3) or 3,
                chunk_cap=getattr(args, 'lecture_chunk_cap', 0) or 0,
            )

            t_retrieve_ms = (time.perf_counter() - t_retrieve_start) * 1000.0

            # Compute candidate info
            candidate_ids = [c.get("id") for c in candidates if c.get("id") is not None]
            gold_in_candidates = label.gold_lecture_id in candidate_ids
            gold_rank = None
            if gold_in_candidates:
                gold_rank = candidate_ids.index(label.gold_lecture_id)

            candidate_details = []
            for rank_idx, cand in enumerate(candidates):
                ev_chunk_ids = [
                    e.get("chunk_id")
                    for e in (cand.get("evidence") or [])
                    if e.get("chunk_id") is not None
                ]
                candidate_details.append({
                    "lecture_id": cand.get("id"),
                    "full_path": cand.get("full_path", ""),
                    "rank": rank_idx,
                    "score": round(cand.get("score", 0.0), 6),
                    "evidence_chunk_ids": ev_chunk_ids,
                })

            retrieval_records.append({
                "label": label,
                "question": question,
                "question_text": question_text,
                "question_text_len": len(question_text),
                "question_text_tokens": _rough_token_count(question_text),
                "scope_subject": scope_subject,
                "candidates": candidates,
                "candidate_ids": candidate_ids,
                "candidate_details": candidate_details,
                "gold_lecture_id": label.gold_lecture_id,
                "gold_lecture_title": lecture_title_map.get(label.gold_lecture_id, ""),
                "gold_in_candidates": gold_in_candidates,
                "gold_rank": gold_rank,
                "retrieve_latency_ms": round(t_retrieve_ms, 2),
            })

            if (idx + 1) % 20 == 0:
                print(f"  Retrieval: {idx + 1}/{total} done...")

        print(f"  Retrieval complete: {len(retrieval_records)} questions evaluated.")

        # ---- Phase 2: Classification (optional) ----
        if args.run_classifier:
            cache = None
            config_hash = None
            if not args.no_cache:
                cache_path = app.config.get("CLASSIFIER_CACHE_PATH") or str(
                    ROOT_DIR / "data" / "classifier_cache.json"
                )
                cache = ClassifierResultCache(cache_path)
                config_hash = _classifier_config_hash(
                    app, retrieval_mode, top_k, evidence_per_lecture
                )
            model_name = app.config.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")

            pending = []
            for rec in retrieval_records:
                cached = None
                if cache and config_hash:
                    cached = cache.get(rec["question"].id, config_hash, model_name)
                if cached:
                    result = cached.get("result") or {}
                    rec["llm_lecture_id"] = result.get("lecture_id")
                    rec["llm_confidence"] = float(result.get("confidence") or 0.0)
                    rec["llm_no_match"] = bool(result.get("no_match", False))
                    rec["llm_evidence"] = result.get("evidence", [])
                    rec["llm_reason"] = result.get("reason", "")
                    rec["llm_model_name"] = result.get("model_name", model_name)
                    rec["judge_latency_ms"] = 0.0
                    rec["llm_retries"] = 0
                    rec["from_cache"] = True
                    continue

                pending.append(rec)

            if pending:
                max_workers = max(1, args.max_workers)
                print(f"  Classifying {len(pending)} questions with {max_workers} workers...")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    for rec in pending:
                        expand_context = bool(app.config.get("PARENT_ENABLED", False))
                        cands = copy.deepcopy(rec["candidates"])
                        future = executor.submit(
                            _classify_one, app, rec["question"].id, cands, expand_context
                        )
                        futures[future] = rec

                    done_count = 0
                    for future in as_completed(futures):
                        rec = futures[future]
                        try:
                            qid, result, latency_ms, retry_count = future.result()
                        except Exception as exc:
                            result = {
                                "lecture_id": None,
                                "confidence": 0.0,
                                "reason": f"Error: {exc}",
                                "evidence": [],
                                "no_match": True,
                                "model_name": model_name,
                            }
                            latency_ms = 0.0
                            retry_count = 0

                        rec["llm_lecture_id"] = result.get("lecture_id")
                        rec["llm_confidence"] = float(result.get("confidence") or 0.0)
                        rec["llm_no_match"] = bool(result.get("no_match", False))
                        rec["llm_evidence"] = result.get("evidence", [])
                        rec["llm_reason"] = result.get("reason", "")
                        rec["llm_model_name"] = result.get("model_name", model_name)
                        rec["judge_latency_ms"] = round(latency_ms, 2)
                        rec["llm_retries"] = retry_count
                        rec["from_cache"] = False

                        if cache and config_hash:
                            cache.set(rec["question"].id, config_hash, model_name, result)

                        done_count += 1
                        if done_count % 10 == 0:
                            print(f"    Classified {done_count}/{len(pending)} ...")

                if cache:
                    cache.save()

            print("  Classification complete.")

        else:
            # Pull existing AI results from DB
            for rec in retrieval_records:
                q = rec["question"]
                rec["llm_lecture_id"] = q.ai_suggested_lecture_id or q.ai_final_lecture_id
                rec["llm_confidence"] = float(q.ai_confidence or 0.0)
                rec["llm_no_match"] = rec["llm_lecture_id"] is None
                rec["llm_evidence"] = []
                rec["llm_reason"] = q.ai_reason or ""
                rec["llm_model_name"] = q.ai_model_name or ""
                rec["judge_latency_ms"] = 0.0
                rec["llm_retries"] = 0
                rec["from_cache"] = False

        # ---- Phase 3: Compute metrics & write outputs ----
        return _compute_and_write(
            retrieval_records, output_dir, args, threshold, margin_delta, top_k
        )


# ---------------------------------------------------------------------------
# Metrics computation and output
# ---------------------------------------------------------------------------


def _compute_and_write(
    records: List[Dict],
    output_dir: Path,
    args,
    threshold: float,
    margin_delta: float,
    top_k: int,
) -> Dict[str, Any]:
    """Compute all metrics, write JSONL logs and summary."""

    log_path = output_dir / "run_log.jsonl"
    jsonl_lines = []

    total = len(records)
    recall_at = {k: 0 for k in [1, 3, 5, 8, 10, 12, 16]}
    judge_given_hit_total = 0
    judge_given_hit_correct = 0
    apply_total = 0
    apply_correct = 0
    apply_incorrect = 0
    no_match_count = 0
    retrieval_no_candidate = 0
    retrieval_gold_not_in_topk = 0

    retrieve_latencies = []
    judge_latencies = []
    total_latencies = []
    retry_counts = []

    # FP tracking: count how often each non-gold lecture appears as top-1
    fp_lecture_counter: Dict[int, int] = {}

    errors_retrieval_miss = []
    errors_judge_miss = []

    for rec in records:
        qid = rec["question"].id
        gold_id = rec["gold_lecture_id"]
        gold_in_cands = rec["gold_in_candidates"]
        gold_rank = rec["gold_rank"]

        llm_id = rec.get("llm_lecture_id")
        llm_conf = rec.get("llm_confidence", 0.0)
        llm_no_match = rec.get("llm_no_match", True)
        candidate_ids = rec["candidate_ids"]

        # ---- Retrieval breakdown ----
        if not candidate_ids:
            retrieval_no_candidate += 1
        if not gold_in_cands:
            retrieval_gold_not_in_topk += 1

        # ---- FP tracking: if gold not hit, record top-1 candidate ----
        if not gold_in_cands and candidate_ids:
            fp_top1 = candidate_ids[0]
            fp_lecture_counter[fp_top1] = fp_lecture_counter.get(fp_top1, 0) + 1

        # ---- Recall@K ----
        for k in recall_at:
            if gold_rank is not None and gold_rank < k:
                recall_at[k] += 1

        # ---- Judge Accuracy | Given-hit ----
        if gold_in_cands:
            judge_given_hit_total += 1
            if llm_id == gold_id:
                judge_given_hit_correct += 1

        # ---- Apply decision simulation ----
        apply_decision = "not_applied"
        apply_reason = ""

        if llm_no_match:
            apply_decision = "no_match"
            apply_reason = "llm_no_match"
            no_match_count += 1
        elif llm_id is None:
            apply_decision = "no_lecture_id"
            apply_reason = "null_lecture_id"
        elif llm_id not in candidate_ids:
            apply_decision = "out_of_candidates"
            apply_reason = "lecture_not_in_candidates"
        elif llm_conf < threshold:
            apply_decision = "low_confidence"
            apply_reason = f"conf={llm_conf:.3f}<{threshold}"
        else:
            apply_decision = "applied"
            apply_reason = f"conf={llm_conf:.3f}>=threshold"
            apply_total += 1
            if llm_id == gold_id:
                apply_correct += 1
            else:
                apply_incorrect += 1

        # ---- Error taxonomy ----
        error_type = None
        if llm_id != gold_id:
            if not gold_in_cands:
                error_type = "retrieval_miss"
                errors_retrieval_miss.append({
                    "question_id": qid,
                    "gold_lecture_id": gold_id,
                    "gold_lecture_title": rec["gold_lecture_title"],
                    "predicted_lecture_id": llm_id,
                    "candidates_top3": rec["candidate_details"][:3],
                })
            else:
                error_type = "judge_miss"
                errors_judge_miss.append({
                    "question_id": qid,
                    "gold_lecture_id": gold_id,
                    "gold_lecture_title": rec["gold_lecture_title"],
                    "gold_rank": gold_rank,
                    "predicted_lecture_id": llm_id,
                    "llm_confidence": llm_conf,
                    "llm_reason": rec.get("llm_reason", ""),
                    "candidates_top3": rec["candidate_details"][:3],
                })

        # ---- Latencies ----
        ret_lat = rec.get("retrieve_latency_ms", 0.0)
        judge_lat = rec.get("judge_latency_ms", 0.0)
        total_lat = ret_lat + judge_lat
        retrieve_latencies.append(ret_lat)
        judge_latencies.append(judge_lat)
        total_latencies.append(total_lat)
        retry_counts.append(rec.get("llm_retries", 0))

        # ---- JSONL record ----
        log_record = {
            "question_id": qid,
            "question_text_len": rec["question_text_len"],
            "question_text_tokens": rec["question_text_tokens"],
            "scope_subject": rec.get("scope_subject"),
            "candidates": rec["candidate_details"],
            "gold_lecture_id": gold_id,
            "gold_lecture_title": rec["gold_lecture_title"],
            "gold_in_candidates": gold_in_cands,
            "gold_rank": gold_rank,
            "llm_output": {
                "lecture_id": llm_id,
                "confidence": round(llm_conf, 4),
                "no_match": llm_no_match,
                "reason": rec.get("llm_reason", ""),
                "evidence_count": len(rec.get("llm_evidence") or []),
            },
            "apply_decision": apply_decision,
            "apply_reason": apply_reason,
            "error_type": error_type,
            "latency_ms": {
                "retrieve": ret_lat,
                "judge": judge_lat,
                "total": round(total_lat, 2),
            },
            "llm_retries": rec.get("llm_retries", 0),
            "from_cache": rec.get("from_cache", False),
        }
        jsonl_lines.append(json.dumps(log_record, ensure_ascii=False))

    # Write JSONL
    log_path.write_text("\n".join(jsonl_lines), encoding="utf-8")
    print(f"  Wrote {len(jsonl_lines)} records to {log_path}")

    # ---- Compute summary metrics ----
    def _percentile(values, p):
        if not values:
            return 0.0
        s = sorted(values)
        k = (len(s) - 1) * p / 100.0
        f = int(k)
        c = f + 1 if f + 1 < len(s) else f
        return s[f] + (k - f) * (s[c] - s[f])

    def _mean(values):
        return sum(values) / len(values) if values else 0.0

    recall_rates = {}
    recall_counts_dict = {}
    for k in recall_at:
        recall_rates[f"recall@{k}"] = round(recall_at[k] / total, 4) if total else 0
        recall_counts_dict[f"recall@{k}_count"] = recall_at[k]

    if judge_given_hit_total > 0:
        judge_accuracy_given_hit = round(judge_given_hit_correct / judge_given_hit_total, 4)
    else:
        judge_accuracy_given_hit = None

    if apply_total > 0:
        apply_precision = round(apply_correct / apply_total, 4)
    else:
        apply_precision = None

    apply_coverage = round(apply_total / total, 4) if total > 0 else 0.0

    summary = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {
            "retrieval_mode": retrieval_mode,
            "top_k": top_k,
            "evidence_per_lecture": args.evidence_per_lecture,
            "confidence_threshold": threshold,
            "apply_margin": margin_delta,
            "run_classifier": args.run_classifier,
            "parent_enabled": os.environ.get("PARENT_ENABLED", "0"),
            "trgm_enabled": os.environ.get("SEARCH_PG_TRGM_ENABLED", "0"),
            "lecture_agg_mode": getattr(args, 'lecture_agg_mode', 'sum') or 'sum',
            "lecture_topm": getattr(args, 'lecture_topm', 3) or 3,
            "lecture_chunk_cap": getattr(args, 'lecture_chunk_cap', 0) or 0,
        },
        "total_questions": total,
        "metrics": {
            "judge_given_hit_total": judge_given_hit_total,
            "judge_given_hit_correct": judge_given_hit_correct,
            "judge_accuracy_given_hit": judge_accuracy_given_hit,
            "apply_total": apply_total,
            "apply_correct": apply_correct,
            "apply_incorrect": apply_incorrect,
            "apply_precision": apply_precision,
            "apply_coverage": apply_coverage,
            "no_match_count": no_match_count,
            "retrieval_no_candidate": retrieval_no_candidate,
            "retrieval_gold_not_in_topk": retrieval_gold_not_in_topk,
        },
        "error_counts": {
            "retrieval_miss": len(errors_retrieval_miss),
            "judge_miss": len(errors_judge_miss),
        },
        "fp_top_lectures": dict(sorted(
            fp_lecture_counter.items(), key=lambda x: -x[1]
        )[:10]),
        "dominance": _compute_dominance(fp_lecture_counter, retrieval_gold_not_in_topk),
        "latency": {
            "retrieve_mean_ms": round(_mean(retrieve_latencies), 2),
            "retrieve_p50_ms": round(_percentile(retrieve_latencies, 50), 2),
            "retrieve_p95_ms": round(_percentile(retrieve_latencies, 95), 2),
            "judge_mean_ms": round(_mean(judge_latencies), 2),
            "judge_p50_ms": round(_percentile(judge_latencies, 50), 2),
            "judge_p95_ms": round(_percentile(judge_latencies, 95), 2),
            "total_mean_ms": round(_mean(total_latencies), 2),
            "total_p95_ms": round(_percentile(total_latencies, 95), 2),
        },
        "llm_calls": {
            "total": sum(1 for r in records if not r.get("from_cache", False) and r.get("judge_latency_ms", 0) > 0),
            "cached": sum(1 for r in records if r.get("from_cache", False)),
            "total_retries": sum(retry_counts),
        },
    }
    # Merge recall into metrics
    summary["metrics"].update(recall_rates)
    summary["metrics"].update(recall_counts_dict)

    # Write summary
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Wrote summary to {summary_path}")

    # ---- Error report (top 50) ----
    _write_error_report(
        output_dir / "errors_top50.md",
        errors_retrieval_miss[:25],
        errors_judge_miss[:25],
        summary,
    )

    # ---- Human-readable baseline report ----
    _write_baseline_report(output_dir / "baseline_run.md", summary)

    # ---- Dominance report ----
    _write_dominance_report(output_dir / "dominance_report.md", summary)

    return summary


# ---------------------------------------------------------------------------
# Dominance metrics (P2-3)
# ---------------------------------------------------------------------------


def _compute_dominance(fp_lecture_counter: Dict, total_misses: int) -> Dict:
    """Compute lecture FP dominance metrics for summary.json."""
    if total_misses == 0 or not fp_lecture_counter:
        return {
            "total_misses": total_misses,
            "dominance_top1_share": 0.0,
            "dominance_top1_lecture": None,
            "dominance_top3_share": 0.0,
        }

    sorted_fps = sorted(fp_lecture_counter.items(), key=lambda x: -x[1])

    top1_lid, top1_cnt = sorted_fps[0]
    top3_cnt = sum(cnt for _, cnt in sorted_fps[:3])

    # Get mega-lecture stats
    top1_mass = _get_lecture_mass(top1_lid)

    return {
        "total_misses": total_misses,
        "dominance_top1_share": round(top1_cnt / total_misses, 4),
        "dominance_top1_lecture": {
            "id": top1_lid,
            "fp_count": top1_cnt,
            **top1_mass,
        },
        "dominance_top3_share": round(top3_cnt / total_misses, 4),
    }


def _get_lecture_mass(lecture_id: int) -> Dict:
    """Get chunk count and total chars for a lecture."""
    try:
        from sqlalchemy import text as sa_text
        result = db.session.execute(sa_text("""
            SELECT COUNT(*) AS chunk_count,
                   COALESCE(SUM(LENGTH(content)), 0) AS total_chars
            FROM lecture_chunks WHERE lecture_id = :lid
        """), {"lid": lecture_id}).mappings().first()
        if result:
            return {"chunk_count": result["chunk_count"], "total_chars": result["total_chars"]}
    except Exception:
        pass
    return {"chunk_count": 0, "total_chars": 0}


def _write_dominance_report(path: Path, summary: Dict):
    """Write dominance_report.md per run."""
    dom = summary.get("dominance", {})
    lines = []
    lines.append("# Dominance Report")
    lines.append("")
    lines.append(f"Generated: {summary.get('generated_at', '')}")
    lines.append("")
    lines.append("## Dominance Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| total_misses | {dom.get('total_misses', 0)} |")
    lines.append(f"| dominance_top1_share | {dom.get('dominance_top1_share', 0):.4f} |")
    lines.append(f"| dominance_top3_share | {dom.get('dominance_top3_share', 0):.4f} |")
    lines.append("")

    top1 = dom.get("dominance_top1_lecture")
    if top1:
        lines.append("## Top FP Lecture (Mega-Lecture)")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| lecture_id | {top1.get('id')} |")
        lines.append(f"| fp_count | {top1.get('fp_count')} |")
        lines.append(f"| chunk_count | {top1.get('chunk_count', '?')} |")
        lines.append(f"| total_chars | {top1.get('total_chars', '?')} |")
        lines.append("")

    # FP frequency table
    fp_lectures = summary.get("fp_top_lectures", {})
    if fp_lectures:
        lines.append("## FP Lecture Frequency")
        lines.append("")
        lines.append("| Lecture ID | FP Count |")
        lines.append("|---|---|")
        for lid, cnt in sorted(fp_lectures.items(), key=lambda x: -x[1]):
            lines.append(f"| {lid} | {cnt} |")
        lines.append("")

    # Config context
    cfg = summary.get("config", {})
    lines.append("## Config Context")
    lines.append("")
    lines.append(f"- agg_mode: {cfg.get('lecture_agg_mode', 'sum')}")
    lines.append(f"- topm: {cfg.get('lecture_topm', 3)}")
    lines.append(f"- chunk_cap: {cfg.get('lecture_chunk_cap', 0)}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote dominance report to {path}")


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def _write_error_report(
    path: Path,
    retrieval_misses: List[Dict],
    judge_misses: List[Dict],
    summary: Dict,
):
    lines = []
    lines.append("# Error Analysis (Top 50)")
    lines.append("")
    lines.append("Generated: " + summary["generated_at"])
    lines.append("")
    lines.append("- Retrieval misses: " + str(summary["error_counts"]["retrieval_miss"]))
    lines.append("- Judge misses: " + str(summary["error_counts"]["judge_miss"]))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Retrieval Misses (gold not in candidates)")
    lines.append("")

    for err in retrieval_misses:
        lines.append("### Q" + str(err["question_id"]))
        lines.append("- **Gold**: lecture " + str(err["gold_lecture_id"]) + " - " + err["gold_lecture_title"])
        lines.append("- **Predicted**: " + str(err["predicted_lecture_id"]))
        lines.append("- **Top-3 candidates:**")
        for c in err.get("candidates_top3", []):
            lines.append("  - rank " + str(c["rank"]) + ": lecture " + str(c["lecture_id"]) + " (" + c["full_path"] + ") score=" + str(c["score"]))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Judge Misses (gold in candidates, LLM chose wrong)")
    lines.append("")

    for err in judge_misses:
        lines.append("### Q" + str(err["question_id"]))
        lines.append("- **Gold**: lecture " + str(err["gold_lecture_id"]) + " - " + err["gold_lecture_title"] + " (rank " + str(err["gold_rank"]) + ")")
        lines.append("- **Predicted**: lecture " + str(err["predicted_lecture_id"]) + " (conf=" + f"{err['llm_confidence']:.3f}" + ")")
        lines.append("- **Reason**: " + err.get("llm_reason", ""))
        lines.append("- **Top-3 candidates:**")
        for c in err.get("candidates_top3", []):
            lines.append("  - rank " + str(c["rank"]) + ": lecture " + str(c["lecture_id"]) + " (" + c["full_path"] + ") score=" + str(c["score"]))
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote error report to {path}")


def _write_baseline_report(path: Path, summary: Dict):
    m = summary["metrics"]
    lat = summary["latency"]
    llm = summary["llm_calls"]
    cfg = summary["config"]

    ja_val = m["judge_accuracy_given_hit"]
    ja_str = "N/A" if ja_val is None else str(ja_val)
    ap_val = m["apply_precision"]
    ap_str = "N/A" if ap_val is None else str(ap_val)

    run_flag = "--run-classifier " if cfg["run_classifier"] else ""
    reproduce_cmd = (
        "python scripts/eval_classifier_run.py "
        + "--question-ids-file evalset_question_ids.txt "
        + run_flag
        + "--top-k " + str(cfg["top_k"]) + " "
        + "--evidence-per-lecture " + str(cfg["evidence_per_lecture"]) + " "
        + "--output-dir " + str(path.parent)
    )

    lines = []
    lines.append("# Baseline Run Report")
    lines.append("")
    lines.append("Generated: " + summary["generated_at"])
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("| Parameter | Value |")
    lines.append("|---|---|")
    lines.append("| Retrieval Mode | " + str(cfg["retrieval_mode"]) + " |")
    lines.append("| Top-K Lectures | " + str(cfg["top_k"]) + " |")
    lines.append("| Evidence/Lecture | " + str(cfg["evidence_per_lecture"]) + " |")
    lines.append("| Confidence Threshold | " + str(cfg["confidence_threshold"]) + " |")
    lines.append("| Apply Margin | " + str(cfg["apply_margin"]) + " |")
    lines.append("| PARENT_ENABLED | " + str(cfg["parent_enabled"]) + " |")
    lines.append("| TRGM_ENABLED | " + str(cfg["trgm_enabled"]) + " |")
    lines.append("| Run Classifier | " + str(cfg["run_classifier"]) + " |")
    lines.append("")
    lines.append("**Total questions**: " + str(summary["total_questions"]))
    lines.append("")
    lines.append("## Retrieval Metrics")
    lines.append("")
    lines.append("| Metric | Rate | Count |")
    lines.append("|---|---|---|")

    for k in [1, 3, 5, 8, 10, 12, 16]:
        rate_key = "recall@" + str(k)
        count_key = rate_key + "_count"
        if rate_key in m:
            lines.append("| Recall@" + str(k) + " | " + f"{m[rate_key]:.4f}" + " | " + str(m[count_key]) + " |")

    lines.append("")
    lines.append("## Classification Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append("| Judge Accuracy (Given-hit) | " + ja_str + " (" + str(m["judge_given_hit_correct"]) + "/" + str(m["judge_given_hit_total"]) + ") |")
    lines.append("| Apply Precision | " + ap_str + " (" + str(m["apply_correct"]) + "/" + str(m["apply_total"]) + ") |")
    lines.append("| Apply Coverage | " + f"{m['apply_coverage']:.4f}" + " (" + str(m["apply_total"]) + "/" + str(summary["total_questions"]) + ") |")
    lines.append("| no_match count | " + str(m["no_match_count"]) + " |")

    lines.append("")
    lines.append("## Error Decomposition")
    lines.append("")
    lines.append("| Error Type | Count | Description |")
    lines.append("|---|---|---|")
    lines.append("| retrieval_no_candidate | " + str(m.get("retrieval_no_candidate", 0)) + " | 후보 0개 (BM25 결과 없음) |")
    lines.append("| retrieval_gold_not_in_topk | " + str(m.get("retrieval_gold_not_in_topk", 0)) + " | 후보 있으나 gold가 topK에 없음 |")
    lines.append("| Retrieval Miss (total) | " + str(summary["error_counts"]["retrieval_miss"]) + " | LLM이 gold를 선택 불가 |")
    lines.append("| Judge Miss | " + str(summary["error_counts"]["judge_miss"]) + " | gold가 후보에 있으나 LLM이 오답 |")

    lines.append("")
    lines.append("## Latency Breakdown")
    lines.append("")
    lines.append("| Stage | Mean | p50 | p95 |")
    lines.append("|---|---|---|---|")
    lines.append("| Retrieve | " + f"{lat['retrieve_mean_ms']:.1f}" + "ms | " + f"{lat['retrieve_p50_ms']:.1f}" + "ms | " + f"{lat['retrieve_p95_ms']:.1f}" + "ms |")
    lines.append("| Judge | " + f"{lat['judge_mean_ms']:.1f}" + "ms | " + f"{lat['judge_p50_ms']:.1f}" + "ms | " + f"{lat['judge_p95_ms']:.1f}" + "ms |")
    lines.append("| Total | " + f"{lat['total_mean_ms']:.1f}" + "ms | - | " + f"{lat['total_p95_ms']:.1f}" + "ms |")

    lines.append("")
    lines.append("## LLM Calls")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append("| Live calls | " + str(llm["total"]) + " |")
    lines.append("| Cached | " + str(llm["cached"]) + " |")
    lines.append("| Total retries | " + str(llm["total_retries"]) + " |")

    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /home/gyu/learn/exam_manager")
    lines.append(reproduce_cmd)
    lines.append("```")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print("  Wrote baseline report to " + str(path))


# ---------------------------------------------------------------------------
# Sweep runner
# ---------------------------------------------------------------------------


def run_sweep(app, args):
    """Run parameter sweeps and produce comparison tables."""

    top_k_values = [int(v) for v in (args.top_k_sweep or "").split(",") if v.strip()] or [args.top_k]
    evidence_values = [int(v) for v in (args.evidence_sweep or "").split(",") if v.strip()] or [args.evidence_per_lecture]

    sweep_dir = Path(args.output_dir)
    sweep_dir.mkdir(parents=True, exist_ok=True)

    all_summaries = []

    for tk in top_k_values:
        for ev in evidence_values:
            label = "k" + str(tk) + "_ev" + str(ev)
            print("\n=== Sweep: top_k=" + str(tk) + ", evidence_per_lecture=" + str(ev) + " ===")

            sweep_args = copy.copy(args)
            sweep_args.top_k = tk
            sweep_args.evidence_per_lecture = ev
            sweep_args.output_dir = str(sweep_dir / label)

            summary = run_evaluation(app, sweep_args)
            summary["sweep_label"] = label
            summary["sweep_top_k"] = tk
            summary["sweep_evidence_per_lecture"] = ev
            all_summaries.append(summary)

    # Write comparison table
    _write_sweep_comparison(sweep_dir / "sweep_comparison.md", all_summaries)

    return all_summaries


def _write_sweep_comparison(path: Path, summaries: List[Dict]):
    lines = []
    lines.append("# Parameter Sweep Comparison")
    lines.append("")
    lines.append("Generated: " + datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    lines.append("")
    lines.append("## Retrieval Recall")
    lines.append("")
    lines.append("| Config | Recall@1 | Recall@3 | Recall@5 | Recall@8 | Recall@10 | Recall@16 | Ret p95 |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for s in summaries:
        m = s["metrics"]
        lat = s["latency"]
        row = "| " + s["sweep_label"]
        for k in [1, 3, 5, 8, 10, 16]:
            key = "recall@" + str(k)
            row += " | " + f"{m.get(key, 0):.4f}"
        row += " | " + f"{lat['retrieve_p95_ms']:.1f}ms |"
        lines.append(row)

    lines.append("")
    lines.append("## Classification Metrics")
    lines.append("")
    lines.append("| Config | Judge Acc (Hit) | Apply Precision | Apply Coverage | no_match | Judge p95 |")
    lines.append("|---|---|---|---|---|---|")

    for s in summaries:
        m = s["metrics"]
        lat = s["latency"]
        ja = m.get("judge_accuracy_given_hit")
        ap = m.get("apply_precision")
        row = "| " + s["sweep_label"]
        row += " | " + (str(ja) if ja is not None else "N/A")
        row += " | " + (str(ap) if ap is not None else "N/A")
        row += " | " + f"{m.get('apply_coverage', 0):.4f}"
        row += " | " + str(m.get("no_match_count", 0))
        row += " | " + f"{lat['judge_p95_ms']:.1f}ms |"
        lines.append(row)

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print("\n  Wrote sweep comparison to " + str(path))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced classification pipeline evaluation."
    )
    parser.add_argument("--output-dir", default="reports/baseline", help="Output directory.")
    parser.add_argument("--question-ids-file", default=None, help="Restrict to question IDs.")
    parser.add_argument("--retrieval-mode", default=None, help="bm25 only.")
    parser.add_argument("--top-k", type=int, default=8, help="Top-K lectures.")
    parser.add_argument("--evidence-per-lecture", type=int, default=3, help="Evidence snippets per lecture.")
    parser.add_argument("--confidence-threshold", type=float, default=0.7, help="Apply threshold.")
    parser.add_argument("--apply-margin", type=float, default=0.2, help="Apply margin delta.")
    parser.add_argument("--include-ambiguous", action="store_true")
    parser.add_argument("--labels-source", default=None, help="Filter evaluation_labels by source (e.g. gold_physio1).")
    parser.add_argument("--limit", type=int, default=None, help="Limit eval count.")

    # Scope filter
    parser.add_argument("--scope-block-id", type=int, default=None,
                        help="Restrict retrieval candidates to lectures in this block_id.")

    # Lecture aggregation (P2)
    parser.add_argument("--lecture-agg-mode", default=None,
                        help="Lecture score aggregation: sum or topm_mean.")
    parser.add_argument("--lecture-topm", type=int, default=None,
                        help="Top-m chunks for topm_mean aggregation.")
    parser.add_argument("--lecture-chunk-cap", type=int, default=None,
                        help="Per-lecture chunk cap (0=disabled).")

    # Classification
    parser.add_argument("--run-classifier", action="store_true", help="Run live LLM calls.")
    parser.add_argument("--max-workers", type=int, default=4, help="Concurrent workers.")
    parser.add_argument("--no-cache", action="store_true", help="Skip classifier cache.")

    # Sweep
    parser.add_argument("--top-k-sweep", default=None, help="Comma-separated top-k values for sweep.")
    parser.add_argument("--evidence-sweep", default=None, help="Comma-separated evidence counts for sweep.")

    parser.add_argument("--db", default=None, help="DATABASE_URL override.")

    args = parser.parse_args()

    config_name = os.environ.get("FLASK_CONFIG") or "default"
    db_url = args.db or os.environ.get("DATABASE_URL")
    app = create_app(config_name, db_uri_override=db_url, skip_migration_check=True)

    # Resolve scope-block-id to lecture_ids list
    if args.scope_block_id is not None:
        with app.app_context():
            scope_lectures = Lecture.query.filter_by(block_id=args.scope_block_id).all()
            args._resolved_scope_lecture_ids = [l.id for l in scope_lectures]
            block = Block.query.get(args.scope_block_id)
            block_name = block.name if block else f"block_{args.scope_block_id}"
            print(f"[scope] Filtering retrieval to block '{block_name}': "
                  f"{len(args._resolved_scope_lecture_ids)} lectures {args._resolved_scope_lecture_ids}")
    else:
        args._resolved_scope_lecture_ids = None

    if args.top_k_sweep or args.evidence_sweep:
        run_sweep(app, args)
    else:
        run_evaluation(app, args)


if __name__ == "__main__":
    main()
