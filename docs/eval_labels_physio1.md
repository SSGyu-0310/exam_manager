# P0 Evaluation – 생리학 1차 Gold Labels

> **Scope**: 이 문서는 "생리학 1차" 블록에 속한 문제 subset에 대한 평가 결과입니다.
> 생리학 2차 데이터는 gold로 포함하지 않았습니다.

## 1. Gold Label 정책

| 항목 | 내용 |
|---|---|
| 대상 블록 | `blocks.id = 1`, name = `생리학1차` |
| 강의 수 | 10개 (물질이동, 전기적현상, 심장, 순환, 근육, 소화, 혈액, 체온, 운동, 호흡) |
| 문제 수 | **479문제** |
| Gold label 값 | `questions.lecture_id` (사용자 확인 분류값) |
| Source tag | `evaluation_labels.source = 'gold_physio1'` |
| 제외 대상 | 생리학 2차 (block_id=2), ai_final_lecture_id만 있는 문제 |

### 추출 SQL

```sql
SELECT q.id, q.exam_id, q.question_number, q.lecture_id AS gold_lecture_id
FROM questions q
JOIN lectures l ON q.lecture_id = l.id
JOIN blocks b ON l.block_id = b.id
WHERE b.name = '생리학1차'
  AND q.lecture_id IS NOT NULL;
```

## 2. Backfill 실행

```bash
# Dry-run (확인만)
docker compose exec api python scripts/backfill_eval_labels.py \
    --block-name "생리학1차" --source gold_physio1 --dry-run true

# 실제 실행
docker compose exec api python scripts/backfill_eval_labels.py \
    --block-name "생리학1차" --source gold_physio1 --dry-run false
```

### 실행 결과

| 항목 | 값 |
|---|---|
| 삽입 | 479건 |
| 스킵 (기존) | 0건 |
| 결측 (lecture_id 없음) | 0건 |
| 재실행 시 스킵 | 479건 (idempotent 확인) |

## 3. Baseline 평가 결과 (BM25, Retrieval Only)

> 실행 시각: 2026-02-11T05:33:29Z
> LLM 호출 없음 (retrieval-only baseline)

### Configuration

| Parameter | Value |
|---|---|
| Retrieval Mode | BM25 (Postgres FTS) |
| Top-K Lectures | 8 |
| Evidence/Lecture | 3 |
| PARENT_ENABLED | false |
| TRGM_ENABLED | false |

### Recall@K

| K | Rate | Count (/479) |
|---|---|---|
| @1 | **0.113** | 54 |
| @3 | **0.495** | 237 |
| @5 | **0.656** | 314 |
| @8 | **0.781** | 374 |
| @10 | 0.781 | 374 |
| @12 | 0.781 | 374 |
| @16 | 0.781 | 374 |

> ⚠️ Recall@8 = Recall@16 이므로 top_k를 8 이상으로 올려도 추가 이득이 없음.
> **105문제(21.9%)는 BM25 top-80 결과에 gold lecture가 전혀 포함되지 않음** → retrieval 자체의 한계.

### Classification Metrics (기존 cached 결과 기반)

| Metric | Value |
|---|---|
| Judge Accuracy (Given-hit) | **93.6%** (350/374) |
| Apply Precision | **96.7%** (349/361) |
| Apply Coverage | 75.4% (361/479) |
| no_match Count | 7 |

### Error Decomposition

| Error Type | Count | 비율 |
|---|---|---|
| Retrieval Miss | 5 | 17.2% of errors |
| Judge Miss | 24 | 82.8% of errors |

### Latency (Retrieval Only)

| Stage | Mean | p50 | p95 |
|---|---|---|---|
| Retrieve (BM25) | 477ms | 443ms | **821ms** |
| Judge (LLM) | — | — | — |
| Total | 477ms | — | 821ms |

### 실행 명령

```bash
docker compose exec api python scripts/eval_classifier_run.py \
    --labels-source gold_physio1 \
    --output-dir reports/baseline_physio1 \
    --retrieval-mode bm25
```

## 4. Key Findings & Bottlenecks

### ✅ 강점
- **Judge Accuracy 93.6%**: gold lecture가 후보에 포함되면, LLM 분류는 매우 정확
- **Apply Precision 96.7%**: 확정된 분류는 거의 항상 정답

### ⚠️ 병목
1. **Recall 한계**: BM25 top-8에 gold가 포함되는 비율이 78.1%에 불과  
   → top-8에서 top-16으로 올려도 동일 (saturation)
2. **Retrieval Miss (105문제)**: 전체 문제의 21.9%는 BM25 검색 자체에서 gold lecture를 찾지 못함
3. **Judge Miss (24건)**: 후보에 gold가 있었지만 LLM이 다른 강의를 선택한 케이스

### 🔧 P1 개선 방향 제안
1. TRGM fallback 활성화 → retrieval miss 감소 기대
2. Hybrid RRF 모드 테스트 → BM25 단독 대비 recall 향상 가능성
3. Evidence snippet 수 증가 (3→5) → judge accuracy 개선 가능

## 5. 제한점

- **생리학 1차 subset에 대한 지표**이며, 전체 과목 성능을 대표하지 않음
- Gold label은 `questions.lecture_id` (사용자 분류 확정값) 기반이므로 일부 오류가 포함될 수 있음
- LLM judge 호출 없이 기존 cached 결과로 계산된 classification metrics임
- 생리학 2차 데이터는 의도적으로 제외됨

## 6. 생성 파일

| File | Description |
|---|---|
| `reports/baseline_physio1/summary.json` | 집계 지표 JSON |
| `reports/baseline_physio1/run_log.jsonl` | 문제별 상세 로그 (479 lines) |
| `reports/baseline_physio1/baseline_run.md` | 베이스라인 보고서 |
| `reports/baseline_physio1/errors_top50.md` | 에러 상위 50건 |
