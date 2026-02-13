#!/usr/bin/env python3
"""
Reproducible local p95 benchmark for search/classification/manage hot paths.

This benchmark intentionally runs on SQLite so it can execute in constrained
local environments where Postgres runtime metrics are unavailable.
It compares:
  - Baseline (pre-optimization logic copied in this script)
  - Current optimized service code in app/services/*
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from flask import current_app
from sqlalchemy import case, event, func

ROOT_DIR = Path(__file__).resolve().parents[1]
import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import create_app, db
from app.models import (
    Block,
    ClassificationJob,
    Lecture,
    LectureChunk,
    LectureMaterial,
    PreviousExam,
    Question,
    QuestionChunkMatch,
    User,
)
from app.services import manage_service, retrieval
from app.services.ai_classifier import (
    apply_classification_results,
    build_job_payload,
    parse_job_payload,
)
from app.services.user_scope import scope_model, scope_query
from config import get_config


def _create_sqlite_app(db_path: Path):
    db_uri = f"sqlite:///{db_path}"
    app = create_app("default", db_uri_override=db_uri, skip_migration_check=True)
    app.config["TESTING"] = True
    return app


@contextmanager
def _query_counter():
    count = {"value": 0}

    def _before_cursor_execute(*_args, **_kwargs):
        count["value"] += 1

    event.listen(db.engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield count
    finally:
        event.remove(db.engine, "before_cursor_execute", _before_cursor_execute)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * (p / 100.0)
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    frac = idx - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * frac


def _summarize(times_ms: list[float], query_counts: list[int]) -> dict[str, float]:
    return {
        "mean_ms": round(sum(times_ms) / len(times_ms), 2) if times_ms else 0.0,
        "p50_ms": round(_percentile(times_ms, 50), 2),
        "p95_ms": round(_percentile(times_ms, 95), 2),
        "queries_mean": round(sum(query_counts) / len(query_counts), 2)
        if query_counts
        else 0.0,
        "queries_p95": round(_percentile([float(v) for v in query_counts], 95), 2)
        if query_counts
        else 0.0,
    }


def _measure_calls(fn: Callable[[], Any], iterations: int) -> dict[str, float]:
    times_ms: list[float] = []
    query_counts: list[int] = []
    for _ in range(iterations):
        with _query_counter() as qc:
            t0 = time.perf_counter()
            fn()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
        times_ms.append(elapsed_ms)
        query_counts.append(int(qc["value"]))
    return _summarize(times_ms, query_counts)


# ---------------------------------------------------------------------------
# Baseline snapshots (pre-optimization logic)
# ---------------------------------------------------------------------------


def baseline_get_dashboard_stats(user) -> dict:
    block_query = scope_model(Block, user, include_public=True)
    lecture_query = scope_model(Lecture, user, include_public=True)
    exam_query = scope_model(PreviousExam, user)
    question_query = scope_model(Question, user)
    recent_exams = exam_query.order_by(PreviousExam.created_at.desc()).limit(5).all()
    exam_ids = [exam.id for exam in recent_exams]
    exam_counts = {}
    if exam_ids:
        rows = (
            scope_query(Question.query, Question, user)
            .with_entities(
                Question.exam_id,
                func.count(Question.id),
                func.sum(case((Question.is_classified.is_(True), 1), else_=0)),
            )
            .filter(Question.exam_id.in_(exam_ids))
            .group_by(Question.exam_id)
            .all()
        )
        for exam_id, total, classified in rows:
            total_count = int(total or 0)
            classified_count = int(classified or 0)
            exam_counts[exam_id] = {
                "total": total_count,
                "unclassified": max(total_count - classified_count, 0),
            }
    return {
        "block_count": block_query.count(),
        "lecture_count": lecture_query.count(),
        "exam_count": exam_query.count(),
        "question_count": question_query.count(),
        "unclassified_count": question_query.filter_by(is_classified=False).count(),
        "recent_exams": [
            {
                "id": e.id,
                "title": e.title,
                "subject": e.subject,
                "year": e.year,
                "term": e.term,
                "question_count": exam_counts.get(e.id, {}).get("total", 0),
                "unclassified_count": exam_counts.get(e.id, {}).get("unclassified", 0),
            }
            for e in recent_exams
        ],
    }


def _baseline_chunk_relevance(chunk: dict) -> float:
    if chunk.get("rrf_score") is not None:
        return float(chunk.get("rrf_score") or 0.0)
    if chunk.get("embedding_score") is not None:
        return float(chunk.get("embedding_score") or 0.0)
    if chunk.get("bm25_score") is not None:
        return float(chunk.get("bm25_score") or 0.0)
    return 0.0


def baseline_aggregate_candidates(
    chunks: list[dict],
    top_k_lectures: int = 8,
    evidence_per_lecture: int = 3,
    *,
    agg_mode: str = "sum",
    topm: int = 3,
    chunk_cap: int = 0,
) -> list[dict]:
    if not chunks:
        return []
    if chunk_cap > 0:
        capped: list[dict] = []
        per_lec_count: dict[int, int] = {}
        for chunk in chunks:
            lid = chunk.get("lecture_id")
            if lid is None:
                continue
            per_lec_count[lid] = per_lec_count.get(lid, 0) + 1
            if per_lec_count[lid] <= chunk_cap:
                capped.append(chunk)
        chunks = capped

    per_lecture: dict[int, dict[str, Any]] = {}
    for chunk in chunks:
        lecture_id = chunk.get("lecture_id")
        if lecture_id is None:
            continue
        score = _baseline_chunk_relevance(chunk)
        entry = per_lecture.setdefault(lecture_id, {"scores": [], "evidence": []})
        entry["scores"].append(score)
        entry["evidence"].append(
            {
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "snippet": chunk.get("snippet") or "",
                "chunk_id": chunk.get("chunk_id"),
                "score": score,
            }
        )

    for info in per_lecture.values():
        scores = info["scores"]
        if agg_mode == "topm_mean" and scores:
            top_scores = sorted(scores, reverse=True)[:topm]
            info["score"] = sum(top_scores) / len(top_scores)
        else:
            info["score"] = sum(scores)

    lecture_ids = list(per_lecture.keys())
    lecture_rows = (
        Lecture.query.join(Block).filter(Lecture.id.in_(lecture_ids)).all()
        if lecture_ids
        else []
    )
    lecture_map = {lecture.id: lecture for lecture in lecture_rows}

    candidates = []
    for lecture_id, info in per_lecture.items():
        lecture = lecture_map.get(lecture_id)
        if not lecture:
            continue
        evidence = sorted(info["evidence"], key=lambda e: e["score"], reverse=True)[
            :evidence_per_lecture
        ]
        candidates.append(
            {
                "id": lecture.id,
                "title": lecture.title,
                "block_name": lecture.block.name if lecture.block else "",
                "full_path": f"{lecture.block.name} > {lecture.title}"
                if lecture.block
                else lecture.title,
                "score": info["score"],
                "evidence": [
                    {
                        "page_start": e["page_start"],
                        "page_end": e["page_end"],
                        "snippet": e["snippet"],
                        "chunk_id": e["chunk_id"],
                    }
                    for e in evidence
                ],
            }
        )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_k_lectures]


def baseline_apply_classification_results(
    question_ids: list[int],
    job_id: int,
    apply_mode: str = "all",
) -> int:
    job = db.session.get(ClassificationJob, job_id)
    if not job or not job.result_json:
        return 0
    _, results = parse_job_payload(job.result_json)
    if not results:
        return 0

    results_map = {
        r.get("question_id"): r for r in results if r.get("question_id") is not None
    }

    auto_apply = bool(current_app.config.get("AI_AUTO_APPLY", False))
    threshold = float(current_app.config.get("AI_CONFIDENCE_THRESHOLD", 0.7))
    margin = float(current_app.config.get("AI_AUTO_APPLY_MARGIN", 0.2))
    auto_apply_min = threshold + margin
    hard_action = "needs_review"
    require_page_span = bool(get_config().experiment.classifier_require_page_span)

    applied_count = 0
    for qid in question_ids:
        result = results_map.get(qid)
        if not result:
            continue
        question = db.session.get(Question, qid)
        if not question:
            continue

        lecture_id = result.get("lecture_id")
        candidate_ids = result.get("candidate_ids") or []
        out_of_candidates = (
            lecture_id is not None
            and bool(candidate_ids)
            and lecture_id not in candidate_ids
        )
        no_match = bool(result.get("no_match", False))
        decision_mode = str(
            result.get("decision_mode") or ("no_match" if no_match else "strict_match")
        ).strip().lower()
        is_weak_match = decision_mode == "weak_match"
        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        lecture = db.session.get(Lecture, lecture_id) if lecture_id else None
        if lecture and not no_match:
            question.ai_suggested_lecture_id = lecture.id
            question.ai_suggested_lecture_title_snapshot = (
                f"{lecture.block.name} > {lecture.title}"
            )
            if not question.is_classified:
                question.classification_status = "ai_suggested"
        else:
            question.ai_suggested_lecture_id = None
            question.ai_suggested_lecture_title_snapshot = None
            if not question.is_classified:
                question.classification_status = "manual"

        question.ai_confidence = confidence
        question.ai_reason = result.get("reason", "") or ""
        question.ai_model_name = result.get("model_name", "") or ""
        question.ai_classified_at = datetime.utcnow()

        final_lecture_id = lecture_id
        if out_of_candidates:
            if hard_action == "clamp_top1" and candidate_ids:
                final_lecture_id = candidate_ids[0]
            else:
                final_lecture_id = None
            question.classification_status = "needs_review"
        question.ai_final_lecture_id = final_lecture_id

        QuestionChunkMatch.query.filter_by(question_id=question.id).delete(
            synchronize_session=False
        )
        evidence_list = result.get("evidence") or []
        if isinstance(evidence_list, list) and evidence_list:
            chunk_ids = []
            for evidence in evidence_list:
                raw_chunk_id = evidence.get("chunk_id")
                if raw_chunk_id in (None, ""):
                    continue
                try:
                    chunk_ids.append(int(raw_chunk_id))
                except (TypeError, ValueError):
                    continue
            chunk_map = {}
            if chunk_ids:
                chunk_rows = LectureChunk.query.filter(LectureChunk.id.in_(chunk_ids)).all()
                chunk_map = {row.id: row for row in chunk_rows}

            matches: list[QuestionChunkMatch] = []
            seen_match_keys: set[tuple[int, int, str]] = set()
            for evidence in evidence_list:
                raw_chunk_id = evidence.get("chunk_id")
                if raw_chunk_id in (None, ""):
                    continue
                try:
                    chunk_id = int(raw_chunk_id)
                except (TypeError, ValueError):
                    continue
                chunk = chunk_map.get(chunk_id)
                if not chunk:
                    continue

                evidence_lecture_id = (
                    evidence.get("lecture_id")
                    or (lecture.id if lecture else None)
                    or (chunk.lecture_id if chunk else None)
                )
                if not evidence_lecture_id:
                    continue

                snippet = (
                    evidence.get("quote")
                    or evidence.get("snippet")
                    or (chunk.content if chunk else "")
                )
                snippet = (snippet or "").strip()
                if len(snippet) > 500:
                    snippet = snippet[:497] + "..."

                page_start = evidence.get("page_start") or chunk.page_start
                page_end = evidence.get("page_end") or chunk.page_end
                if require_page_span and (page_start is None or page_end is None):
                    continue

                source = "ai"
                match_key = (question.id, chunk_id, source)
                if match_key in seen_match_keys:
                    continue
                seen_match_keys.add(match_key)

                matches.append(
                    QuestionChunkMatch(
                        question_id=question.id,
                        lecture_id=evidence_lecture_id,
                        chunk_id=chunk_id,
                        material_id=chunk.material_id,
                        page_start=page_start,
                        page_end=page_end,
                        snippet=snippet,
                        score=evidence.get("score") or confidence,
                        source=source,
                        job_id=job_id,
                        is_primary=(len(matches) == 0),
                    )
                )
            if matches:
                db.session.add_all(matches)

        if out_of_candidates:
            continue

        force_apply = apply_mode == "all"
        is_pass = (
            (force_apply or auto_apply)
            and final_lecture_id
            and (not no_match)
            and (force_apply or not is_weak_match)
            and (force_apply or confidence >= auto_apply_min)
        )
        if is_pass:
            final_lecture = db.session.get(Lecture, final_lecture_id)
            if not final_lecture:
                continue
            question.lecture_id = final_lecture.id
            question.is_classified = True
            question.classification_status = "ai_confirmed"
            applied_count += 1

    db.session.commit()
    return applied_count


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def seed_manage_db(db_path: Path) -> int:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = User(email="bench-manage@example.com", is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.flush()

        blocks = [
            Block(
                name=f"Block {i}",
                subject="Subject A",
                order=i,
                user_id=user.id,
            )
            for i in range(60)
        ]
        db.session.add_all(blocks)
        db.session.flush()

        lectures = [
            Lecture(
                block_id=blocks[i % len(blocks)].id,
                title=f"Lecture {i}",
                order=i,
                user_id=user.id,
            )
            for i in range(360)
        ]
        db.session.add_all(lectures)
        db.session.flush()

        now = datetime.utcnow()
        exams = [
            PreviousExam(
                title=f"Exam {i}",
                subject="Subject A",
                year=2020 + (i % 5),
                term=f"T{i % 2 + 1}",
                user_id=user.id,
                created_at=now - timedelta(days=i),
            )
            for i in range(120)
        ]
        db.session.add_all(exams)
        db.session.flush()

        questions: list[Question] = []
        for exam in exams:
            for qnum in range(1, 61):
                questions.append(
                    Question(
                        exam_id=exam.id,
                        user_id=user.id,
                        question_number=qnum,
                        is_classified=(qnum % 4 != 0),
                        classification_status="manual",
                        q_type=Question.TYPE_MULTIPLE_CHOICE,
                        content=f"Question {exam.id}-{qnum}",
                    )
                )
        db.session.add_all(questions)
        db.session.commit()
        user_id = int(user.id)
    return user_id


def seed_search_db(db_path: Path) -> None:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = User(email="bench-search@example.com", is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.flush()

        blocks = [
            Block(name=f"SBlock {i}", subject="Search", order=i, user_id=user.id)
            for i in range(50)
        ]
        db.session.add_all(blocks)
        db.session.flush()

        lectures = [
            Lecture(
                block_id=blocks[i % len(blocks)].id,
                title=f"SLecture {i}",
                order=i,
                user_id=user.id,
            )
            for i in range(450)
        ]
        db.session.add_all(lectures)
        db.session.commit()


def seed_classification_db(db_path: Path) -> tuple[list[int], int]:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = User(email="bench-classify@example.com", is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.flush()

        blocks = [
            Block(name=f"CBlock {i}", subject="Classify", order=i, user_id=user.id)
            for i in range(25)
        ]
        db.session.add_all(blocks)
        db.session.flush()

        lectures = [
            Lecture(
                block_id=blocks[i % len(blocks)].id,
                title=f"CLecture {i}",
                order=i,
                user_id=user.id,
            )
            for i in range(180)
        ]
        db.session.add_all(lectures)
        db.session.flush()

        materials = [
            LectureMaterial(
                lecture_id=lecture.id,
                file_path=f"/tmp/material_{lecture.id}.pdf",
                original_filename=f"material_{lecture.id}.pdf",
            )
            for lecture in lectures
        ]
        db.session.add_all(materials)
        db.session.flush()
        material_by_lecture = {m.lecture_id: m for m in materials}

        chunks: list[LectureChunk] = []
        for lecture in lectures:
            material = material_by_lecture[lecture.id]
            for page in range(1, 7):
                chunks.append(
                    LectureChunk(
                        lecture_id=lecture.id,
                        material_id=material.id,
                        page_start=page,
                        page_end=page,
                        content=f"Lecture {lecture.id} content page {page}",
                        char_len=120,
                    )
                )
        db.session.add_all(chunks)
        db.session.flush()

        chunk_ids_by_lecture: dict[int, list[int]] = {}
        for chunk in chunks:
            chunk_ids_by_lecture.setdefault(chunk.lecture_id, []).append(chunk.id)

        exam = PreviousExam(
            title="Classification Bench Exam",
            subject="Classify",
            year=2025,
            term="T1",
            user_id=user.id,
        )
        db.session.add(exam)
        db.session.flush()

        questions = [
            Question(
                exam_id=exam.id,
                user_id=user.id,
                question_number=i + 1,
                is_classified=False,
                classification_status="manual",
                q_type=Question.TYPE_MULTIPLE_CHOICE,
                content=f"Classification question {i + 1}",
            )
            for i in range(420)
        ]
        db.session.add_all(questions)
        db.session.flush()

        results = []
        for idx, question in enumerate(questions):
            lecture = lectures[idx % len(lectures)]
            next_lecture = lectures[(idx + 1) % len(lectures)]
            third_lecture = lectures[(idx + 2) % len(lectures)]
            chunk_ids = chunk_ids_by_lecture[lecture.id][:3]
            results.append(
                {
                    "question_id": question.id,
                    "lecture_id": lecture.id,
                    "candidate_ids": [lecture.id, next_lecture.id, third_lecture.id],
                    "confidence": 0.91,
                    "reason": "benchmark",
                    "model_name": "bench-model",
                    "no_match": False,
                    "decision_mode": "strict_match",
                    "evidence": [
                        {
                            "lecture_id": lecture.id,
                            "chunk_id": chunk_id,
                            "page_start": 1,
                            "page_end": 1,
                            "quote": f"evidence-{chunk_id}",
                            "score": 0.91,
                        }
                        for chunk_id in chunk_ids
                    ],
                }
            )

        for idx, question in enumerate(questions):
            lecture = lectures[idx % len(lectures)]
            chunk_id = chunk_ids_by_lecture[lecture.id][0]
            chunk = db.session.get(LectureChunk, chunk_id)
            db.session.add(
                QuestionChunkMatch(
                    question_id=question.id,
                    lecture_id=lecture.id,
                    chunk_id=chunk_id,
                    material_id=chunk.material_id if chunk else None,
                    page_start=1,
                    page_end=1,
                    snippet="old evidence",
                    score=0.1,
                    source="ai",
                    is_primary=True,
                )
            )

        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=len(questions),
            processed_count=len(questions),
            success_count=len(questions),
            failed_count=0,
        )
        job.result_json = json.dumps(build_job_payload({}, results), ensure_ascii=False)
        db.session.add(job)
        db.session.commit()

        question_ids = [int(q.id) for q in questions]
        job_id = int(job.id)
    return question_ids, job_id


# ---------------------------------------------------------------------------
# Bench runners
# ---------------------------------------------------------------------------


def run_manage_benchmark(db_path: Path, user_id: int, iterations: int) -> dict[str, dict]:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        user = db.session.get(User, user_id)
        if not user:
            raise RuntimeError("manage benchmark user missing")
        baseline = _measure_calls(lambda: baseline_get_dashboard_stats(user), iterations)
        optimized = _measure_calls(lambda: manage_service.get_dashboard_stats(user), iterations)
    return {"before": baseline, "after": optimized}


def run_search_benchmark(db_path: Path, iterations: int) -> dict[str, dict]:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        lecture_ids = [
            int(row[0]) for row in db.session.query(Lecture.id).order_by(Lecture.id).all()
        ]
        rng = random.Random(42)
        chunks = []
        for idx in range(7000):
            lecture_id = lecture_ids[idx % len(lecture_ids)]
            score = 10.0 - (idx / 9000.0) + rng.random() * 0.001
            chunks.append(
                {
                    "chunk_id": idx + 1,
                    "lecture_id": lecture_id,
                    "page_start": (idx % 12) + 1,
                    "page_end": (idx % 12) + 1,
                    "snippet": f"Chunk snippet {idx}",
                    "bm25_score": score,
                }
            )

        baseline = _measure_calls(
            lambda: baseline_aggregate_candidates(
                chunks, top_k_lectures=8, evidence_per_lecture=3
            ),
            iterations,
        )
        optimized = _measure_calls(
            lambda: retrieval.aggregate_candidates(
                chunks, top_k_lectures=8, evidence_per_lecture=3
            ),
            iterations,
        )
    return {"before": baseline, "after": optimized}


def _run_classification_once(
    db_path: Path,
    fn: Callable[[list[int], int], int],
) -> tuple[float, int, int]:
    app = _create_sqlite_app(db_path)
    with app.app_context():
        job = db.session.query(ClassificationJob).order_by(ClassificationJob.id.desc()).first()
        if not job:
            raise RuntimeError("classification benchmark job missing")
        question_ids = [int(row[0]) for row in db.session.query(Question.id).order_by(Question.id).all()]
        with _query_counter() as qc:
            t0 = time.perf_counter()
            applied_count = fn(question_ids, int(job.id))
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
        query_count = int(qc["value"])
    return elapsed_ms, query_count, applied_count


def run_classification_benchmark(
    template_db_path: Path,
    iterations: int,
) -> dict[str, dict]:
    before_times: list[float] = []
    before_queries: list[int] = []
    before_applied: list[int] = []
    after_times: list[float] = []
    after_queries: list[int] = []
    after_applied: list[int] = []

    for i in range(iterations):
        before_db = template_db_path.parent / f"classify_before_{i}.db"
        after_db = template_db_path.parent / f"classify_after_{i}.db"
        shutil.copy2(template_db_path, before_db)
        shutil.copy2(template_db_path, after_db)
        try:
            t_ms, q_count, applied = _run_classification_once(
                before_db,
                lambda qids, job_id: baseline_apply_classification_results(
                    qids, job_id, apply_mode="all"
                ),
            )
            before_times.append(t_ms)
            before_queries.append(q_count)
            before_applied.append(applied)

            t_ms, q_count, applied = _run_classification_once(
                after_db,
                lambda qids, job_id: int(
                    apply_classification_results(qids, job_id, apply_mode="all")
                ),
            )
            after_times.append(t_ms)
            after_queries.append(q_count)
            after_applied.append(applied)
        finally:
            if before_db.exists():
                before_db.unlink()
            if after_db.exists():
                after_db.unlink()

    if before_applied and after_applied and before_applied[0] != after_applied[0]:
        raise RuntimeError(
            f"classification applied_count mismatch: before={before_applied[0]} after={after_applied[0]}"
        )

    return {
        "before": _summarize(before_times, before_queries),
        "after": _summarize(after_times, after_queries),
        "applied_count": before_applied[0] if before_applied else 0,
    }


def _improvement(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return round(((before - after) / before) * 100.0, 2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark p95 for search/classification/manage service paths."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=12,
        help="Iterations per scenario (classification runs this many DB clones).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output JSON path (default: reports/benchmark_screen_p95_*.json).",
    )
    args = parser.parse_args()

    work_dir = Path(tempfile.mkdtemp(prefix="exam_perf_bench_"))
    try:
        manage_db = work_dir / "manage_seed.db"
        search_db = work_dir / "search_seed.db"
        classify_db = work_dir / "classify_seed.db"

        user_id = seed_manage_db(manage_db)
        seed_search_db(search_db)
        seed_classification_db(classify_db)

        manage_result = run_manage_benchmark(manage_db, user_id, args.iterations)
        search_result = run_search_benchmark(search_db, args.iterations)
        classify_result = run_classification_benchmark(classify_db, args.iterations)

        report = {
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "iterations": args.iterations,
            "runtime_db": "sqlite",
            "note": (
                "SQLite harness for reproducible local comparison when Postgres runtime "
                "profiling is unavailable."
            ),
            "manage_dashboard": manage_result,
            "search_candidate_aggregation": search_result,
            "classification_apply": classify_result,
        }

        if args.output_json:
            output_path = Path(args.output_json)
        else:
            output_path = (
                ROOT_DIR
                / "reports"
                / f"benchmark_screen_p95_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        table_rows = [
            (
                "manage_dashboard",
                manage_result["before"]["p95_ms"],
                manage_result["after"]["p95_ms"],
                _improvement(
                    manage_result["before"]["p95_ms"], manage_result["after"]["p95_ms"]
                ),
            ),
            (
                "search_candidate_aggregation",
                search_result["before"]["p95_ms"],
                search_result["after"]["p95_ms"],
                _improvement(
                    search_result["before"]["p95_ms"], search_result["after"]["p95_ms"]
                ),
            ),
            (
                "classification_apply",
                classify_result["before"]["p95_ms"],
                classify_result["after"]["p95_ms"],
                _improvement(
                    classify_result["before"]["p95_ms"],
                    classify_result["after"]["p95_ms"],
                ),
            ),
        ]

        print(f"Benchmark report: {output_path}")
        print("| Scenario | Before p95 (ms) | After p95 (ms) | Improvement |")
        print("|---|---:|---:|---:|")
        for name, before_p95, after_p95, pct in table_rows:
            print(f"| {name} | {before_p95:.2f} | {after_p95:.2f} | {pct:.2f}% |")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
