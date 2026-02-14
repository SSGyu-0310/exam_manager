from __future__ import annotations

import re
import logging
from typing import List, Dict, Optional

from sqlalchemy import text, bindparam

from config import get_config
from app import db
from app.services.db_utils import is_postgres


# FTS5 reserved operators (case-insensitive)
_FTS_RESERVED = {"OR", "AND", "NOT", "NEAR"}
_BM25_STOPWORDS = {
    "다음",
    "중",
    "옳은",
    "틀린",
    "아닌",
    "것",
    "가장",
    "맞는",
    "고른",
    "고르시오",
    "선지",
    "문항",
    "보기",
    "위",
    "아래",
    "다음중",
    "해당",
    "설명",
    "것은",
}

# Token patterns:
#  - ratios like 120/80
#  - decimals like 7.35
#  - integers like 140
#  - words (Korean/English) like "Cr", "Na", "알칼리증"
_TOKEN_RE = re.compile(
    r"""
    \d+/\d+            # ratio
    |\d+\.\d+          # decimal
    |[A-Za-z]+[0-9]+[A-Za-z0-9]*[+-]?  # alnum like HCO3, HbA1c, pCO2
    |[0-9]+[A-Za-z]+[A-Za-z0-9]*       # alnum like 2A
    |[A-Za-z]+[+-]?                    # english word, optional +/-
    |[가-힣]+           # korean word
    |\d+               # integer
    """,
    re.VERBOSE,
)


_PG_TOKEN_CLEAN_RE = re.compile(r"[^0-9A-Za-z가-힣]")


def _resolve_search_backend() -> str:
    """Resolve effective search backend (Postgres-only runtime)."""
    native_backend = "postgres" if is_postgres() else "unsupported"
    requested = (get_config().experiment.search_backend or "auto").strip().lower()
    if requested in ("", "auto"):
        if native_backend == "postgres":
            return "postgres"
        raise RuntimeError(
            "Search backend requires PostgreSQL runtime. "
            "SQLite fallback has been removed."
        )
    if requested in ("postgres", "postgresql"):
        if native_backend != "postgres":
            raise RuntimeError(
                "SEARCH_BACKEND=postgres requested but active DB is not PostgreSQL. "
                "SQLite fallback has been removed."
            )
        return "postgres"
    if requested == "sqlite":
        logging.warning(
            "SEARCH_BACKEND=sqlite is no longer supported; forcing postgres backend."
        )
        if native_backend == "postgres":
            return "postgres"
        raise RuntimeError(
            "SEARCH_BACKEND=sqlite is unsupported and active DB is not PostgreSQL."
        )
    logging.warning("Unsupported SEARCH_BACKEND=%s; forcing postgres backend.", requested)
    if native_backend == "postgres":
        return "postgres"
    raise RuntimeError("Unsupported DB backend for search.")


def use_postgres_search_backend() -> bool:
    return _resolve_search_backend() == "postgres"


def _pg_query_mode() -> str:
    mode = (get_config().experiment.search_pg_query_mode or "websearch").strip().lower()
    if mode not in ("websearch", "plainto", "to_tsquery"):
        return "websearch"
    return mode


def postgres_tsquery_expression(param_name: str = "query") -> str:
    """SQL fragment for Postgres tsquery expression from configured mode."""
    mode = _pg_query_mode()
    if mode == "plainto":
        fn = "plainto_tsquery"
    elif mode == "to_tsquery":
        fn = "to_tsquery"
    else:
        fn = "websearch_to_tsquery"
    return f"{fn}('simple', :{param_name})"


def _needs_quote(token: str) -> bool:
    """Check if token needs double quotes for FTS5 escaping.

    Tokens need quotes if they contain:
    - Special characters: -, *, ", (, ), {, }, [, ]
    - Are single character (can confuse parser)
    - Start with a digit (can be ambiguous)
    """
    if not token:
        return False
    if len(token) == 1:
        return True
    if token.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
        return True
    special_chars = {"-", "+", "/", "*", '"', "(", ")", "{", "}", "[", "]", ":"}
    return any(c in special_chars for c in token)


