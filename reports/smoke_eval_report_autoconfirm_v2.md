# Smoke Eval Report: Auto-confirm v2

## Status
- Embedding queries failed in this environment (torch DLL load error), so full tuning/eval could not complete.
- Auto-confirm v2 defaults recorded for now; rerun tuning after fixing embedding runtime.

## Chosen Thresholds (current defaults)
- delta: 0.05
- max_bm25_rank: 5
- delta_uncertain: 0.03
- min_chunk_len: 200

## Metrics
- final_acc: N/A (eval skipped; embedding failure)
- auto_confirm_precision: N/A (tuning skipped; embedding failure)
- auto_confirm_coverage: N/A (tuning skipped; embedding failure)

## Next Steps
- Fix torch/sentence-transformers runtime.
- Rerun:
  - `python scripts/dump_retrieval_features.py --db data/dev.db --out reports/retrieval_features_evalset.csv`
  - `python scripts/tune_autoconfirm_v2.py --db data/dev.db --precision-target 0.86 --out reports/autoconfirm_v2_tuning.md`
  - `python scripts/evaluate_evalset.py --db data/dev.db --auto-confirm-delta <best> --auto-confirm-bm25-rank <best>`
