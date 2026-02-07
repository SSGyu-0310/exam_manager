# PDF 파싱 검증 세트 (10샘플)

`app/services/pdf_parser.py`의 정규식/레이아웃 의존 파싱 품질을 릴리즈 전 최소 게이트로 확인하기 위한 절차입니다.

## 1) 샘플 세트 준비
- 샘플 PDF 10개를 `parse_lab/pdfs/`에 배치합니다.
- 체크표 템플릿: `docs/refactoring/pdf_parser_validation_template.csv`
- 각 행의 `pdf_path`를 실제 파일 경로로 맞춥니다.

## 2) 기대값 입력
- 사람 검수 기준으로 각 PDF의 기대 문항 수/선지 수를 입력합니다.
- 컬럼:
  - `expected_questions`
  - `expected_choices`

## 3) 업로드 결과 입력
- Next 강의/시험 업로드 후 API 응답(`questionCount`, `choiceCount`) 또는 화면 통계 기준으로:
  - `uploaded_questions`
  - `uploaded_choices`
  값을 입력합니다.

## 4) 비교 실행
```bash
python scripts/validate_pdf_parser_manifest.py \
  --manifest docs/refactoring/pdf_parser_validation_template.csv \
  --mode legacy \
  --report parse_lab/output/pdf_parser_validation_report.csv
```

## 5) 판정 기준
- `parse_lab/output/pdf_parser_validation_report.csv`에서 상태 컬럼 확인:
  - `expected_*_status`
  - `uploaded_*_status`
- `FAIL` 또는 `parse_error`가 있으면 릴리즈 차단.
