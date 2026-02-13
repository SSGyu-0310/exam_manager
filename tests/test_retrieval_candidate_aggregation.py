from app import db
from app.models import Block, Lecture
from app.services import retrieval


def _seed_two_lectures():
    block = Block(name="Physiology")
    db.session.add(block)
    db.session.flush()
    lecture_a = Lecture(block_id=block.id, title="A", order=1)
    lecture_b = Lecture(block_id=block.id, title="B", order=2)
    db.session.add_all([lecture_a, lecture_b])
    db.session.commit()
    return lecture_a, lecture_b


def test_aggregate_candidates_keeps_evidence_fields_and_ranks_by_score(app):
    with app.app_context():
        lecture_a, lecture_b = _seed_two_lectures()

        chunks = [
            {
                "chunk_id": 101,
                "lecture_id": lecture_a.id,
                "page_start": 3,
                "page_end": 4,
                "snippet": "alpha",
                "bm25_score": 1.2,
            },
            {
                "chunk_id": 102,
                "lecture_id": lecture_a.id,
                "page_start": 7,
                "page_end": 7,
                "snippet": "beta",
                "bm25_score": 0.8,
            },
            {
                "chunk_id": 201,
                "lecture_id": lecture_b.id,
                "page_start": 11,
                "page_end": 12,
                "snippet": "gamma",
                "bm25_score": 3.0,
            },
        ]

        candidates = retrieval.aggregate_candidates(
            chunks,
            top_k_lectures=2,
            evidence_per_lecture=2,
        )

        assert len(candidates) == 2
        assert candidates[0]["id"] == lecture_b.id
        evidence = candidates[0]["evidence"][0]
        assert evidence["chunk_id"] == 201
        assert evidence["page_start"] == 11
        assert evidence["page_end"] == 12
        assert isinstance(evidence["snippet"], str)


def test_aggregate_candidates_rrf_available_and_uses_rrf_score(app):
    with app.app_context():
        lecture_a, lecture_b = _seed_two_lectures()

        chunks = [
            {
                "chunk_id": 101,
                "lecture_id": lecture_a.id,
                "page_start": 1,
                "page_end": 1,
                "snippet": "alpha",
                "rrf_score": 0.20,
            },
            {
                "chunk_id": 201,
                "lecture_id": lecture_b.id,
                "page_start": 2,
                "page_end": 2,
                "snippet": "beta",
                "rrf_score": 0.10,
            },
        ]

        candidates = retrieval.aggregate_candidates_rrf(
            chunks,
            top_k_lectures=2,
            evidence_per_lecture=1,
        )

        assert candidates[0]["id"] == lecture_a.id


def test_build_match_query_postgres_websearch_uses_or(monkeypatch):
    monkeypatch.setattr(retrieval, "_pg_query_mode", lambda: "websearch")
    query = retrieval._build_match_query(
        ["stem", "cell", "differentiation"],
        max_terms=8,
        mode="OR",
        backend="postgres",
    )

    assert " OR " in query
    assert "stem" in query
