# AI 자동분류 파이프라인 로직 분석

> **목적**: 문제(Question)가 어떤 강의(Lecture)에 해당하는지 AI가 자동으로 분류하는 전체 흐름을 설명합니다.
> 현재 Docker 환경(`.env.docker`)의 설정 기준으로 분석합니다.

---

## 1. 전체 파이프라인 흐름도

```mermaid
flowchart TD
    START["🚀 분류 시작<br/>AsyncBatchProcessor.start_classification_job()"]
    
    subgraph PREP["📋 전처리"]
        Q_LOAD["Question 로드<br/>question.content + choices"]
        Q_TEXT["question_text 조합<br/>content + choices (최대 4000자)"]
    end
    
    subgraph STAGE1["🔍 Stage 1: RETRIEVE — 후보 강의 검색"]
        CACHE["LectureRetriever.refresh_cache()<br/>전체 강의 목록 메모리 캐시"]
        SCOPE["scope 필터 적용<br/>block_id / folder_id → lecture_ids"]
        BM25["search_chunks_bm25()<br/>Postgres ts_rank_cd 검색"]
        AGG["aggregate_candidates()<br/>상위 8개 강의로 집계"]
    end
    
    subgraph STAGE2["🔄 Stage 2: EXPAND — 컨텍스트 확장 (조건부)"]
        PARENT_CHECK{"PARENT_ENABLED?<br/>(.env.docker: OFF)"}
        UNCERTAIN{"is_uncertain()?"}
        EXPAND["expand_candidates()<br/>semantic neighbors 확장"]
        SKIP_EXPAND["확장 없이 통과"]
    end
    
    subgraph STAGE3["🤖 Stage 3: JUDGE — LLM 분류 판정"]
        PROMPT["프롬프트 구축<br/>question + choices + candidates"]
        LLM["Gemini API 호출<br/>temperature=0.2"]
        PARSE["JSON 파싱<br/>+ fallback 파싱"]
        VALIDATE["결과 검증<br/>lecture_id ∈ valid_ids?"]
        EVIDENCE["evidence 정규화<br/>_normalize_evidence()"]
        EVID_CHECK{"evidence 있음?"}
        FORCE_NO["❌ no_match = true<br/>lecture_id = null"]
        RESULT["✅ 분류 결과 생성"]
    end
    
    subgraph APPLY["📝 결과 적용 (apply_classification_results)"]
        THRESH{"confidence ≥ threshold?<br/>(0.7)"}
        DB_WRITE["DB 반영<br/>question.lecture_id = 선택된 강의"]
        SUGGEST["ai_suggested로만 저장<br/>(미적용)"]
    end
    
    START --> Q_LOAD --> Q_TEXT
    Q_TEXT --> CACHE --> SCOPE --> BM25 --> AGG
    AGG --> PARENT_CHECK
    PARENT_CHECK -->|"OFF (현재)"| SKIP_EXPAND
    PARENT_CHECK -->|"ON"| UNCERTAIN
    UNCERTAIN -->|"Yes"| EXPAND
    UNCERTAIN -->|"No"| SKIP_EXPAND
    EXPAND --> PROMPT
    SKIP_EXPAND --> PROMPT
    PROMPT --> LLM --> PARSE --> VALIDATE
    VALIDATE --> EVIDENCE --> EVID_CHECK
    EVID_CHECK -->|"없으면"| FORCE_NO
    EVID_CHECK -->|"있으면"| RESULT
    FORCE_NO --> SUGGEST
    RESULT --> THRESH
    THRESH -->|"Yes + apply_mode=all"| DB_WRITE
    THRESH -->|"No"| SUGGEST
```

---

## 2. 각 단계 상세 설명

### 2.1 전처리 (Question Text 조합)

**파일**: `ai_classifier.py` (라인 936-945)

```python
question_text = question.content or ""
if choices:
    question_text = f"{question_text}\n" + " ".join(choices)
question_text = question_text.strip()
if len(question_text) > 4000:
    question_text = question_text[:4000]
```

- 문제 본문(`content`)과 선지(`choices`)를 합쳐서 검색용 텍스트를 만듦
- **⚠️ 실패 가능성**: `content`가 이미지 전용(`None` 또는 빈 문자열)이면 검색 텍스트가 거의 없어서 BM25 검색이 실패함

---

### 2.2 Stage 1: RETRIEVE (후보 강의 검색)

**파일**: `ai_classifier.py` → `retrieval.py`

현재 Docker 설정:
| 설정 | 값 | 출처 |
|------|-----|------|
| `RETRIEVAL_MODE` | `bm25` | `.env.docker` |
| `SEARCH_BACKEND` | `postgres` | `.env.docker` |
| `SEARCH_PG_QUERY_MODE` | `websearch` | `.env.docker` |
| `SEARCH_PG_TRGM_ENABLED` | `0` (OFF) | `.env.docker` |


