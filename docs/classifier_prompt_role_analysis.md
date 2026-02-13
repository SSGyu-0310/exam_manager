# AI 강의 분류기 로직/프롬프트 역할 분석 가이드

## 목적

- 프롬프트 문제와 파이프라인 문제(검색/후처리/적용 게이트)를 분리해서 진단한다.
- 프롬프트 수정 전후를 같은 조건에서 비교할 수 있도록 측정 항목을 고정한다.
- "강의 분류기"의 목적(정확한 강의 ID 선택 + 근거 제공 + 안전한 적용)에 맞는 프롬프트 계약을 정의한다.

## 현재 분류 파이프라인 요약 (코드 기준)

### 1) RETRIEVE: 후보 강의 검색

- 구현: `app/services/ai_classifier.py:255`, `app/services/retrieval.py:571`, `app/services/retrieval.py:682`
- 동작:
  - 문제 본문+선지를 합쳐 `question_text` 생성 (최대 4000자)
  - `RETRIEVAL_MODE`에 따라 BM25 또는 Hybrid RRF 검색
  - 강의 후보 최대 8개, 강의별 evidence 3개 제공
- 핵심 포인트:
  - Gold lecture가 후보 Top-K에 없으면 프롬프트가 아무리 좋아도 정답을 만들 수 없다.

### 2) EXPAND: 불확실할 때만 컨텍스트 확장

- 구현: `app/services/classification_pipeline.py:151`, `app/services/retrieval_features.py:137`, `app/services/context_expander.py:121`
- 동작:
  - retrieval feature로 `auto_confirm_v2`/`is_uncertain` 계산
  - 불확실한 케이스만 `parent_text`, `parent_page_ranges`를 후보에 추가
- 핵심 포인트:
  - Expanded Context는 일부 문제에만 붙는다.
  - 프롬프트는 "확장 컨텍스트가 있을 수도, 없을 수도 있음"을 전제로 설계돼야 한다.

### 3) JUDGE: LLM이 후보 중 1개 또는 no_match 결정

- 구현: `app/services/ai_classifier.py:319`, `app/services/ai_classifier.py:524`
- 동작:
  - 현재 프롬프트로 Gemini 호출 (`response_mime_type="application/json"`)
  - 결과를 JSON 파싱하고 실패 시 fallback 정규식 파싱

### 4) POST-PROCESS: 강제 보정/검증

- 구현: `app/services/ai_classifier.py:123`, `app/services/ai_classifier.py:167`, `app/services/ai_classifier.py:569`
- 동작:
  - `lecture_id` 타입 보정
  - reason/study_hint에서 lecture id 재추출
  - 후보 목록 밖 lecture_id는 무효 처리
  - evidence는 선택된 후보의 chunk/snippet과 일치할 때만 정규화
- 핵심 포인트:
  - 프롬프트 출력이 부정확하면 후처리에서 빈 evidence/no_match로 떨어질 수 있다.

### 5) APPLY: 실제 분류 반영 게이트

- 구현: `app/services/ai_classifier.py:915`
- 동작:
  - `AI_CONFIDENCE_THRESHOLD + AI_AUTO_APPLY_MARGIN` 이상일 때만 자동 반영
  - out-of-candidate는 `needs_review`로 처리
  - no_match는 자동 반영 제외
- 핵심 포인트:
  - confidence calibration이 나쁘면 자동 반영 품질이 급격히 흔들린다.

## 현재 프롬프트의 강점과 한계

### 강점

- 출력 스키마를 명시해서 구조화 데이터를 유도한다.
- `no_match`와 `evidence`를 강제해 감사 가능한 결과를 만들려는 의도가 있다.
- `study_hint`에 페이지 기반 학습 힌트를 요구한다.

### 한계

- 판단 규칙이 추상적이다.
  - "key concept"만으로는 동형 개념(유사 강의) 구분 기준이 부족하다.
- 후보 제한 규칙이 약하다.
  - "반드시 후보 ID 중 하나만 선택"이 강하게 명시돼 있지 않다.
- no_match 기준이 모호하다.
  - "근거가 약한 경우"와 "정말 해당 강의 없음"을 구분하는 규칙이 없다.
- confidence 기준이 없다.
  - 0.6과 0.9를 언제 주는지 기준이 없어 auto-apply 품질이 불안정해진다.
- evidence 정합성 제약이 약하다.
  - quote/chunk/page를 후보 증거와 정확히 맞추는 규칙이 없어 후처리에서 많이 탈락할 수 있다.
- JSON 강제 수준이 약하다.
  - 코드블록/설명문이 섞이면 fallback 파서 의존도가 올라간다.

## 프롬프트와 코드의 역할 분리 (권장 계약)

### 프롬프트가 반드시 해야 할 일

- 후보 강의 중 1개 선택 또는 no_match 선언
- 선택 근거를 후보 evidence와 연결
- confidence를 규칙 기반으로 산정
- 사람이 재검토할 수 있는 `reason`/`study_hint` 생성

### 프롬프트가 하면 안 되는 일

- 후보 밖 강의 ID 추측
- 임계값/자동반영 정책 결정
- DB 상태/메타데이터 변경 의사결정
- 출력 스키마 임의 확장

### 코드가 반드시 보장해야 할 일

