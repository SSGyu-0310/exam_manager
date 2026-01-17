# Cache Policy

Exam Manager의 캐시/아티팩트 경로 규칙과 관리 방침입니다.

## Cache Directory Structure

| Directory | Purpose | Contents |
|-----------|---------|----------|
| `data/cache/` | AI 분류 캐시 | JSON cache files for classifier results |
| `data/classifier_cache.json` | 레거시 캐시 (호환용) | Classifier results in single JSON file |
| `reports/` | 평가 리포트 | Evaluation runs, logs, metrics |

## Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLASSIFIER_CACHE_PATH` | `data/classifier_cache.json` | 분류기 캐시 경로 (호환용, 사용 권장 x) |
| `DATA_CACHE_DIR` | `data/cache` | 캐시 디렉토리 기본 경로 |
| `REPORTS_DIR` | `reports` | 리포트 디렉토리 기본 경로 |

## Cache Key Schema

`ClassifierResultCache`는 다음 키 스키마 사용:

```
{question_id}:{config_hash}:{model_name}
```

**구성 요소:**
- `question_id`: 문제 ID
- `config_hash`: 설정 해시 (모델/모드/파라미터 변화 감지)
- `model_name`: 모델명 (e.g., `gemini-3-flash-preview`)

**충돌 방지:**
- 모델/모드/버전 변경 시 자동으로 새 캐시 키 생성
- config_hash는 `build_config_hash()`로 생성

## Cache Invalidation

캐시는 다음 경우 자동 무효화됩니다:

1. **모델 변경**: `GEMINI_MODEL_NAME` 변경 시
2. **설정 변경**: retrieval/확장 관련 설정 변경 시 config_hash 변화
3. **수동 무효화**: 캐시 파일 삭제 시

## 파일 관리

### 무시해야 할 디렉토리

다음 디렉토리는 git에 커밋하지 않습니다:

```
data/cache/
reports/
```

이 디렉토리들은 `.gitignore`에 이미 포함되어 있습니다.

### 캐시 비우기

```bash
# 캐시 비우기
rm -rf data/cache/*

# 리포트 비우기
rm -rf reports/*

# 분류기 캐시 비우기 (호환용)
rm -f data/classifier_cache.json
```

### 캐시 파일 형식

`data/cache/` 내 JSON 파일들:

- `baseline_classifier_cache.json`: 베이스라인 캐시
- `upgrade_classifier_cache.json`: 업그레이드 캐시
- `upgraded_classifier_cache.json`: 최신 캐시

이 파일들은 스크립트/배치 평가에 의해 생성되며, 자동 관리 대상입니다.

## 브랜치/환경별 캐시 관리

### Development 환경
```bash
# 캐시 허용 (기본)
# 환경변수 불필요
```

### Production 환경
```bash
# 캐시 허용 (기본)
# 환경변수 불필요

# 캐시 위치 변경 (필요 시)
export DATA_CACHE_DIR=/path/to/cache
export REPORTS_DIR=/path/to/reports
```

### Local Admin 환경
```bash
# 기본 캐시 설정 상속
# LocalAdminConfig는 별도 캐시 설정 없음
```

## 캐시 관리 모범 사례

### 1. 캐시 디버깅
```bash
# 캐시 상태 확인
ls -lh data/cache/

# 캐시 파일 내용 확인
cat data/cache/baseline_classifier_cache.json | jq '. | keys' | head
```

### 2. 모델/설정 변경 후 캐시 정리
```bash
# 설정 변경 후
vim .env  # 설정 변경

# 캐시 정리 (새 config_hash 적용)
rm -f data/classifier_cache.json
rm -rf data/cache/*

# 새 캐시 생성 후 실행
python run.py
```

### 3. 평가 스크립트와 캐시
```bash
# 평가 시 캐시 사용 (기본 동작)
python scripts/evaluate_evalset.py

# 캐시 없이 평가 (비교용)
rm -rf data/cache/*
python scripts/evaluate_evalset.py
```

## 관련 코드

- `config.py`: 캐시 경로 설정 (`CLASSIFIER_CACHE_PATH`, `DATA_CACHE_DIR`, `REPORTS_DIR`)
- `app/services/classifier_cache.py`: `ClassifierResultCache` 구현
- `scripts/evaluate_evalset.py`: `build_config_hash()` 및 캐시 사용

## 참고

- [Configuration Reference](../setup/config-reference.md)
- [Operations Scripts](../operations/scripts.md)
