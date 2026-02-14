# API Guide

API 문서를 목적별로 분리했습니다.

## 어떤 문서를 볼지

- 개발 연동(프론트/백 통합, 엔드포인트 맵): `docs/api-dev.md`
- 운영 점검(헬스체크/장애 대응/분류 진단): `docs/api-ops.md`

## 공통 규칙

- Next는 `/api/proxy/*`를 통해 Flask API를 호출합니다.
- 인증은 JWT 쿠키 기반입니다.
- 일부 API는 신규 응답(`ok/data`)과 legacy 응답이 병행됩니다.

## Source of Truth

- Flask blueprint 등록: `app/__init__.py`
- 라우트 구현: `app/routes/*.py`
- Next proxy: `next_app/src/app/api/proxy/[...path]/route.ts`