def _normalize_query(text: str) -> str:
    """Normalize query text for FTS5 search."""
    if not text:
        return ""
    # Extract tokens using regex
    tokens = _TOKEN_RE.findall(text)
    # Filter out stopwords and reserved FTS operators
    filtered = []
    for t in tokens:
        if t.upper() in _FTS_RESERVED:
            continue
        if t in _BM25_STOPWORDS:
            continue
        filtered.append(t)
    return " ".join(filtered)


def _build_fts_query(tokens_or_str, max_terms: int = 16, mode: str = "OR") -> str:
    # Accept either string (space-separated) or list of tokens
    if isinstance(tokens_or_str, str):
        tokens = [t for t in tokens_or_str.split() if t]
    else:
        tokens = list(tokens_or_str) if tokens_or_str else []
    if not tokens:
        return ""
    seen = set()
    deduped = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    if len(deduped) == 1:
        token = deduped[0]
        return f'"{token}"' if _needs_quote(token) else token
    quoted_tokens = [
        f'"{token}"' if _needs_quote(token) else token for token in deduped
    ]
    joiner = " OR " if str(mode).upper() == "OR" else " "
    return joiner.join(quoted_tokens)


def _build_plain_query_input(tokens_or_str, max_terms: int = 16) -> str:
    if isinstance(tokens_or_str, str):
        tokens = [t for t in tokens_or_str.split() if t]
    else:
        tokens = list(tokens_or_str) if tokens_or_str else []
    if not tokens:
        return ""
    deduped = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    return " ".join(deduped)


def _sanitize_pg_token(token: str) -> str:
    return _PG_TOKEN_CLEAN_RE.sub("", token or "").strip()


def _build_pg_websearch_query(
    tokens_or_str,
    max_terms: int = 16,
    mode: str = "OR",
) -> str:
    if isinstance(tokens_or_str, str):
        tokens = [t for t in tokens_or_str.split() if t]
    else:
        tokens = list(tokens_or_str) if tokens_or_str else []
    if not tokens:
        return ""

    deduped: List[str] = []
    seen = set()
    for token in tokens:
        sanitized = _sanitize_pg_token(token)
        if not sanitized or sanitized in seen:
            continue
        seen.add(sanitized)
        deduped.append(sanitized)
        if len(deduped) >= max_terms:
            break
    if not deduped:
        return ""
    if len(deduped) == 1:
        return deduped[0]

    joiner = " OR " if str(mode).upper() == "OR" else " "
    return joiner.join(deduped)


def _build_pg_tsquery(tokens_or_str, max_terms: int = 16, mode: str = "OR") -> str:
    if isinstance(tokens_or_str, str):
        tokens = [t for t in tokens_or_str.split() if t]
    else:
        tokens = list(tokens_or_str) if tokens_or_str else []
    if not tokens:
        return ""

    seen = set()
    cleaned = []
    for token in tokens:
        sanitized = _sanitize_pg_token(token)
        if not sanitized or sanitized in seen:
            continue
        seen.add(sanitized)
        cleaned.append(sanitized)
        if len(cleaned) >= max_terms:
            break
    if not cleaned:
        return ""

    joiner = " | " if str(mode).upper() == "OR" else " & "
    return joiner.join(cleaned)


def _build_match_query(
    tokens_or_str,
    max_terms: int = 16,
    mode: str = "OR",
    backend: Optional[str] = None,
) -> str:
    backend = backend or _resolve_search_backend()
    if backend == "postgres":
        pg_mode = _pg_query_mode()
        if pg_mode == "to_tsquery":
            return _build_pg_tsquery(tokens_or_str, max_terms=max_terms, mode=mode)
        if pg_mode == "websearch":
            return _build_pg_websearch_query(
                tokens_or_str,
                max_terms=max_terms,
                mode=mode,
            )
        return _build_plain_query_input(tokens_or_str, max_terms=max_terms)
    raise RuntimeError(f"Unsupported search backend: {backend}")


