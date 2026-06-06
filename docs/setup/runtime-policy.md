# Docker Runtime Policy

이 프로젝트의 공통 실행 표준은 특정 로컬 런타임이 아니라 Docker CLI와 Compose입니다.

## 핵심 원칙
- 프로젝트가 기대하는 공통 인터페이스는 `docker`와 `docker compose`입니다.
- `docker-compose`는 레거시 호환 경로로 보고, 문서와 스크립트의 기본 표기는 `docker compose`로 맞춥니다.
- Docker daemon 구현체는 환경별로 다를 수 있습니다.
  - macOS: Docker Desktop 또는 Colima
  - Windows / WSL: Docker Desktop
  - Linux: Docker Engine 또는 이에 준하는 Docker-compatible daemon
- 리포지토리 스크립트는 특정 런타임을 자동 설치하거나 자동 기동하지 않습니다.
- 런타임이 꺼져 있으면 스크립트는 현재 Docker context를 기준으로 원인을 설명하고, 사용자가 런타임을 직접 올리도록 안내합니다.

## 왜 이렇게 정하나
- 배포 전 검증과 로컬 개발이 같은 Compose 인터페이스를 공유해야 환경 차이를 줄일 수 있습니다.
- macOS 전용 도구인 Colima를 리포지토리 수준 표준으로 강제하면 Windows, WSL, Linux 문서와 흐름이 흐려집니다.
- 반대로 Docker Desktop만 전제로 박아두면 macOS에서 Colima를 쓰는 개발자에게 불필요한 제약이 생깁니다.

## 권장 사용 방식
- 배포 전 검증: `./scripts/dc up -d --build`
- 로컬 빠른 개발: DB만 Compose로 띄우고 앱은 호스트에서 실행
- 문제 진단 순서:
  1. `docker context show`
  2. `docker info`
  3. 현재 context에 맞는 런타임 기동
     - Colima: `colima start`
     - Docker Desktop: 앱 실행 후 daemon 준비 확인

## 팀 합의 문장
- "우리 프로젝트는 Docker Compose를 표준 인터페이스로 사용한다."
- "로컬 런타임 선택은 개발 환경별 책임으로 둔다."
- "배포/검증 문서와 스크립트는 런타임 중립적으로 유지한다."
