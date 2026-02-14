#!/usr/bin/env python3
"""Local PDF parsing/classification lab runner.

Fast iteration loop for backend-only parser tuning:
- Parse a local PDF with legacy/experimental mode
- Save structured outputs per run
- Detect suspicious parse anomalies
- Compare against baseline mode or prior JSON
- Optionally run lecture retrieval/classification
- Optional watch loop to auto-rerun after code changes
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app.services.pdf_parser_factory import parse_pdf

DEFAULT_WATCH_FILES = (
    "app/services/pdf_parser.py",
    "app/services/pdf_parser_experimental.py",
    "app/services/pdf_parser_factory.py",
)


@dataclass
class LabResult:
    run_dir: Path
    parsed_questions: list[dict[str, Any]]
    summary: dict[str, Any]
    anomalies: list[dict[str, Any]]
    diff: dict[str, Any] | None
    retrieval_results: list[dict[str, Any]] | None


class _ChoiceCollection:
    def __init__(self, choices: list[str]):
        self._choices = [
            SimpleNamespace(choice_number=index + 1, content=content or "")
            for index, content in enumerate(choices)
        ]

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._choices


class _DummyQuestion:
    def __init__(self, qid: int, content: str, choices: list[str]):
        self.id = qid
        self.content = content
        self.choices = _ChoiceCollection(choices)


def parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    result: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"Invalid integer token: {token}")
        result.append(int(token))
    return result


def normalize_space(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(str(text).split())


def _normalize_db_uri(db_value: str) -> str:
    db_uri = db_value.strip()
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if not db_uri.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "--db must be a PostgreSQL URI (postgresql+psycopg://...)."
        )
    return db_uri


def canonicalize_question(question: dict[str, Any]) -> dict[str, Any]:
    options = sorted(
        question.get("options", []),
        key=lambda item: int(item.get("number") or 0),
    )
    answer_options = sorted(int(v) for v in (question.get("answer_options") or []))
    return {
        "question_number": int(question.get("question_number") or 0),
        "content": normalize_space(question.get("content", "")),
        "image_path": question.get("image_path"),
        "options": [
            {
                "number": int(opt.get("number") or 0),
                "content": normalize_space(opt.get("content", "")),
                "image_path": opt.get("image_path"),
                "is_correct": bool(opt.get("is_correct", False)),
            }
            for opt in options
        ],
        "answer_options": answer_options,
        "answer_text": normalize_space(question.get("answer_text", "")),
    }


def analyze_parse_result(
    questions: list[dict[str, Any]],
    max_option_number: int,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()

    for raw_q in questions:
        q = canonicalize_question(raw_q)
        qnum = q["question_number"]
        options = q["options"]
        answer_options = q["answer_options"]
        option_numbers = {opt["number"] for opt in options}

        if qnum in seen_numbers:
            anomalies.append(
                {
                    "code": "DUPLICATE_QUESTION_NUMBER",
                    "question_number": qnum,
                    "detail": f"Question number {qnum} appears multiple times.",
                }
            )
        seen_numbers.add(qnum)

        if not q["content"] and not q["image_path"]:
            anomalies.append(
                {
                    "code": "EMPTY_QUESTION_CONTENT",
                    "question_number": qnum,
                    "detail": "Question has neither text nor image.",
                }
            )

        if options and not any(opt["content"] or opt["image_path"] for opt in options):
            anomalies.append(
                {
                    "code": "EMPTY_OPTIONS",
                    "question_number": qnum,
                    "detail": "Question has option slots but no option content/image.",
                }
            )

        for opt in options:
            number = opt["number"]
            if number <= 0 or number > max_option_number:
                anomalies.append(
                    {
                        "code": "OPTION_NUMBER_OUT_OF_RANGE",
                        "question_number": qnum,
                        "detail": (
                            f"Option number {number} is outside 1..{max_option_number}."
                        ),
                    }
                )
            if not opt["content"] and not opt["image_path"]:
                anomalies.append(
                    {
                        "code": "EMPTY_OPTION_CONTENT",
                        "question_number": qnum,
                        "detail": f"Option {number} has neither text nor image.",
                    }
                )

        invalid_answers = [n for n in answer_options if n not in option_numbers]
        if invalid_answers:
            anomalies.append(
                {
                    "code": "ANSWER_OPTION_MISSING",
                    "question_number": qnum,
                    "detail": f"Answer option(s) not found in options: {invalid_answers}",
                }
            )

        if options and not answer_options and not q["answer_text"]:
            anomalies.append(
                {
                    "code": "NO_ANSWER_SIGNAL",
                    "question_number": qnum,
                    "detail": "Options exist but no marked answer option/text found.",
                }
            )

    return anomalies


def build_diff_report(
    current_questions: list[dict[str, Any]],
    baseline_questions: list[dict[str, Any]],
) -> dict[str, Any]:
    current_map = {
        q["question_number"]: q for q in (canonicalize_question(i) for i in current_questions)
    }
    baseline_map = {
        q["question_number"]: q
        for q in (canonicalize_question(i) for i in baseline_questions)
    }

    current_numbers = set(current_map.keys())
    baseline_numbers = set(baseline_map.keys())
    added = sorted(current_numbers - baseline_numbers)
    removed = sorted(baseline_numbers - current_numbers)

    changed: list[dict[str, Any]] = []
    for qnum in sorted(current_numbers & baseline_numbers):
        cur = current_map[qnum]
        base = baseline_map[qnum]
        fields: list[str] = []

        if cur["content"] != base["content"]:
            fields.append("content")
        if cur["image_path"] != base["image_path"]:
            fields.append("image_path")
        if cur["options"] != base["options"]:
            fields.append("options")
        if cur["answer_options"] != base["answer_options"]:
            fields.append("answer_options")
        if cur["answer_text"] != base["answer_text"]:
            fields.append("answer_text")

        if fields:
            changed.append(
                {
                    "question_number": qnum,
                    "changed_fields": fields,
                    "current_option_count": len(cur["options"]),
                    "baseline_option_count": len(base["options"]),
                    "current_answer_options": cur["answer_options"],
                    "baseline_answer_options": base["answer_options"],
                }
            )

    return {
        "added_questions": added,
        "removed_questions": removed,
        "changed_questions": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def _build_question_preview_markdown(
    questions: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    limit: int,
    selected_question_numbers: set[int] | None = None,
) -> str:
    lines = ["# PDF Lab Preview", ""]
    anomaly_by_qnum: dict[int, list[dict[str, Any]]] = {}
    for item in anomalies:
        qnum = int(item.get("question_number") or 0)
        anomaly_by_qnum.setdefault(qnum, []).append(item)

    count = 0
    for question in questions:
        q = canonicalize_question(question)
        qnum = q["question_number"]
        if selected_question_numbers and qnum not in selected_question_numbers:
            continue
        if count >= limit:
            break
        count += 1

        lines.append(f"## Q{qnum}")
        lines.append(f"- content: {q['content'] or '(empty)'}")
        lines.append(
            f"- image_path: {q['image_path'] or '(none)'} | answer_options: {q['answer_options']}"
        )
        lines.append(f"- answer_text: {q['answer_text'] or '(empty)'}")
        lines.append("- options:")
        if not q["options"]:
            lines.append("  - (none)")
        else:
            for opt in q["options"]:
                option_text = opt["content"] or "(empty)"
                option_image = opt["image_path"] or "-"
                lines.append(
                    "  - "
                    f"{opt['number']}) {option_text} "
                    f"[correct={opt['is_correct']}, image={option_image}]"
                )
        if anomaly_by_qnum.get(qnum):
            lines.append("- anomalies:")
            for anomaly in anomaly_by_qnum[qnum]:
                lines.append(f"  - {anomaly['code']}: {anomaly['detail']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _extract_choice_texts(question: dict[str, Any]) -> list[str]:
    ordered_options = sorted(
        question.get("options", []),
        key=lambda item: int(item.get("number") or 0),
    )
    return [normalize_space(opt.get("content", "")) for opt in ordered_options]


def _resolve_scoped_lecture_ids(
    app,
    block_id: int | None,
    folder_id: int | None,
    include_descendants: bool,
) -> list[int] | None:
    if block_id is None and folder_id is None:
        return None

    from app.models import Lecture
    from app.services.folder_scope import resolve_folder_ids

    with app.app_context():
        query = Lecture.query
        if block_id is not None:
            query = query.filter(Lecture.block_id == block_id)
        if folder_id is not None:
            folder_ids = resolve_folder_ids(folder_id, include_descendants, block_id)
            if not folder_ids:
                return []
            query = query.filter(Lecture.folder_id.in_(folder_ids))
        return [lecture.id for lecture in query.all()]


def _run_retrieval_and_classification(
    *,
    app,
    questions: list[dict[str, Any]],
    top_k: int,
    lecture_ids: list[int] | None,
    with_classifier: bool,
) -> list[dict[str, Any]]:
    from app.services.ai_classifier import GeminiClassifier, LectureRetriever

    results: list[dict[str, Any]] = []

    with app.app_context():
        retriever = LectureRetriever()
        retriever.refresh_cache()
        classifier = GeminiClassifier() if with_classifier else None

        for index, question in enumerate(questions, start=1):
            qnum = int(question.get("question_number") or index)
            content = normalize_space(question.get("content", ""))
            choice_texts = _extract_choice_texts(question)
            merged = content
            if choice_texts:
                merged = f"{merged}\n" + " ".join(choice_texts)
            merged = merged.strip()
            if len(merged) > 4000:
                merged = merged[:4000]

            candidates = retriever.find_candidates(
                merged,
                top_k=top_k,
                question_id=None,
                lecture_ids=lecture_ids,
            )
            item: dict[str, Any] = {
                "question_number": qnum,
                "candidate_count": len(candidates),
                "top_candidates": [
                    {
                        "id": c.get("id"),
                        "full_path": c.get("full_path"),
                        "score": c.get("score"),
                    }
                    for c in candidates
                ],
            }

            if classifier:
                dummy_question = _DummyQuestion(qnum, content, choice_texts)
                result = classifier.classify_single(dummy_question, candidates)
                item["classification"] = {
                    "lecture_id": result.get("lecture_id"),
                    "confidence": result.get("confidence", 0.0),
                    "reason": result.get("reason", ""),
                    "study_hint": result.get("study_hint", ""),
                    "no_match": result.get("no_match", False),
                    "model_name": result.get("model_name", ""),
                }

            results.append(item)

    return results


def _file_state(paths: Iterable[Path]) -> dict[str, tuple[bool, int, int]]:
    state: dict[str, tuple[bool, int, int]] = {}
    for path in paths:
        abs_path = path.resolve()
        if abs_path.exists():
            stat = abs_path.stat()
            state[str(abs_path)] = (True, int(stat.st_mtime_ns), int(stat.st_size))
        else:
            state[str(abs_path)] = (False, 0, 0)
    return state


def _load_questions_from_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return payload["questions"]
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported JSON structure: {path}")


def _create_run_dir(output_root: Path, pdf_path: Path, mode: str) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    stem = pdf_path.stem.replace(" ", "_")
    run_dir = output_root / f"{timestamp}_{stem}_{mode}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_once(args) -> LabResult:
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_root = Path(args.output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = _create_run_dir(output_root, pdf_path, args.mode)
    media_dir = run_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    exam_prefix = args.exam_prefix or pdf_path.stem[:20]
    started_at = datetime.utcnow()
    started_monotonic = time.perf_counter()
    parsed_questions = parse_pdf(
        pdf_path=pdf_path,
        upload_dir=media_dir,
        exam_prefix=exam_prefix,
        mode=args.mode,
        max_option_number=args.max_option_number,
    )
    elapsed_ms = round((time.perf_counter() - started_monotonic) * 1000, 2)

    question_numbers_filter = (
        set(parse_int_list(args.questions)) if (args.questions or "").strip() else None
    )
    anomalies = analyze_parse_result(parsed_questions, args.max_option_number)
    anomalies_filtered = (
        [a for a in anomalies if int(a.get("question_number") or 0) in question_numbers_filter]
        if question_numbers_filter
        else anomalies
    )

    baseline_questions: list[dict[str, Any]] | None = None
    diff_report: dict[str, Any] | None = None

    if args.compare_json:
        baseline_path = Path(args.compare_json).expanduser().resolve()
        if not baseline_path.exists():
            raise FileNotFoundError(f"--compare-json not found: {baseline_path}")
        baseline_questions = _load_questions_from_json(baseline_path)

    if args.compare_mode:
        with TemporaryDirectory(prefix="pdf-lab-baseline-") as tmp:
            baseline_questions = parse_pdf(
                pdf_path=pdf_path,
                upload_dir=Path(tmp),
                exam_prefix=exam_prefix,
                mode=args.compare_mode,
                max_option_number=args.max_option_number,
            )

    if baseline_questions is not None:
        diff_report = build_diff_report(parsed_questions, baseline_questions)

    retrieval_results: list[dict[str, Any]] | None = None
    if args.with_retrieval or args.with_classifier:
        from app import create_app

        db_override = None
        if args.db:
            db_override = _normalize_db_uri(args.db)

        app = create_app(
            args.config,
            db_uri_override=db_override,
            skip_migration_check=True,
        )
        if args.retrieval_mode:
            app.config["RETRIEVAL_MODE"] = args.retrieval_mode

        lecture_ids = parse_int_list(args.lecture_ids)
        if not lecture_ids:
            lecture_ids = _resolve_scoped_lecture_ids(
                app,
                args.block_id,
                args.folder_id,
                args.include_descendants,
            ) or []
        lecture_ids_or_none = lecture_ids if lecture_ids else None

        retrieval_results = _run_retrieval_and_classification(
            app=app,
            questions=parsed_questions,
            top_k=args.top_k,
            lecture_ids=lecture_ids_or_none,
            with_classifier=args.with_classifier,
        )
        if question_numbers_filter:
            retrieval_results = [
                item
                for item in retrieval_results
                if int(item.get("question_number") or 0) in question_numbers_filter
            ]

    parsed_payload = {
        "meta": {
            "generated_at": started_at.isoformat() + "Z",
            "parser_mode": args.mode,
            "pdf_path": str(pdf_path),
            "elapsed_ms": elapsed_ms,
            "max_option_number": args.max_option_number,
            "exam_prefix": exam_prefix,
        },
        "questions": parsed_questions,
    }
    _write_json(run_dir / "parsed_questions.json", parsed_payload)
    _write_json(run_dir / "anomalies.json", anomalies_filtered)
    if diff_report is not None:
        _write_json(run_dir / "diff.json", diff_report)
    if retrieval_results is not None:
        _write_json(run_dir / "retrieval_classification.json", retrieval_results)

    preview_md = _build_question_preview_markdown(
        parsed_questions,
        anomalies_filtered,
        limit=args.preview_limit,
        selected_question_numbers=question_numbers_filter,
    )
    (run_dir / "preview.md").write_text(preview_md, encoding="utf-8")

    total_choices = sum(len(q.get("options", [])) for q in parsed_questions)
    summary: dict[str, Any] = {
        "generated_at": started_at.isoformat() + "Z",
        "pdf_path": str(pdf_path),
        "parser_mode": args.mode,
        "elapsed_ms": elapsed_ms,
        "question_count": len(parsed_questions),
        "choice_count": total_choices,
        "anomaly_count": len(anomalies_filtered),
        "anomaly_codes": sorted({a.get("code", "") for a in anomalies_filtered}),
        "output_dir": str(run_dir),
    }
    if diff_report is not None:
        summary["diff_summary"] = diff_report.get("summary", {})
    if retrieval_results is not None:
        summary["retrieval_count"] = len(retrieval_results)
        summary["classified_count"] = sum(
            1 for item in retrieval_results if item.get("classification")
        )
    _write_json(run_dir / "summary.json", summary)

    return LabResult(
        run_dir=run_dir,
        parsed_questions=parsed_questions,
        summary=summary,
        anomalies=anomalies_filtered,
        diff=diff_report,
        retrieval_results=retrieval_results,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Path to local PDF file.")
    parser.add_argument(
        "--mode",
        choices=("legacy", "experimental"),
        default=os.environ.get("PDF_PARSER_MODE", "legacy"),
        help="Parser mode.",
    )
    parser.add_argument(
        "--compare-mode",
        choices=("legacy", "experimental"),
        default=None,
        help="Optional baseline parser mode for in-run diff.",
    )
    parser.add_argument(
        "--compare-json",
        default=None,
        help="Compare with parsed JSON file from a previous run.",
    )
    parser.add_argument(
        "--questions",
        default="",
        help="Comma-separated question numbers to focus preview/results.",
    )
    parser.add_argument(
        "--output-root",
        default="parse_lab/output/lab_runs",
        help="Root directory for lab runs.",
    )
    parser.add_argument(
        "--exam-prefix",
        default=None,
        help="Image filename prefix (default: PDF stem).",
    )
    parser.add_argument(
        "--max-option-number",
        type=int,
        default=16,
        help="Max option number for parser.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=15,
        help="How many questions to include in preview.md.",
    )

    parser.add_argument(
        "--with-retrieval",
        action="store_true",
        help="Attach lecture retrieval candidates per parsed question.",
    )
    parser.add_argument(
        "--with-classifier",
        action="store_true",
        help="Run Gemini classifier on top of retrieval candidates.",
    )
    parser.add_argument("--top-k", type=int, default=8, help="Retriever top-k.")
    parser.add_argument(
        "--lecture-ids",
        default="",
        help="Comma-separated lecture IDs restriction.",
    )
    parser.add_argument("--block-id", type=int, default=None, help="Filter by block id.")
    parser.add_argument("--folder-id", type=int, default=None, help="Filter by folder id.")
    parser.add_argument(
        "--include-descendants",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When folder-id is set, include descendants.",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=("bm25",),
        default=None,
        help="Override retrieval mode.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Optional PostgreSQL URI override for retrieval/classification.",
    )
    parser.add_argument(
        "--config",
        default="default",
        help="Flask config profile for app context.",
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch parser files and PDF, then auto-rerun.",
    )
    parser.add_argument(
        "--watch-interval",
        type=float,
        default=1.0,
        help="Watch poll interval in seconds.",
    )
    parser.add_argument(
        "--watch-files",
        default="",
        help="Extra files to watch (comma-separated paths).",
    )
    return parser


def _watch_paths(args) -> list[Path]:
    paths = [Path(args.pdf).expanduser().resolve()]
    for relative in DEFAULT_WATCH_FILES:
        paths.append((ROOT_DIR / relative).resolve())
    for item in (args.watch_files or "").split(","):
        item = item.strip()
        if not item:
            continue
        paths.append(Path(item).expanduser().resolve())
    unique: list[Path] = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _print_result(result: LabResult) -> None:
    summary = result.summary
    print("")
    print("=== PDF LAB RUN ===")
    print(f"output_dir: {summary.get('output_dir')}")
    print(
        "parsed: "
        f"questions={summary.get('question_count')} "
        f"choices={summary.get('choice_count')} "
        f"elapsed_ms={summary.get('elapsed_ms')}"
    )
    print(
        "anomalies: "
        f"count={summary.get('anomaly_count')} "
        f"codes={','.join(summary.get('anomaly_codes', [])) or '-'}"
    )
    if summary.get("diff_summary") is not None:
        diff = summary["diff_summary"]
        print(
            "diff: "
            f"added={diff.get('added', 0)} "
            f"removed={diff.get('removed', 0)} "
            f"changed={diff.get('changed', 0)}"
        )
    if result.retrieval_results is not None:
        print(
            "retrieval/classifier: "
            f"items={summary.get('retrieval_count', 0)} "
            f"classified={summary.get('classified_count', 0)}"
        )
    print("===================")
    print("")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.with_classifier:
        args.with_retrieval = True

    if args.db:
        try:
            _normalize_db_uri(args.db)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {exc}")
            return 1
    if args.compare_mode and args.compare_json:
        print("[ERROR] Use only one of --compare-mode or --compare-json.")
        return 1

    if not args.watch:
        try:
            result = run_once(args)
            _print_result(result)
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {exc}")
            return 1

    watch_paths = _watch_paths(args)
    print("PDF lab watch mode started.")
    print("Watching files:")
    for path in watch_paths:
        print(f"- {path}")
    print("Press Ctrl+C to stop.")

    stop = False

    def _handle_signal(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    previous_state: dict[str, tuple[bool, int, int]] | None = None
    while not stop:
        current_state = _file_state(watch_paths)
        changed = previous_state is None or current_state != previous_state
        if changed:
            changed_files = []
            if previous_state is None:
                changed_files = list(current_state.keys())
            else:
                for path, state in current_state.items():
                    if previous_state.get(path) != state:
                        changed_files.append(path)
            if changed_files:
                print("")
                print("Detected change:")
                for path in changed_files:
                    print(f"- {path}")
            try:
                result = run_once(args)
                _print_result(result)
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] {exc}")
            previous_state = current_state

        time.sleep(max(args.watch_interval, 0.2))

    print("PDF lab watch mode stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
