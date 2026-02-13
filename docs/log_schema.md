# Classification Pipeline Log Schema

## Per-Question JSONL Record (`run_log.jsonl`)

Each line is a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `question_id` | int | Question primary key |
| `question_text_len` | int | Character length of question + choices text |
| `question_text_tokens` | int | Rough token count (words + CJK chars) |
| `scope_subject` | string? | Subject of the exam this question belongs to |
| `candidates` | array | Top-K lecture candidates from retrieval |
| `candidates[].lecture_id` | int | Lecture ID |
| `candidates[].full_path` | string | "Block > Lecture" display path |
| `candidates[].rank` | int | 0-indexed rank in candidate list |
| `candidates[].score` | float | Retrieval score (BM25/RRF) |
| `candidates[].evidence_chunk_ids` | int[] | chunk IDs used as evidence snippets |
| `gold_lecture_id` | int | Ground truth lecture from evaluation labels |
| `gold_lecture_title` | string | Display title for gold lecture |
| `gold_in_candidates` | bool | Whether gold lecture appears in candidate set |
| `gold_rank` | int? | 0-indexed rank of gold in candidates (null if missing) |
| `llm_output.lecture_id` | int? | LLM's selected lecture |
| `llm_output.confidence` | float | LLM confidence 0.0–1.0 |
| `llm_output.no_match` | bool | LLM said no match |
| `llm_output.reason` | string | LLM's explanation (Korean) |
| `llm_output.evidence_count` | int | Number of evidence items returned |
| `apply_decision` | string | One of: `applied`, `no_match`, `no_lecture_id`, `out_of_candidates`, `low_confidence` |
| `apply_reason` | string | Human-readable reason for decision |
| `error_type` | string? | `retrieval_miss`, `judge_miss`, or null if correct |
| `latency_ms.retrieve` | float | Retrieval stage latency in ms |
| `latency_ms.judge` | float | LLM judge latency in ms |
| `latency_ms.total` | float | Total latency |
| `llm_retries` | int | Number of LLM retry attempts |
| `from_cache` | bool | Whether LLM result was from cache |

## Aggregated Summary (`summary.json`)

### Metrics

| Metric | Formula |
|---|---|
| `recall@K` | count(gold_rank < K) / total |
| `judge_accuracy_given_hit` | correct_llm_picks / questions_where_gold_in_candidates |
| `apply_precision` | correct_applied / total_applied |
| `apply_coverage` | total_applied / total_questions |

### Error Taxonomy

| Type | Condition |
|---|---|
| `retrieval_miss` | Gold lecture **not** in candidate set |
| `judge_miss` | Gold in candidates but LLM chose wrong |