```mermaid
flowchart TD
    INPUT["question_text 입력"]
    
    subgraph TOKENIZE["토큰화"]
        TOKEN["_normalize_query()<br/>한글/영어/숫자 토큰 추출"]
        STOP["불용어 제거<br/>다음, 중, 옳은, 틀린, 것 등"]
        BUILD["_build_pg_websearch_query()<br/>Postgres websearch 쿼리 생성"]
    end
    
    subgraph SEARCH["검색 실행"]
        PG_SEARCH["_search_chunks_bm25_postgres()<br/>content_tsv @@ websearch_to_tsquery()"]
        FALLBACK1["8-term fallback 쿼리"]
        FALLBACK2["4-term fallback 쿼리"]
        TRGM{"TRGM 켜짐?<br/>(현재: OFF)"}
    end
    
    subgraph AGGREGATE["Top-K 집계"]
        SCORE["lecture 별 점수 합산"]
        EVID["강의당 상위 3개 evidence"]
        TOP8["상위 8개 강의 선택"]
    end
    
    INPUT --> TOKEN --> STOP --> BUILD
    BUILD --> PG_SEARCH
    PG_SEARCH -->|"결과 없음"| FALLBACK1
    FALLBACK1 -->|"결과 없음"| FALLBACK2
    PG_SEARCH -->|"결과 있음"| TRGM
    FALLBACK1 -->|"결과 있음"| TRGM
    FALLBACK2 --> TRGM
    TRGM -->|"OFF"| SCORE
    SCORE --> EVID --> TOP8
    
    style TRGM fill:#ff9999
    style PG_SEARCH fill:#ffcc66
```

#### ⚠️ 여기서 실패하는 주요 원인

1. **토큰이 0개가 되는 경우**: 불용어 제거 후 의미 있는 토큰이 없으면 빈 쿼리 → 검색 결과 0건
2. **Postgres `websearch_to_tsquery` 한계**: CJK(한국어) 텍스트에 대해 `simple` config만 사용하므로 형태소 분석 없이 공백 단위 토큰만 매칭
3. **tsvector 미스매치**: `lecture_chunks.content_tsv` 컬럼이 제대로 인덱싱되지 않았거나, chunk 내용과 문제 텍스트의 용어가 다르면 매칭 실패
4. **TRGM이 꺼져 있음**: 유사한 표현(오타, 다른 표기법)이면 매칭 불가 — trigram fallback이 비활성
5. **candidates가 0건이면** → 바로 `no_match=True` 반환 (Stage 3을 건너뜀)

---

### 2.3 Stage 2: EXPAND (컨텍스트 확장)

**파일**: `context_expander.py`, `retrieval_features.py`

```
현재 Docker 설정: PARENT_ENABLED = false (기본값)
→ 이 단계는 완전히 건너뜀
```

이 단계가 켜져 있으면:
1. `retrieval_features.is_uncertain()` 함수가 검색 결과의 "불확실성"을 평가
2. 불확실하면 `expand_candidates()`로 각 candidate의 seed chunk에서 BM25 기반 semantic neighbors를 추가 수집
3. 확장된 텍스트(`parent_text`)가 LLM 프롬프트에 포함됨

---

### 2.4 Stage 3: JUDGE (LLM 분류 판정)

**파일**: `ai_classifier.py` GeminiClassifier