def make_bm25_match_query(raw_question_text: str) -> str:
    tokens = _normalize_query(raw_question_text)
    return _build_match_query(
        tokens, max_terms=16, mode="OR", backend=_resolve_search_backend()
    )


def safe_match_query_variants(raw_question_text: str) -> List[str]:
    tokens = _normalize_query(raw_question_text)
    if not tokens:
        return []
    backend = _resolve_search_backend()
    return [
        _build_match_query(tokens, max_terms=16, mode="OR", backend=backend),
        _build_match_query(tokens, max_terms=8, mode="OR", backend=backend),
        _build_match_query(tokens, max_terms=4, mode="OR", backend=backend),
    ]


def _normalize_search_text(text: str, max_chars: int = 4000) -> str:
    if not text:
        return ""
    s = text.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        s = s[:max_chars]
    return s


def search_chunks_bm25(
    query: str,
    top_n: int = 80,
    *,
    question_id: int | None = None,
    lecture_ids: List[int] | None = None,
) -> List[Dict]:
    # question_id is retained for API compatibility with existing call sites.
    _ = question_id
    backend = _resolve_search_backend()
    tokens = _normalize_query(query)
    query_inputs: List[str] = []
    fts_query = _build_match_query(tokens, max_terms=16, mode="OR", backend=backend)
    if fts_query:
        query_inputs.append(fts_query)

    # Postgres websearch/plainto can be over-restrictive for long prompts.
    # Add shorter fallback variants before giving up.
    if backend == "postgres":
        for max_terms in (8, 4):
            variant_query = _build_match_query(
                tokens,
                max_terms=max_terms,
                mode="OR",
                backend=backend,
            )
            if variant_query and variant_query not in query_inputs:
                query_inputs.append(variant_query)

    if lecture_ids is not None and not lecture_ids:
        return []

    rows = []
    for query_input in query_inputs:
        rows = _search_chunks_bm25_postgres(
            query_input,
            top_n=top_n,
            lecture_ids=lecture_ids,
        )
        if rows:
            break

    # Ensure rows are mutable dicts (DB may return RowMapping objects)
    rows = [dict(r) if not isinstance(r, dict) else r for r in rows]

    # TRGM score blending (P1-2): blend BM25 + alpha * TRGM scores.
    cfg = get_config().experiment
    blend_mode = getattr(cfg, "search_pg_trgm_blend_mode", "off")
    trgm_alpha = float(getattr(cfg, "search_pg_trgm_alpha", 0.3))
    min_bm25_results = int(getattr(cfg, "search_pg_trgm_min_bm25_results", 10))

    should_run_trgm = False
    if backend == "postgres" and bool(cfg.search_pg_trgm_enabled) and blend_mode != "off":
        if blend_mode == "always":
            should_run_trgm = True
        elif blend_mode == "conditional":
            # Fire if BM25 returned few results or query is short
            if len(rows) < min_bm25_results:
                should_run_trgm = True
            elif len(tokens) <= 5:
                should_run_trgm = True

    if should_run_trgm:
        trgm_top_n = max(top_n, int(cfg.search_pg_trgm_top_n))
        trgm_rows = _search_chunks_trgm_postgres(
            query_text=_normalize_search_text(query, max_chars=1000),
            top_n=trgm_top_n,
            lecture_ids=lecture_ids,
            min_similarity=float(cfg.search_pg_trgm_min_similarity),
        )
        if trgm_rows:
            trgm_rows = [dict(r) if not isinstance(r, dict) else r for r in trgm_rows]
            # Build lookup: chunk_id -> trgm_score
            trgm_by_chunk = {r["chunk_id"]: float(r.get("trgm_score", 0)) for r in trgm_rows if r.get("chunk_id")}
            # Add trgm_score to existing BM25 rows
            for row in rows:
                cid = row.get("chunk_id")
                if cid and cid in trgm_by_chunk:
                    row["trgm_score"] = trgm_by_chunk.pop(cid)
            # Add TRGM-only chunks (not in BM25 results)
            for trow in trgm_rows:
                cid = trow.get("chunk_id")
                if cid and cid in trgm_by_chunk:
                    trow["bm25_score"] = 0.0  # no BM25 match
                    rows.append(trow)
                    trgm_by_chunk.pop(cid, None)

    if not rows:
        return []

    # Compute blended score for each chunk
    for row in rows:
        bm25_raw = row.get("bm25_score")
        trgm_raw = row.get("trgm_score")
        bm25_val = float(bm25_raw or 0.0)
        trgm_val = float(trgm_raw or 0.0)
        row["_final_score"] = bm25_val + trgm_alpha * trgm_val

    # Re-sort by blended score descending
    rows.sort(key=lambda r: r.get("_final_score", 0), reverse=True)

    results = []
    for row in rows[:top_n]:
        snippet_text = (
            (row.get("snippet") or "")
            .replace("\n", " ")
            .replace("<b>", "")
            .replace("</b>", "")
            .strip()
        )
        results.append(
            {
                "chunk_id": row.get("chunk_id"),
                "lecture_id": row.get("lecture_id"),
                "page_start": row.get("page_start"),
                "page_end": row.get("page_end"),
                "snippet": snippet_text,
                "bm25_score": row.get("_final_score", 0),
            }
        )
    return results


