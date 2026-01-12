# Exam Manager

## 프로젝트 소개
- 한 줄 요약: 기출 시험 PDF를 파싱해 문제를 저장하고, 강의/블록 단위로 분류하며, 연습/채점까지 연결하는 로컬 웹 앱.
- 문제 정의: PDF 기반 기출 문제를 강의 단위로 정리/분류하고 연습 흐름을 한곳에서 처리해야 함.
- 해결 방식: Flask(Jinja) 관리 UI + SQLAlchemy/SQLite 데이터 모델 + Gemini 기반 자동 분류 + Next.js 연습 UI.
- 현재 스코프: 로컬 실행 중심, SQLite 단일 파일 DB, 관리/분류/연습/AI 분류 API 제공.

## 데모/스크린샷
- TODO: 실제 화면 캡처/링크 추가

## 주요 기능
### 현재 구현됨
- 블록/강의/기출시험 CRUD (`app/routes/manage.py`)
- PDF 업로드 → 문제/선지/정답 파싱 및 이미지 저장 (`app/services/pdf_parser.py`)
- 문제 수동 분류 + 일괄 분류 (`app/routes/exam.py`)
- Gemini 기반 AI 분류 작업(배치) + 미리보기/적용 (`app/routes/ai.py`)
- 강의 PDF 키워드 추출 (Gemini + pdfplumber, `app/services/keyword_extractor.py`)
- 연습 모드(Flask 템플릿): 강의별 문제 풀이/채점/결과/세션 기록 (`app/routes/practice.py`)
- 연습 API + Next.js 연습 UI (`app/routes/api_practice.py`, `next_app/`)
- Local admin 모드 (별도 DB + experimental PDF parser, `run_local_admin.py`)

### 계획됨
- TODO: 명시된 로드맵/백로그가 없어 확인 필요

## 기술 스택
- Frontend: Flask Jinja 템플릿(`app/templates`), Next.js 16.1.1(`next_app`), React 19.2.3, Tailwind CSS 3.4.17
- Backend: Python, Flask, Flask-SQLAlchemy, python-dotenv, pdfplumber, pandas, Pillow, google-genai, tenacity, scikit-learn, numpy
- DB: SQLite (`data/exam.db`, `data/admin_local.db`)
- AI: Google Gemini (google-genai)
- Infra: 로컬 실행 스크립트(`run.py`, `run_local_admin.py`, `launch_exam_manager*.bat`)
- Observability: 별도 스택/설정 확인되지 않음 (TODO)

## 빠른 시작
### Requirements
- Python (버전 TODO)
- Node.js (next_app 실행용, 버전 TODO)

### 설치
```bash
pip install -r requirements.txt
```

```bash
cd next_app
npm install
```

### 환경변수
Flask 루트 `.env` 준비:
```bash
copy .env.example .env
```

Mac/Linux:
```bash
cp .env.example .env
```

Next.js `.env.local` (필수, `next_app/` 아래):
```env
FLASK_BASE_URL=http://127.0.0.1:5000
```

### 개발 서버 실행
Flask (관리 UI + API):
```bash
python run.py
```
접속: http://127.0.0.1:5000

Local admin (실험용, 별도 DB):
```bash
python run_local_admin.py
```
접속: http://127.0.0.1:5001/manage

Next.js (연습 UI):
```bash
cd next_app
npm run dev
```
접속: http://localhost:3000/lectures

Windows 전용 실행 스크립트:
- `launch_exam_manager.bat`
- `launch_exam_manager_local_admin.bat`

### 빌드
Next.js:
```bash
cd next_app
npm run build
npm run start
```

Backend 빌드/배포 명령: TODO(확인 필요)

## 환경변수(.env) 가이드
### Flask (.env)
| 키 | 필수 | 설명 | 기본값/비고 |
| --- | --- | --- | --- |
| SECRET_KEY | 선택 | Flask 세션/보안 키 | 미설정 시 `dev-secret-key-change-in-production` |
| GEMINI_API_KEY | 조건부 | Gemini API 키 (AI 분류/텍스트 교정/키워드 추출 사용 시) | 없음 |
| GEMINI_MODEL_NAME | 선택 | Gemini 모델명 | `gemini-2.0-flash-lite` |
| AUTO_CREATE_DB | 선택 | 앱 시작 시 `db.create_all()` 자동 실행 | DevelopmentConfig 기본 True, 값은 `1/true/yes/on` |
| LOCAL_ADMIN_ONLY | 선택 | `/manage` 라우트 로컬호스트 제한 | 값은 `1/true/yes/on` |
| LOCAL_ADMIN_DB | 선택 | local admin DB 경로 | 미설정 시 `data/admin_local.db` |
| PDF_PARSER_MODE | 선택 | PDF 파서 선택 (`legacy`/`experimental`) | 기본 `legacy`, local_admin은 `experimental` |
| FLASK_CONFIG | 선택 | 설정 프로파일 선택 | `default`, `development`, `production`, `local_admin` |

