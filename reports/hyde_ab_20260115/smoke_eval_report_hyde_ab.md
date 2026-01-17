# HyDE-lite A/B Eval Report (dev.db)

## Environment
- python: 3.12.4 (Anaconda, MSC v.1929, AMD64)
- torch: 2.3.1+cpu
- numpy: 1.26.4
- HF cache: C:\Users\SS_Gyu\.cache\huggingface\hub

## DB / Migration
- backup: `reports/hyde_ab_20260115/dev.db.bak`
- applied migration: `20260115_1930_question_queries.sql`
- table check: question_queries + idx_question_queries_question_id OK

## HyDE cache build
- command: `python scripts/build_queries.py --provider gemini --concurrency 10 --skip-existing`
- result: questions=1177, cached=1177, failed=0

## Eval (HyDE OFF vs ON, hybrid_rrf)
- OFF report: `reports/hyde_ab_20260115/results_off/summary.json`
- ON report: `reports/hyde_ab_20260115/results_on/summary.json`

| Metric | OFF | ON |
| --- | --- | --- |
| Top-1 | 0.588 | 0.500 |
| Top-3 | 0.863 | 0.812 |
| Top-5 | 0.942 | 0.912 |
| Top-10 | 0.992 | 0.963 |
| MRR | 0.737 | 0.670 |
| Final accuracy | 0.738 | 0.738 |
| Auto-confirm precision | 0.836 (153/183) | 0.843 (150/178) |
| out_of_candidate_rate_raw | 0.075 | 0.079 |
| out_of_candidate_rate_final | 0.058 | 0.062 |

Interpretation: HyDE ON decreased Top-1/MRR vs OFF in this run, while final accuracy is unchanged and auto-confirm precision slightly improved.

## Next actions
- Check HyDE prompt quality and negative keywords; consider lowering HYDE_EMBED_WEIGHT or disabling negative terms in BM25.
- Run a small weight sweep (0.3/0.7, 0.5/0.5, 0.7/0.3) for embedding blend.