def _search_chunks_bm25_postgres(
    query_input: str,
    *,
    top_n: int,
    lecture_ids: List[int] | None,
) -> List[Dict]:
    tsq_expr = postgres_tsquery_expression("query")
    where_clause = "WHERE c.content_tsv @@ q.tsq"
    params: Dict[str, object] = {"query": query_input, "top_n": top_n}

    if lecture_ids is not None:
        where_clause += " AND c.lecture_id IN :lecture_ids"
        params["lecture_ids"] = [int(lecture_id) for lecture_id in lecture_ids]

    sql = text(
        f"""
        WITH q AS (
            SELECT {tsq_expr} AS tsq
        )
        SELECT
            c.id AS chunk_id,
            c.lecture_id,
            c.page_start,
            c.page_end,
            ts_headline(
                'simple',
                c.content,
                q.tsq,
                'MaxFragments=1, MaxWords=24, MinWords=8, ShortWord=2'
            ) AS snippet,
            ts_rank_cd(c.content_tsv, q.tsq) AS bm25_score
        FROM lecture_chunks c
        CROSS JOIN q
        {where_clause}
        ORDER BY bm25_score DESC
        LIMIT :top_n
        """
    )
    if lecture_ids is not None:
        sql = sql.bindparams(bindparam("lecture_ids", expanding=True))
    return db.session.execute(sql, params).mappings().all()


