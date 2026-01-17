# HyDE-lite Iteration 2 (Evalset-only)

## Evalset IDs
- Derived from `evaluation_labels` where `gold_lecture_id IS NOT NULL` and `is_ambiguous = 0`
- Saved to `evalset_question_ids.txt` (240 ids)

## HyDE cache build (evalset only)
- Command: `python scripts/build_queries.py --provider gemini --concurrency 10 --force --question-ids-file evalset_question_ids.txt`
- Result: success=240, failed=0, cached=240

## Experiment matrix
| Run | Top-1 | MRR | Final acc | Auto-confirm precision | out_raw | out_final |
| --- | --- | --- | --- | --- | --- | --- |
| results_evalset_best_of_two | 0.592 | 0.743 | 0.738 | 0.840 (152/181) | 0.075 | 0.058 |
| results_evalset_bm25_hyde_only | 0.263 | 0.277 | 0.738 | 0.895 (51/57) | 0.725 | 0.725 |
| results_evalset_bm25_mixed_light | 0.575 | 0.723 | 0.738 | 0.831 (152/183) | 0.050 | 0.042 |
| results_evalset_bm25_orig_only | 0.600 | 0.747 | 0.738 | 0.836 (153/183) | 0.067 | 0.054 |
| results_evalset_weights_0p0_1p0 | 0.575 | 0.722 | 0.738 | 0.831 (152/183) | 0.058 | 0.050 |
| results_evalset_weights_0p3_0p7 | 0.575 | 0.723 | 0.738 | 0.831 (152/183) | 0.050 | 0.042 |
| results_evalset_weights_0p5_0p5 | 0.571 | 0.719 | 0.738 | 0.836 (153/183) | 0.050 | 0.037 |
| results_evalset_weights_0p7_0p3 | 0.567 | 0.712 | 0.738 | 0.831 (152/183) | 0.054 | 0.042 |
| results_evalset_weights_1p0_0p0 | 0.542 | 0.697 | 0.738 | 0.830 (151/182) | 0.054 | 0.042 |

## Analysis
- Embedding blend sweep (mixed_light BM25) peaks at 0.3/0.7 but does not beat orig-only BM25.
- BM25_HYDE_ONLY is severely harmful (Top-1/MRR collapse + high out_of_candidate).
- BM25_ORIG_ONLY + HyDE embedding blend gives best Top-1/MRR overall.
- Best-of-two improves over mixed_light but still below orig-only BM25 variant.

## Recommendation
- Set `HYDE_BM25_VARIANT=orig_only` to avoid candidate drift from HyDE keywords.
- Keep embedding blend at `HYDE_EMBED_WEIGHT=0.3` and `HYDE_EMBED_WEIGHT_ORIG=0.7`.
- Keep `HYDE_STRATEGY=blend` (best-of-two not superior to orig-only BM25 in this run).

## Next follow-ups
- If HyDE still underperforms, consider disabling negative keyword stopwords or tightening HyDE prompt.
- Re-tune auto-confirm thresholds after stabilizing retrieval changes.