```mermaid
flowchart TD
    subgraph PROMPT_BUILD["프롬프트 구축"]
        P1["Question 텍스트"]
        P2["Choices (선지)"]
        P3["Candidate 정보<br/>(ID, full_path, evidence snippets)"]
        P4["Instructions<br/>(only pick from candidate IDs)"]
    end
    
    subgraph LLM_CALL["Gemini API 호출"]
        API["gemini-3-flash-preview<br/>temp=0.2, response_mime=JSON"]
        RETRY["최대 3회 재시도<br/>(exponential backoff)"]
    end
    
    subgraph POST_PROCESS["후처리 (핵심 검증)"]
        JSON_PARSE["JSON 파싱<br/>→ fallback regex 파싱"]
        
        LID_CHECK{"lecture_id<br/>valid_ids에 있음?"}
        LID_NULL["lecture_id = null<br/>no_match = true"]
        
        EVID_NORM["_normalize_evidence()<br/>증거 검증"]
        
        VQ_CHECK{"verbatim quote<br/>snippet에 포함?"}
        PS_CHECK{"page_start/end<br/>존재?"}
        CID_CHECK{"chunk_id<br/>candidate에 있음?"}
        
        EVID_PASS["evidence 통과"]
        EVID_FAIL["evidence 전부 실패"]
        
        FINAL_CHECK{"evidence 1개↑<br/>남아있음?"}
        FORCE_NOMATCH["❌ no_match 강제<br/>(grounded evidence 없음)"]
        SUCCESS["✅ 분류 성공"]
    end
    
    P1 --> API
    P2 --> API
    P3 --> API
    P4 --> API
    API --> RETRY --> JSON_PARSE
    
    JSON_PARSE --> LID_CHECK
    LID_CHECK -->|"없음"| LID_NULL
    LID_CHECK -->|"있음"| EVID_NORM
    
    EVID_NORM --> VQ_CHECK
    VQ_CHECK -->|"No (현재:필수)"| EVID_FAIL
    VQ_CHECK -->|"Yes"| PS_CHECK
    PS_CHECK -->|"No (현재:필수)"| EVID_FAIL
    PS_CHECK -->|"Yes"| CID_CHECK
    CID_CHECK -->|"No"| EVID_FAIL
    CID_CHECK -->|"Yes"| EVID_PASS
    
    EVID_PASS --> FINAL_CHECK
    EVID_FAIL --> FINAL_CHECK
    FINAL_CHECK -->|"0건"| FORCE_NOMATCH
    FINAL_CHECK -->|"1건+"| SUCCESS
    
    style FORCE_NOMATCH fill:#ff6666,color:#fff
    style VQ_CHECK fill:#ffaa00
    style PS_CHECK fill:#ffaa00
    style CID_CHECK fill:#ffaa00
```

#### ⚠️ 여기서 실패하는 주요 원인 (가장 중요!)

현재 Docker 설정:
```
CLASSIFIER_REQUIRE_VERBATIM_QUOTE=1  ← 엄격 모드
CLASSIFIER_REQUIRE_PAGE_SPAN=1       ← 엄격 모드
```

**`_normalize_evidence()` 함수 (라인 588-664)의 필터링 로직:**

| 조건 | 설정 | 실패 시 |
|------|------|---------|
| `chunk_id`가 candidate의 evidence에 존재해야 함 | 항상 | evidence 항목 제거 |
| LLM이 반환한 `quote`가 원본 `snippet` 안에 **정확히 포함**되어야 함 | `REQUIRE_VERBATIM=1` | evidence 항목 제거 |
| `page_start`/`page_end`가 존재해야 함 | `REQUIRE_PAGE_SPAN=1` | evidence 항목 제거 |

**👉 evidence가 모두 필터링되어 0건이 되면 → `no_match=true`로 강제 변환! (라인 798-801)**

```python
if lecture_id and not no_match:
    evidence = self._normalize_evidence(lecture_id, candidates, evidence_raw)
    if not evidence:
        # No grounded evidence -> force safe no_match.
        lecture_id = None
        no_match = True
```

이것이 **"당연히 분류돼야 할 문제가 no_match가 되는"** 가장 흔한 원인입니다.

---

## 3. 핵심 실패 시나리오 정리

```mermaid
flowchart LR
    subgraph FAIL1["🔴 실패 1: 검색 단계"]
        F1A["토큰화 후 0건"]
        F1B["tsvector 미매칭"]
        F1C["candidates = 0"]
    end
    
    subgraph FAIL2["🔴 실패 2: Evidence 검증"]
        F2A["LLM이 quote를<br/>약간 변형해서 반환"]
        F2B["chunk_id를<br/>잘못된 값으로 반환"]
        F2C["page 정보<br/>누락"]
    end
    
    subgraph FAIL3["🔴 실패 3: ID 검증"]
        F3A["LLM이 candidate에 없는<br/>lecture_id 반환"]
        F3B["LLM이 lecture_id를<br/>문자열로 반환"]
    end
    
    F1A --> NOMATCH["no_match = true"]
    F1B --> NOMATCH
    F1C --> NOMATCH
    F2A --> NOMATCH
    F2B --> NOMATCH
    F2C --> NOMATCH
    F3A --> NOMATCH
    F3B --> NOMATCH
    
    style NOMATCH fill:#ff4444,color:#fff
```

---

## 4. Docker 환경의 현재 설정과 영향