- 후보 제한, 타입 보정, evidence 정규화
- out-of-candidate/no_match 안전 처리
- auto-apply gate와 감사 로그

## "뭘 분석하면 되지?"에 대한 실전 체크리스트

## 1) 검색 상한 진단 (프롬프트 무관)

- 지표:
  - Top-1/3/5/10에 gold lecture 포함률
  - Top-10 miss 사례 수
- 목적:
  - 프롬프트 개선으로 해결 불가능한 케이스 분리

## 2) 프롬프트 판단 품질

- 지표:
  - final accuracy (`ai_final_lecture_id` 기준)
  - raw suggestion accuracy (`ai_suggested_lecture_id` 기준)
  - out-of-candidate rate (`out_of_candidate`, `out_of_candidate_final`)
  - no_match rate 및 오판 케이스

## 3) confidence calibration

- 지표:
  - confidence bin별 정확도 (예: 0.0-0.2, ..., 0.8-1.0)
  - auto gate 통과 샘플의 precision
- 목적:
  - threshold/margin을 튜닝 가능한 신뢰도로 만들기

## 4) evidence 품질

- 지표:
  - `no_match=false`인데 evidence가 비는 비율
  - evidence의 chunk_id 유효 비율
  - quote가 snippet/expanded context와 실제 매칭되는 비율
  - page_start/page_end 유효 비율

## 5) 운영 지표

- 지표:
  - LLM 실패율(JSON parse fallback 비율)
  - 평균 응답 시간
  - 재시도율/예외율

## 평가 실행 예시

기본 평가:

```bash
python scripts/evaluate_evalset.py --db "$DATABASE_URL"
```

실제 분류기 실행 포함:

```bash
python scripts/evaluate_evalset.py \
  --db "$DATABASE_URL" \
  --run-classifier \
  --retrieval-mode hybrid_rrf \
  --max-workers 4
```

불확실 케이스만 점검:

```bash
python scripts/evaluate_evalset.py \
  --db "$DATABASE_URL" \
  --run-classifier \
  --only-uncertain
```

## 개선 프롬프트 템플릿 (분류기 목적 맞춤)

아래 템플릿은 "후보 제한 + 근거 정합성 + confidence 기준"을 강화한 버전이다.

```python
prompt = f"""You are a medical lecture classifier for exam questions.

Task:
Choose exactly one lecture from Candidate Lectures, or return no_match=true.

Input:
- Question: {question_content}
- Choices: {choices_text}
- Candidate Lectures with evidence: {candidates_text}

Decision Rules (strict):
1) You MUST select from candidate lecture IDs only.
2) Choose a lecture only when the core concept, mechanism, or diagnostic/therapeutic logic is directly supported by candidate evidence.
3) If evidence is weak, conflicting, or too generic across candidates, set no_match=true and lecture_id=null.
4) confidence rubric:
   - 0.85~1.00: one candidate has direct and specific evidence, alternatives are clearly weaker
   - 0.60~0.84: likely match but alternatives still plausible
   - 0.00~0.59: weak match or uncertain (prefer no_match)
5) reason must be short Korean text and include why alternatives are weaker.
6) study_hint must include exact page range from selected evidence (e.g., "p.12-13").
7) evidence rules:
   - If no_match=true, evidence must be [].
   - If no_match=false, include 1~3 evidence items from the selected lecture only.
   - quote must be copied from given evidence text (verbatim snippet).
   - page_start/page_end/chunk_id must match provided evidence.
8) Return valid JSON only. No markdown, no extra keys, no explanation outside JSON.

Output JSON schema:
{{
  "lecture_id": 123 or null,
  "confidence": 0.0,
  "reason": "짧은 한국어 근거",
  "study_hint": "p.12-13 중심으로 핵심 개념과 유사 개념을 비교",
  "no_match": false,
  "evidence": [
    {{
      "lecture_id": 123,
      "page_start": 12,
      "page_end": 13,
      "quote": "exact snippet text",
      "chunk_id": 991
    }}
  ]
}}
"""
```

## 프롬프트 변경 시 최소 수용 기준 (Acceptance)

- out-of-candidate rate가 증가하지 않을 것
- no_match=false 케이스의 evidence 유효율이 유지 또는 개선될 것
- auto gate 통과 샘플 precision이 baseline 이상일 것
- 최종 정확도(`ai_final_lecture_id`)가 baseline 이상일 것

## 참고 코드 위치

- 프롬프트 생성: `app/services/ai_classifier.py:319`
- 파싱/보정: `app/services/ai_classifier.py:123`
- 후보 검색: `app/services/ai_classifier.py:255`
- 불확실성 판정: `app/services/retrieval_features.py:157`
- 컨텍스트 확장: `app/services/context_expander.py:121`
- 적용 게이트: `app/services/ai_classifier.py:915`
- 평가 스크립트: `scripts/evaluate_evalset.py:220`

## 점검 메모

- `LectureRetriever.find_candidates`는 `retrieval.aggregate_candidates_rrf`를 호출한다 (`app/services/ai_classifier.py:284`).
- 현재 `app/services/retrieval.py`에서 동일 이름 함수 정의를 바로 확인하기 어렵다.
- hybrid 경로를 실제 사용 중이라면 이 연결 상태를 먼저 점검해야 프롬프트 실험 결과를 정확히 해석할 수 있다.
