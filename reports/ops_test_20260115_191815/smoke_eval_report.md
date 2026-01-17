# Ops Smoke + Regression Report (dev DB, rerun)

## 0) Environment
- python: 3.12.4 (Anaconda, MSC v.1929, AMD64)
- platform: Windows-11-10.0.26100-SP0
- processor: AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD
- cpu_count: 16
- torch: 2.3.1+cpu (cuda_available=False)
- HF cache: C:\Users\SS_Gyu\.cache\huggingface\hub

## 1) Migrations / Embeddings / FTS
- ran: `python scripts/run_migrations.py --db data/dev.db` -> OK (0 applied)
- ran: `python scripts/build_embeddings.py --db data/dev.db --rebuild` -> OK (long-running)
- counts: lecture_chunks=877, lecture_chunk_embeddings=877
- sample rows: model_name=intfloat/multilingual-e5-base, embedding_bytes=3072 (dim=768)
- ran: `python scripts/init_fts.py --db data/dev.db --rebuild` -> OK (877 chunks)

## 2) Evalset regression
- bm25: `reports/eval_20260115_095814/summary.json`
- hybrid_rrf (sentence-transformers): `reports/eval_20260115_101612/summary.json`

| Metric | BM25 | hybrid_rrf (E5) |
| --- | --- | --- |
| Top-1 | 112 (0.467) | 141 (0.588) |
| Top-3 | 205 (0.854) | 207 (0.863) |
| Top-5 | 224 (0.933) | 226 (0.942) |
| Top-10 | 237 (0.988) | 238 (0.992) |
| MRR | 0.674 | 0.737 |
| Final accuracy | 177/240 (0.738) | 177/240 (0.738) |
| Auto-confirm precision (thr 0.7+0.2) | 0.864 (152/176) | 0.836 (153/183) |
| out_of_candidate_rate_raw | 0.104 | 0.075 |
| out_of_candidate_rate_final | 0.087 | 0.058 |

Conclusion: hybrid_rrf improves Top-1 and MRR vs bm25, while final accuracy is unchanged; auto-confirm precision dipped slightly.