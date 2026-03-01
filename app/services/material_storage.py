from __future__ import annotations

from pathlib import Path

from flask import current_app


def resolve_upload_folder() -> Path:
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        return Path(upload_folder)
    return Path(current_app.static_folder) / "uploads"


def resolve_material_path(file_path: str | Path) -> Path:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate
    return resolve_upload_folder() / candidate


def should_keep_pdf_after_index() -> bool:
    return bool(current_app.config.get("KEEP_PDF_AFTER_INDEX", False))


def remove_material_file(
    path: Path,
    *,
    log_message: str = "Failed to delete uploaded material: %s",
) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning(log_message, path)