def _search_chunks_trgm_postgres(
    query_text: str,
    *,
    top_n: int,
    lecture_ids: List[int] | None,
    min_similarity: float,
) -> List[Dict]:
    if not query_text:
        return []

    params: Dict[str, object] = {
        "query": query_text,
        "top_n": top_n,
        "min_similarity": min_similarity,
    }
    where_clause = "WHERE similarity(c.content, :query) >= :min_similarity"

    if lecture_ids is not None:
        where_clause += " AND c.lecture_id IN :lecture_ids"
        params["lecture_ids"] = [int(lecture_id) for lecture_id in lecture_ids]

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.lecture_id,
            c.page_start,
            c.page_end,
            left(regexp_replace(c.content, '\\s+', ' ', 'g'), 240) AS snippet,
            similarity(c.content, :query) AS trgm_score
        FROM lecture_chunks c
        {where_clause}
        ORDER BY trgm_score DESC
        LIMIT :top_n
        """
    )
    if lecture_ids is not None:
        sql = sql.bindparams(bindparam("lecture_ids", expanding=True))
    try:
        return db.session.execute(sql, params).mappings().all()
    except Exception as exc:
        logging.warning("pg_trgm fallback query failed: %s", exc)
        return []


def aggregate_candidates(
    chunks: List[Dict],
    top_k_lectures: int = 8,
    evidence_per_lecture: int = 3,
    *,
    agg_mode: str = "sum",
    topm: int = 3,
    chunk_cap: int = 0,
) -> List[Dict]:
    if not chunks:
        return []

    # P2-2: Per-lecture chunk cap — limit how many chunks per lecture enter the pool
    if chunk_cap > 0:
        capped: List[Dict] = []
        per_lec_count: Dict[int, int] = {}
        for chunk in chunks:  # chunks are already score-sorted from retrieval
            lid = chunk.get("lecture_id")
            if lid is None:
                continue
            per_lec_count[lid] = per_lec_count.get(lid, 0) + 1
            if per_lec_count[lid] <= chunk_cap:
                capped.append(chunk)
        chunks = capped

    # Collect per-lecture chunk scores and evidence
    per_lecture: Dict[int, Dict] = {}
    for chunk in chunks:
        lecture_id = chunk.get("lecture_id")
        if lecture_id is None:
            continue
        score = _chunk_relevance(chunk)
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

    # P2-1: Compute lecture score based on agg_mode
    for info in per_lecture.values():
        scores = info["scores"]
        if agg_mode == "topm_mean" and scores:
            top_scores = sorted(scores, reverse=True)[:topm]
            info["score"] = sum(top_scores) / len(top_scores)
        else:
            info["score"] = sum(scores)

    lecture_ids = list(per_lecture.keys())
    lecture_map = _fetch_lecture_metadata(lecture_ids) if lecture_ids else {}

    candidates = []
    for lecture_id, info in per_lecture.items():
        lecture = lecture_map.get(lecture_id)
        if not lecture:
            continue
        evidence = sorted(info["evidence"], key=lambda e: e["score"], reverse=True)[
            :evidence_per_lecture
        ]
        title = lecture.get("title", "")
        block_name = lecture.get("block_name", "")
        full_path = f"{block_name} > {title}" if block_name else title
        candidates.append(
            {
                "id": lecture_id,
                "title": title,
                "block_name": block_name,
                "full_path": full_path,
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


def _fetch_lecture_metadata(lecture_ids: List[int]) -> Dict[int, Dict[str, str]]:
    if not lecture_ids:
        return {}
    sql = (
        text(
            """
        SELECT
            l.id AS lecture_id,
            l.title AS lecture_title,
            b.name AS block_name
        FROM lectures l
        JOIN blocks b ON b.id = l.block_id
        WHERE l.id IN :lecture_ids
        """
        ).bindparams(bindparam("lecture_ids", expanding=True))
    )
    rows = (
        db.session.execute(sql, {"lecture_ids": lecture_ids}).mappings().all()
    )
    lecture_map: Dict[int, Dict[str, str]] = {}
    for row in rows:
        lecture_id = row.get("lecture_id")
        if lecture_id is None:
            continue
        lecture_map[int(lecture_id)] = {
            "title": row.get("lecture_title") or "",
            "block_name": row.get("block_name") or "",
        }
    return lecture_map


def _chunk_relevance(chunk: Dict) -> float:
    if chunk.get("rrf_score") is not None:
        return float(chunk.get("rrf_score") or 0.0)
    if chunk.get("bm25_score") is not None:
        return float(chunk.get("bm25_score") or 0.0)
    return 0.0


def aggregate_candidates_rrf(
    chunks: List[Dict],
    top_k_lectures: int = 8,
    evidence_per_lecture: int = 3,
    **kwargs,
) -> List[Dict]:
    # Hybrid chunks already carry rrf_score, and aggregate_candidates handles it.
    return aggregate_candidates(
        chunks,
        top_k_lectures=top_k_lectures,
        evidence_per_lecture=evidence_per_lecture,
        **kwargs,
    )