| 환경변수 | 현재값 | 영향 |
|----------|--------|------|
| `RETRIEVAL_MODE` | `bm25` | embedding 없이 순수 텍스트 매칭만 사용 |
| `SEARCH_BACKEND` | `postgres` | PostgreSQL `tsvector` 기반 검색 |
| `SEARCH_PG_QUERY_MODE` | `websearch` | `websearch_to_tsquery('simple', ...)` 사용 |
| `SEARCH_PG_TRGM_ENABLED` | `0` | trigram 유사도 fallback **비활성** |
| `CLASSIFIER_REQUIRE_VERBATIM_QUOTE` | `1` | LLM quote가 snippet에 **정확히** 포함돼야 함 |
| `CLASSIFIER_REQUIRE_PAGE_SPAN` | `1` | page_start/end **필수** |
| `CLASSIFIER_ALLOW_ID_FROM_TEXT` | `0` | reason/study_hint에서 ID 추출 **안 함** |
| `GEMINI_MODEL_NAME` | `gemini-3-flash-preview` | 프리뷰 모델 (안정성 미보장) |

---

## 5. 코드 디버깅 진입점

환경변수 `CLASSIFIER_DEBUG_LOG=1`을 추가하면 상세 로그가 출력됩니다:

```bash
# .env.docker에 추가
CLASSIFIER_DEBUG_LOG=1
```

주요 로그 트레이스 포인트:

| 로그 프리픽스 | 위치 | 정보 |
|--------------|------|------|
| `CLASSIFIER_JOB_ENQUEUED` | line 864 | Job 생성 시 |
| `CLASSIFIER_JOB_STARTED` | line 893 | Job 처리 시작 |
| `CLASSIFIER_PARSE_TRACE` | line 726 | LLM 응답 파싱 결과 |
| `CLASSIFIER_JOB_TRACE` | line 1043 | 문제별 분류 결과 요약 |
| `CLASSIFIER_APPLY_DECISION` | line 1360 | 적용 판정 이유 |
| `CLASSIFIER_APPLY_SKIP` | line 1322 | 스킵 사유 (out_of_candidates) |

---

## 6. 주요 소스 파일 맵

```mermaid
graph TB
    subgraph API["API Layer"]
        ROUTE["routes/manage.py<br/>classify_exam_questions()"]
    end
    
    subgraph Pipeline["Pipeline Layer"]
        PIPELINE["classification_pipeline.py<br/>classify_single_question()"]
        BATCH["ai_classifier.py<br/>AsyncBatchProcessor._process_job()"]
    end
    
    subgraph Services["Service Layer"]
        RETRIEVER["ai_classifier.py<br/>LectureRetriever"]
        CLASSIFIER["ai_classifier.py<br/>GeminiClassifier"]
        RETRIEVAL["retrieval.py<br/>search_chunks_bm25()"]
        EXPANDER["context_expander.py<br/>expand_candidates()"]
        FEATURES["retrieval_features.py<br/>is_uncertain()"]
    end
    
    subgraph Data["Data Layer"]
        DB["PostgreSQL<br/>lecture_chunks.content_tsv"]
        MODELS["models.py<br/>Question, Lecture, LectureChunk"]
    end
    
    subgraph Config["Configuration"]
        ENV[".env.docker"]
        SCHEMA["config/schema.py<br/>ExperimentConfig"]
    end
    
    ROUTE --> BATCH
    PIPELINE --> RETRIEVER
    PIPELINE --> EXPANDER
    PIPELINE --> CLASSIFIER
    BATCH --> RETRIEVER
    BATCH --> CLASSIFIER
    BATCH --> EXPANDER
    RETRIEVER --> RETRIEVAL
    RETRIEVAL --> DB
    EXPANDER --> RETRIEVAL
    CLASSIFIER --> API_CALL["Gemini API"]
    ENV --> SCHEMA
    SCHEMA --> RETRIEVER
    SCHEMA --> CLASSIFIER
    SCHEMA --> RETRIEVAL
```

---

## 7. 권장 확인/수정 포인트

### 즉시 확인할 것
1. **`CLASSIFIER_DEBUG_LOG=1`** 설정 후 로그에서 `candidates=0`인 문제가 있는지 확인
2. 로그에서 `CLASSIFIER_PARSE_TRACE`의 `no_match` 값 확인 — LLM이 `no_match=true`를 반환하는지, 아니면 후처리에서 강제 변환되는지

### 가장 영향이 큰 설정 변경 후보
1. **`CLASSIFIER_REQUIRE_VERBATIM_QUOTE=0`**: LLM이 quote를 약간 변형해도 허용 (가장 큰 영향)
2. **`CLASSIFIER_REQUIRE_PAGE_SPAN=0`**: page 정보 없어도 evidence 허용
3. **`SEARCH_PG_TRGM_ENABLED=1`**: 표현이 다른 경우에도 trigram 유사도로 검색 보완
4. **`CLASSIFIER_ALLOW_ID_FROM_TEXT=1`**: LLM이 reason 텍스트에 ID를 언급했으면 추출 시도
