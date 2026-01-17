# HyDE-lite Query Transformation 도입 보고서

## 1. 목적 (Why)

기출문제(Query)와 강의록(Document) 간의 **형태적·의미적 비대칭성**으로 인해  
기존 BM25 + embedding 기반 retrieval에서 발생하는 한계를 개선하기 위해  
HyDE-lite(Query Transformation) 기법을 도입하고 실제 성능 영향을 검증한다.

목표는 다음과 같다.

- 문제 텍스트를 수정하지 않고, **검색 전용 Query**를 추가 생성
- retrieval 성능(Top-1, MRR) 및 안정성(out_of_candidate) 개선 여부 검증
- auto-confirm precision에 미치는 영향 평가
- 실패 시에도 기존 파이프라인이 깨지지 않는 **옵션형 모듈**로 통합

---

## 2. 기존 파이프라인 (Baseline)

- 데이터
  - 파싱된 기출문제(question_text)
  - 청킹된 강의록(chunk_text)
- Retrieval
  - BM25(FTS) → 후보 생성
  - sentence-transformer(E5) → 재정렬
  - hybrid RRF
- Decision
  - auto-confirm / AI decision

Baseline 성능(dev / evalset 기준):
- Top-1 ≈ 0.59
- MRR ≈ 0.74
- Final accuracy ≈ 0.738
- auto-confirm precision ≈ 0.83~0.86

---

## 3. HyDE-lite 설계 및 구현

### 3.1 개념
- LLM(Gemini)을 사용해 **문제 텍스트를 ‘강의록 검색에 적합한 형태’로 재표현**
- 정답 추론/선지 선택은 절대 금지
- 생성 결과는 **검색 전용**이며 decision 단계에 직접 사용하지 않음

### 3.2 생성 결과 형식
- Keywords (BM25용)
- Lecture-style query (Embedding용)
- Negative keywords (선택적)

### 3.3 구현 포인트
- 캐시 테이블: `(question_id, prompt_version)` composite PK
- 오프라인 배치 CLI 제공
- HyDE 비활성화 시 기존 파이프라인과 **완전히 동일한 동작**
- 실패/누락 시 원문 query로 안전한 fallback

---

## 4. 1차 실험: 전체 데이터셋 A/B

### 실험 설정
- OFF: HyDE 비활성화
- ON: HyDE 활성화 (BM25 확장 + embedding 블렌딩)

### 결과 요약 (hybrid_rrf)
- HyDE ON:
  - Top-1, MRR **하락**
  - Final accuracy 동일
  - auto-confirm precision 소폭 상승

해석:
- HyDE가 retrieval 품질을 저하시킬 가능성 관측
- 원인 분리를 위한 추가 실험 필요

---

## 5. 2차 실험: evalset 전용 정밀 분석 (≈240문항)

### 실험 목적
- HyDE의 부작용 원인이
  - embedding 블렌딩인지
  - BM25 후보 드리프트인지
  - 혹은 둘 다인지 분리

### 실험 설계
- evalset question_id만 대상으로 제한
- HyDE 캐시 생성 / 평가 모두 evalset 전용
- 실험 항목:
  1. Embedding 블렌딩 가중치 스윕
  2. BM25 query 구성 방식 비교
  3. best-of-two(비블렌딩 경쟁 전략)

---

## 6. 2차 실험 결과 요약 (evalset-only)

### Best overall
**BM25_ORIG_ONLY**
- Top-1: 0.600
- MRR: 0.747
- Final acc: 0.738
- auto-confirm: 0.836
- out_raw: 0.067

### Embedding 블렌딩
- 최선: HYDE=0.3 / ORIG=0.7
- 그러나 baseline(BM25_ORIG_ONLY)보다 낮음

### Best-of-two
- Top-1: 0.592
- MRR: 0.743
- baseline 미달

### BM25_HYDE_ONLY
- Top-1: 0.263
- out_raw: 0.725
- **치명적 후보 드리프트 발생**

---

## 7. 핵심 결론

1. **BM25 후보 생성에는 원문 기출문제가 가장 강력**
2. HyDE 키워드는 BM25 단계에서 심각한 후보 드리프트를 유발
3. Embedding 단계에서조차 HyDE는 보조 신호로만 제한적으로 유효
4. 본 데이터셋(의학 기출문제)은
   - 자연어 QA 문제가 아니라
   - **전문 용어 정합(recall) 문제가 핵심**

즉,

> HyDE는 이 데이터에서 **retrieval 개선 도구가 아니라,  
> 잘못 쓰면 성능을 망치는 노이즈 소스**임이 실험적으로 확인되었다.

---

## 8. 최종 권장 설정

```text
HYDE_BM25_VARIANT = orig_only
HYDE_EMBED_WEIGHT = 0.3
HYDE_EMBED_WEIGHT_ORIG = 0.7
HYDE_STRATEGY = blend
