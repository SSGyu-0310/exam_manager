# Ops Smoke + Regression Report (dev DB)

## 0) Environment
- python: 3.12.4 (Anaconda, MSC v.1929, AMD64)
- platform: Windows-11-10.0.26100-SP0
- processor: AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD
- cpu_count: 16
- HF cache: C:\Users\SS_Gyu\.cache\huggingface\hub
- torch import: FAILED: WinError 1114 (c10.dll)

## 1) Migrations / Embeddings / FTS
- ran: `python scripts/run_migrations.py --db data/dev.db` -> OK (0 applied)
- ran: `python scripts/build_embeddings.py --db data/dev.db --rebuild` -> FAILED (WinError 1114 loading torch c10.dll)
- counts (after failure): lecture_chunks=877, lecture_chunk_embeddings=877 (existing hashing-512-v1)
- sample rows: model_name=hashing-512-v1, embedding_bytes=2048 (dim=512)
- ran: `python scripts/init_fts.py --db data/dev.db --rebuild` -> OK (877 chunks)

## 2) Retrieval smoke (3 questions)
- Q576 bm25: [20,1,5,19,18] / hybrid_rrf: [20,4,18,5,9]
- Q577 bm25: [20,5,9,3,7] / hybrid_rrf: [20,18,5,3,16]
- Q578 bm25: [3,16,20,4,11] / hybrid_rrf: [3,16,20,18,13]
- embedding load failed (torch DLL) -> hybrid_rrf fell back to BM25-only rerank (rank changes due to RRF aggregation, not embeddings)
- fallback check (bad model name) -> hybrid_rrf returned candidates (BM25 fallback OK)

## 3) Evalset regression
- bm25 command: `python scripts/evaluate_evalset.py --db data/dev.db --retrieval-mode bm25` -> OK (reports/eval_20260115_073942)
- hybrid command (sentence-transformers default): `python scripts/evaluate_evalset.py --db data/dev.db --retrieval-mode hybrid_rrf` -> TIMEOUT (torch DLL error spam)
- hybrid rerun (hashing fallback): `EMBEDDING_MODEL_NAME=hashing-512-v1 EMBEDDING_DIM=512 python scripts/evaluate_evalset.py --db data/dev.db --retrieval-mode hybrid_rrf` -> OK (reports/eval_20260115_074225)

| Metric | BM25 | hybrid_rrf (hashing fallback) |
| --- | --- | --- |
| Top-1 | 112 (0.467) | 62 (0.258) |
| Top-3 | 205 (0.854) | 192 (0.800) |
| Top-5 | 224 (0.933) | 222 (0.925) |
| Top-10 | 237 (0.988) | 234 (0.975) |
| MRR | 0.674 | 0.544 |
| Final accuracy | 177/240 (0.738) | 177/240 (0.738) |
| Auto-confirm precision (thr 0.7+0.2) | 0.864 (152/176) | 0.859 (152/177) |
| out_of_candidate_rate_raw | 0.104 | 0.100 |
| out_of_candidate_rate_final | 0.087 | 0.087 |

Conclusion: hybrid_rrf did NOT improve Top-1/MRR vs bm25 in the hashing fallback run (Top-1/MRR decreased).

## 4) Safety guards
- HARD_CANDIDATE_ACTION=needs_review -> ai_final_lecture_id=None, status=needs_review (OK)
- HARD_CANDIDATE_ACTION=clamp_top1 -> ai_final_lecture_id=top1 candidate, status=needs_review (OK)
- DB_READ_ONLY=1 -> GET allowed, POST blocked with 503 (OK)
- pending migrations detection -> warning emitted; FAIL_ON_PENDING_MIGRATIONS=1 in production raises RuntimeError (OK)

## 5) Failures / Notes
- sentence-transformers could not import torch: WinError 1114 loading c10.dll (CPU-only run blocked)
- embedding build did not run; lecture_chunk_embeddings still hashing-512-v1
- hybrid_rrf evaluation with real model could not complete due to torch DLL errors

## 6) Hypotheses if hybrid does not improve (once torch works)
1) Model/prefix/normalize mismatch (E5 requires query:/passage: prefixes + L2 normalize).
2) Rerank pool too small (EMBEDDING_TOP_N=300 may miss gold candidates).
3) Query normalization too aggressive for numbers/units (tokenization may drop crucial units).
Recommended next experiment: increase EMBEDDING_TOP_N to 500 and rebuild embeddings, then re-run eval.