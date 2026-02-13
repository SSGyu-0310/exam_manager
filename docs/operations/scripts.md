# 운영/스크립트 가이드 (Postgres)

## 주의 사항
- 모든 운영 DB 작업은 Postgres URI(`postgresql+psycopg://...`) 기준으로 실행합니다.
- 스크립트 실행 전 DB 백업을 먼저 수행합니다.
- 레거시 파일 기반 스크립트 경로는 운영 대상에서 제외되었습니다.

## 기본 운영 흐름
```bash
# 1) 백업
python scripts/backup_postgres.py --db "$DATABASE_URL"

# 2) 마이그레이션
python scripts/run_postgres_migrations.py --db "$DATABASE_URL"

# 3) FTS 동기화
python scripts/init_fts.py --db "$DATABASE_URL" --sync
```

## FTS 초기화/동기화
```bash
python scripts/init_fts.py --db "$DATABASE_URL" --sync
python scripts/init_fts.py --db "$DATABASE_URL" --rebuild
```
- `--sync`: 증분 반영
- `--rebuild`: 기존 인덱스/벡터를 재생성

## AI 분류 필드 마이그레이션
```bash
python scripts/migrate_ai_fields.py --db "$DATABASE_URL"
```

## 기타 유틸리티 (CLI)

### PDF -> CSV 변환
```bash
PYTHONPATH=. python app/routes/parse_pdf_questions.py input.pdf [output.csv]
```

### PDF 문제 크롭 이미지 생성
```bash
python app/routes/crop.py --pdf input.pdf --out exam_crops
```

## 데이터 위치 요약
- 업로드 이미지/파일: `app/static/uploads/` (local admin은 `uploads_admin`)
- 백업 덤프 기본 경로: `backups/`
