# AI Agent 작업 프롬프트: `no_match` 재판단(2-pass) 로직 구현

아래 요구사항을 이 저장소(`/home/gyu/learn/exam_manager`)에 직접 반영해 주세요.

## 1) 배경과 목표
- 현재 분류는 `strict no_match` 정책으로 안전하지만, 후보 강의가 충분한데도 `no_match`가 과도하게 발생합니다.
- 목표는 **기존 안전성(정밀도)을 유지한 채**, `no_match` 케이스에 한해 추가 정보를 넣어 2차 재판단하여 회수율을 개선하는 것입니다.
- 핵심 원칙:
  - 1차 분류 로직은 유지
  - `no_match`일 때만 2차 재판단
  - 자동 반영(auto-apply)은 보수적으로 유지

## 2) 구현 범위
### A. 설정(Feature Flag) 추가
다음 설정을 추가하고 `.env.docker.example`/설정 스키마/기본값에 반영하세요.
- `CLASSIFIER_REJUDGE_ENABLED` (default: `1`)
- `CLASSIFIER_REJUDGE_MIN_CANDIDATES` (default: `3`)
- `CLASSIFIER_REJUDGE_TOP_K` (default: `8`)
- `CLASSIFIER_REJUDGE_EVIDENCE_PER_LECTURE` (default: `6`)
- `CLASSIFIER_REJUDGE_MIN_CONFIDENCE_STRICT` (default: `0.80`)
- `CLASSIFIER_REJUDGE_ALLOW_WEAK_MATCH` (default: `1`)
- `CLASSIFIER_REJUDGE_MIN_CONFIDENCE_WEAK` (default: `0.65`)

### B. 2-pass 분류 흐름 추가
대상 파일 중심:
- `app/services/ai_classifier.py`
- 필요 시 `app/services/retrieval.py`, `app/services/retrieval_features.py`

구현 요구:
1. 1차 분류(`classify_single`) 결과가 `no_match`이고, 후보 수가 `CLASSIFIER_REJUDGE_MIN_CANDIDATES` 이상이면 2차 재판단 호출.
2. 2차에서는 후보별 근거를 더 두텁게 제공:
   - 동일 후보 강의 집합 내에서 evidence를 더 많이 수집(lecture별 up to `CLASSIFIER_REJUDGE_EVIDENCE_PER_LECTURE`)
   - 가능하면 parent/인접 문맥을 포함
3. 2차 전용 프롬프트(`_build_rejudge_prompt`) 추가:
   - 출력 스키마:
     - `decision_mode`: `strict_match | weak_match | no_match`
     - `lecture_id`
     - `confidence`
     - `reason`
     - `evidence`
     - `why_not_no_match`
4. 결과 병합 규칙:
   - `strict_match` + confidence >= `CLASSIFIER_REJUDGE_MIN_CONFIDENCE_STRICT` -> 분류 제안으로 채택
   - `weak_match` + `CLASSIFIER_REJUDGE_ALLOW_WEAK_MATCH=1` + confidence >= `CLASSIFIER_REJUDGE_MIN_CONFIDENCE_WEAK` -> 제안으로 채택(단, auto-apply 제외)
   - 나머지는 `no_match` 유지

### C. 결과 메타데이터/진단 확장
`result_json`의 문항 결과에 아래 필드를 추가 저장:
- `rejudge_attempted` (bool)
- `rejudge_decision_mode` (nullable)
- `rejudge_confidence` (nullable)
- `rejudge_reason` (nullable)
- `final_decision_source` (`pass1|pass2`)

`build_job_diagnostics`에 요약 카운트 추가:
- `rejudge_attempted_count`
- `rejudge_salvaged_count` (`pass1 no_match -> pass2 match/weak_match`)
- `weak_match_count`

### D. 적용(apply) 정책
`apply_classification_results`에서:
- `decision_mode == weak_match`는 자동 반영하지 않음
- 기존 `strict match` 자동 반영 조건만 유지
- `apply_report`/`diagnostics`에 weak_match skip 사유 명시

## 3) 기존 동작과의 호환성
- 기존 API 응답 스키마는 깨지지 않게 유지(필드 추가는 허용).
- `CLASSIFIER_REJUDGE_ENABLED=0`일 때 기존 동작과 동일해야 함.
- 시험지 과목 기반 후보 제한 로직(현재 기본값)은 유지.

## 4) 테스트 요구사항
테스트 파일:
- `tests/test_classifier_postprocess.py` 중심으로 추가

최소 테스트 케이스:
1. `pass1 no_match` + `pass2 strict_match` -> 최종 lecture 채택
2. `pass1 no_match` + `pass2 weak_match` -> 결과에는 남지만 auto-apply 제외
3. `CLASSIFIER_REJUDGE_ENABLED=0` -> 기존과 동일
4. 후보 부족(< min candidates) -> 재판단 미실행
5. 진단 카운트(`rejudge_*`) 정확성

## 5) 구현 제약
- DB 마이그레이션은 만들지 말고 `result_json` 확장으로 처리.
- 코드 스타일은 기존 저장소 패턴을 따르고, 불필요한 리팩터링은 피하세요.
- 변경 파일과 테스트 결과를 최종 보고에 명시하세요.

## 6) 완료 기준(Acceptance Criteria)
- 면역학처럼 `no_match`가 많은 배치에서, 안전성 훼손 없이 일부 케이스가 `strict_match` 또는 `weak_match`로 구조적으로 회수됨.
- `weak_match`는 자동 반영되지 않고 리뷰 큐 개선용으로만 노출됨.
- Feature flag off 시 회귀 없음.
