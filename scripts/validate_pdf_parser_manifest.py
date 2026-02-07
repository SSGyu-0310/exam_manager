#!/usr/bin/env python3
"""Validate PDF parser counts against expected/uploaded counts in a manifest CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.pdf_parser_factory import parse_pdf

REQUIRED_COLUMNS = {
    "sample_id",
    "pdf_path",
    "expected_questions",
    "expected_choices",
    "uploaded_questions",
    "uploaded_choices",
    "notes",
}


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return int(text)


def _resolve_pdf_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (manifest_path.parent / candidate).resolve()


def _status(actual: int | None, expected: int | None) -> str:
    if expected is None:
        return "SKIP"
    if actual is None:
        return "ERROR"
    return "PASS" if actual == expected else "FAIL"


def _load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            missing_sorted = ", ".join(sorted(missing))
            raise ValueError(f"Missing required columns: {missing_sorted}")
        return list(reader)


def _write_report(report_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="docs/refactoring/pdf_parser_validation_template.csv",
        help="Path to validation manifest CSV.",
    )
    parser.add_argument(
        "--mode",
        default="legacy",
        choices=("legacy", "experimental"),
        help="PDF parser mode (legacy|experimental).",
    )
    parser.add_argument(
        "--report",
        default="parse_lab/output/pdf_parser_validation_report.csv",
        help="Output CSV path for computed comparison report.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    report_path = Path(args.report).resolve()

    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return 1

    try:
        manifest_rows = _load_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to read manifest: {exc}")
        return 1

    computed_rows: list[dict[str, str]] = []
    parse_errors = 0
    failed_checks = 0

    with TemporaryDirectory(prefix="pdf-validate-") as tmp_dir:
        upload_dir = Path(tmp_dir)
        for index, row in enumerate(manifest_rows, start=1):
            sample_id = (row.get("sample_id") or "").strip() or f"sample_{index:02d}"
            raw_pdf_path = (row.get("pdf_path") or "").strip()

            expected_questions = _to_int(row.get("expected_questions"))
            expected_choices = _to_int(row.get("expected_choices"))
            uploaded_questions = _to_int(row.get("uploaded_questions"))
            uploaded_choices = _to_int(row.get("uploaded_choices"))

            parsed_questions: int | None = None
            parsed_choices: int | None = None
            parse_error = ""

            pdf_path = _resolve_pdf_path(manifest_path, raw_pdf_path) if raw_pdf_path else None
            if not raw_pdf_path:
                parse_error = "missing pdf_path"
            elif pdf_path is None or not pdf_path.exists():
                parse_error = f"missing file: {pdf_path}"
            else:
                try:
                    parsed = parse_pdf(
                        pdf_path,
                        upload_dir=upload_dir,
                        exam_prefix=sample_id,
                        mode=args.mode,
                    )
                    parsed_questions = len(parsed)
                    parsed_choices = sum(len(item.get("options", [])) for item in parsed)
                except Exception as exc:  # noqa: BLE001
                    parse_error = str(exc)

            expected_q_status = _status(parsed_questions, expected_questions)
            expected_c_status = _status(parsed_choices, expected_choices)
            uploaded_q_status = _status(parsed_questions, uploaded_questions)
            uploaded_c_status = _status(parsed_choices, uploaded_choices)

            status_fields = (
                expected_q_status,
                expected_c_status,
                uploaded_q_status,
                uploaded_c_status,
            )
            failed_checks += sum(1 for status in status_fields if status == "FAIL")
            if parse_error:
                parse_errors += 1

            computed_rows.append(
                {
                    "sample_id": sample_id,
                    "pdf_path": raw_pdf_path,
                    "parser_mode": args.mode,
                    "parsed_questions": (
                        str(parsed_questions) if parsed_questions is not None else ""
                    ),
                    "parsed_choices": (
                        str(parsed_choices) if parsed_choices is not None else ""
                    ),
                    "expected_questions": row.get("expected_questions", ""),
                    "expected_choices": row.get("expected_choices", ""),
                    "uploaded_questions": row.get("uploaded_questions", ""),
                    "uploaded_choices": row.get("uploaded_choices", ""),
                    "expected_questions_status": expected_q_status,
                    "expected_choices_status": expected_c_status,
                    "uploaded_questions_status": uploaded_q_status,
                    "uploaded_choices_status": uploaded_c_status,
                    "parse_error": parse_error,
                    "notes": row.get("notes", ""),
                }
            )

    _write_report(report_path, computed_rows)

    print(f"[DONE] report: {report_path}")
    print(
        f"[SUMMARY] samples={len(computed_rows)} parse_errors={parse_errors} failed_checks={failed_checks}"
    )
    if parse_errors > 0 or failed_checks > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
