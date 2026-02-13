from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Dict, Optional

from app.models import Lecture
from app.services.folder_scope import parse_bool, resolve_lecture_ids
from app.services.user_scope import scope_model


def _pick_value(raw_scope: Mapping[str, Any], snake_key: str, legacy_key: str):
    if snake_key in raw_scope:
        return True, raw_scope.get(snake_key)
    if legacy_key in raw_scope:
        return True, raw_scope.get(legacy_key)
    return False, None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_lecture_ids(raw_value: Any) -> Optional[list[int]]:
    if raw_value is None:
        return None
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
        return None

    normalized: list[int] = []
    for lecture_id in raw_value:
        coerced = _coerce_int(lecture_id)
        if coerced is None:
            return None
        normalized.append(coerced)
    return sorted(set(normalized))


def normalize_scope_user_id(raw_user_id: Any) -> Optional[int]:
    return _coerce_int(raw_user_id)


def normalize_classification_scope(raw_scope: Any) -> Dict[str, Any]:
    if not isinstance(raw_scope, Mapping):
        return {}

    normalized: Dict[str, Any] = {}

    _, raw_block_id = _pick_value(raw_scope, "block_id", "blockId")
    block_id = _coerce_int(raw_block_id)
    if block_id is not None:
        normalized["block_id"] = block_id

    _, raw_folder_id = _pick_value(raw_scope, "folder_id", "folderId")
    folder_id = _coerce_int(raw_folder_id)
    if folder_id is not None:
        normalized["folder_id"] = folder_id

    if block_id is not None or folder_id is not None:
        _, raw_include_descendants = _pick_value(
            raw_scope, "include_descendants", "includeDescendants"
        )
        normalized["include_descendants"] = parse_bool(raw_include_descendants, True)

    lecture_ids_present, raw_lecture_ids = _pick_value(
        raw_scope, "lecture_ids", "lectureIds"
    )
    if lecture_ids_present:
        lecture_ids = _normalize_lecture_ids(raw_lecture_ids)
        if lecture_ids is not None:
            # Important: explicit [] must remain [].
            normalized["lecture_ids"] = lecture_ids

    return normalized


def resolve_scope_lecture_ids(
    scope: Any,
    *,
    user=None,
    include_public: bool = False,
) -> Dict[str, Any]:
    normalized = normalize_classification_scope(scope)

    if "lecture_ids" in normalized:
        lecture_ids = normalized["lecture_ids"]
        if not lecture_ids:
            normalized["lecture_ids"] = []
            return normalized
        allowed_ids = [
            row.id
            for row in scope_model(Lecture, user, include_public=include_public)
            .filter(Lecture.id.in_(lecture_ids))
            .all()
        ]
        normalized["lecture_ids"] = sorted(set(allowed_ids))
        return normalized

    block_id = normalized.get("block_id")
    folder_id = normalized.get("folder_id")
    if block_id is None and folder_id is None:
        return normalized

    resolved_ids = resolve_lecture_ids(
        block_id,
        folder_id,
        normalized.get("include_descendants", True),
        user=user,
        include_public=include_public,
    )
    if resolved_ids is not None:
        normalized["lecture_ids"] = sorted(set(resolved_ids))
    return normalized