### Next.js (`next_app/.env.local`)
| 키 | 필수 | 설명 | 기본값/비고 |
| --- | --- | --- | --- |
| FLASK_BASE_URL | 필수 | Next.js API proxy 대상 | 예: `http://127.0.0.1:5000` |

## 프로젝트 구조
```text
.
|-- app/
|   |-- __init__.py
|   |-- models.py
|   |-- routes/
|   |-- services/
|   |-- templates/
|   |-- static/
|-- data/
|-- next_app/
|-- scripts/
|-- frontend/
|-- config.py
|-- requirements.txt
|-- run.py
|-- run_local_admin.py
|-- launch_exam_manager.bat
|-- launch_exam_manager_local_admin.bat
|-- sample.pdf
```

- `app/`: Flask 앱 본체(앱 팩토리, DB, 라우트, 서비스, 템플릿, 정적 파일)
- `app/routes/`: Blueprint 모음(`main`, `exam`, `manage`, `practice`, `api_practice`, `ai`, `parse_pdf_questions.py`)
- `app/services/`: PDF 파서, AI 분류, 키워드 추출, 연습 로직
- `app/templates/`: Jinja UI 템플릿
- `app/static/`: JS + 업로드 파일(`uploads`, `uploads_admin`)
- `data/`: SQLite DB 및 백업(`exam.db`, `admin_local.db`, `exam.db.bak`)
- `next_app/`: Next.js 연습 UI + API proxy
- `scripts/`: DB 마이그레이션 스크립트
- `frontend/`: `dist` + `src/styles` + `node_modules` 존재 (용도 TODO)
- `run.py`/`run_local_admin.py`: Flask 실행 엔트리포인트
- `config.py`: 환경설정 및 플래그

### 아키텍처 개요
- Flask는 Jinja 템플릿 UI와 JSON API를 동시에 제공
- Next.js는 `/api/proxy/*`로 Flask API(`/api/practice`)를 프록시
- SQLite 파일 DB를 `data/`에 저장
- AI 분류는 백그라운드 스레드(`ThreadPoolExecutor`)로 실행되고 `classification_jobs`에 상태 저장

### 운영 포인트
- `AUTO_CREATE_DB` 활성 시 앱 시작 시점에 테이블 자동 생성
- Local admin 모드는 `LOCAL_ADMIN_ONLY`로 localhost 접근만 허용
- PDF 파서 모드(`PDF_PARSER_MODE`)는 `legacy`/`experimental` 선택
- 업로드 최대 크기: 100MB (`config.py`의 `MAX_CONTENT_LENGTH`)
- 업로드 저장 위치: `app/static/uploads` (local admin은 `uploads_admin`)
- AI 분류 작업은 비동기 처리이므로 서버 로그/상태 API를 통해 진행 확인

## 핵심 도메인/데이터 모델
### SQLAlchemy 모델 요약
- Block: 블록/과목 단위, `Lecture` 1:N
- Lecture: 강의 메타(제목/교수/순서/keywords), `Question` 1:N
- PreviousExam: 기출 시험 메타, `Question` 1:N
- Question: 문제 본문/정답/해설/난이도, 강의 분류 및 AI 분류 필드 포함
- Choice: 객관식 보기(번호/내용/정답 여부)
- UserNote: 문제별 사용자 메모
- PracticeSession: 연습 세션(문항 순서/모드/시간)
- PracticeAnswer: 세션별 답안 기록(정답 여부, 응답 시간)
- ClassificationJob: AI 분류 배치 작업 상태/결과

### localStorage (Flask practice UI)
- Key: `practice_{lectureId}` → `{ version: 1, lectureId, updatedAt, answers: { [questionId]: { type, value } } }`
- Key: `practice_{lectureId}_result` → `{ version: 1, lectureId, submittedAt, payload }`
- 마이그레이션: legacy 형식 감지 시 v1 형식으로 변환 후 저장(`app/static/js/practice_storage.js`)

### sessionStorage (Next practice UI)
- Key: `practice:session:{sessionId}` → 세션 컨텍스트(강의/모드/경고)
- Key: `practice:result:{sessionId}` → 제출 결과 요약 및 답안(`next_app/src/app/practice/...`)

## 주요 사용자 플로우
1) 관리/세팅: 블록 생성 → 강의 생성 → PDF 업로드 → 시험/문제 생성 → 문제 분류
2) AI 분류: 미분류 문제 선택 → AI 분류 시작 → 상태 조회 → 결과 미리보기 → 적용
3) 학습/연습: 강의 선택 → 연습 시작 → 문제 풀이 → 제출 → 결과 확인/세션 기록

## 개발 규칙 / 컨벤션
- Flask 라우트는 `app/routes` Blueprint로 분리하고, 비즈니스 로직은 `app/services`에 둔다
- DB 모델 변경 시 `app/models.py`와 마이그레이션 스크립트를 함께 업데이트한다
- API 응답은 `app/routes/api_practice.py`의 `error_response` 패턴(`ok`, `code`, `message`)을 유지한다
- UI 템플릿은 `app/templates`, Next 컴포넌트는 `next_app/src/components`에 위치시킨다
- 커밋/브랜치 전략은 명시된 규칙이 없음 → 추천: `main` + 짧은 feature 브랜치, 변경 단위별 커밋

### Non-negotiables
- `app/models.py`가 스키마의 단일 기준이며 변경 시 데이터 마이그레이션이 필요함
- `/api/practice` 응답 스키마를 변경할 경우 Next.js 클라이언트를 함께 수정해야 함
- `PRACTICE_VERSION=1` 로컬 저장 스키마 변경 시 마이그레이션 로직을 반드시 추가해야 함
- `PDF_PARSER_MODE` 값(`legacy`/`experimental`) 및 local_admin 전용 실험 흐름은 유지해야 함
- 업로드 저장 경로(`app/static/uploads*`)를 바꿀 경우 템플릿/파서/관리 UI를 함께 갱신해야 함

### LLM에게 작업시킬 때 지켜야 할 규칙
- 기존 폴더 구조(Flask Blueprint/Next App Router)를 유지하고, 신규 파일은 해당 위치에 추가한다
- 대규모 리팩토링 금지; 작은 변경 단위로 나눠서 진행한다
- API/DB 스키마 변경 시 backend+frontend+마이그레이션+README를 동시에 갱신한다
- README에는 실제 존재하는 명령어만 추가하고, 없는 항목은 TODO로 남긴다
- Next.js 변경 시 가능하면 `npm run lint`를 통과시키고, 실행하지 못했으면 명시한다
- `.env`/`.env.local` 실제 키 값은 커밋하지 않는다

## 트러블슈팅
- `ModuleNotFoundError` 발생: `pip install -r requirements.txt` 재실행
- AI 분류/텍스트 교정 실패: `google-genai` 설치 여부와 `GEMINI_API_KEY` 설정 확인
- Next.js 시작 시 `Missing or invalid FLASK_BASE_URL`: `next_app/.env.local`에 URL 설정
- PDF 업로드 후 문항이 0개: PDF 포맷 문제 가능 → `PDF_PARSER_MODE=experimental` 시도
- 업로드가 413으로 실패: `config.py`의 `MAX_CONTENT_LENGTH`(100MB) 확인
- Local admin 화면이 404: `LOCAL_ADMIN_ONLY` 활성화 시 localhost에서만 접근 가능
- 테이블이 생성되지 않음: `AUTO_CREATE_DB` 설정 또는 마이그레이션 스크립트 실행
- AI 분류 작업이 멈춘 것처럼 보임: 백그라운드 스레드 처리이므로 서버 로그/`/ai/classify/status`로 확인
- Next.js 연습 화면에서 데이터 로드 실패: Flask 서버가 실행 중인지, `/api/practice` 라우트가 등록됐는지 확인

## 로드맵
- 0~2주: 운영/배포 방식 결정, `frontend/` 사용 여부 정리, Next/Flask 역할 문서화
- 2~4주: backend 테스트/린트 기준 마련, 마이그레이션 절차 정리, API 스키마 문서화

## 라이선스/기여
라이선스 파일이 없습니다. 외부 기여/배포 정책은 TODO(확인 필요).

## TODO(확인 필요)
- Python/Node.js 최소 지원 버전은?
- `frontend/` 디렉터리는 현재 사용 중인가, 제거 가능한가?
- 배포/운영 환경(호스팅, 프로세스 매니저, CI)은?
- 인증/권한(로그인) 기능이 필요한가?
- `data/tmp_uploads` 사용 목적은?
- `next_app/.env.example` 템플릿을 추가할지?
- 백업/마이그레이션 정책은 어떻게 운영할지?
- `importer.py` 사용 계획은?
