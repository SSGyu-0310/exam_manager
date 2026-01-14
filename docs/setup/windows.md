# Windows 설치/실행 가이드

PowerShell 기준으로 작성했습니다.

## 0) 전제
- Python 3.10+ 설치 후 `py` 명령 동작
- Node.js 18+ 설치 후 `node`/`npm` 사용 가능
- Git 사용 가능

## 1) 프로젝트 준비
```powershell
cd C:\path\to\exam_manager
```

## 2) Python 가상환경
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3) 환경변수(.env)
```powershell
copy .env.example .env
```
- AI 기능을 사용할 경우 `.env`에 `GEMINI_API_KEY`를 입력합니다.

## 4) Next.js 환경변수
```powershell
Set-Content -Path next_app\.env.local -Value "FLASK_BASE_URL=http://127.0.0.1:5000"
```
- SSR에서 올바른 base URL이 필요하면 `NEXT_PUBLIC_SITE_URL`을 추가합니다.

## 5) 서버 실행
### Flask (관리 UI + API)
```powershell
python run.py
```
접속: http://127.0.0.1:5000

### Next.js (관리/연습 UI)
```powershell
cd next_app
npm install
npm run dev
```
접속: http://localhost:3000/lectures

## 6) Local admin (실험용)
```powershell
python run_local_admin.py
```
접속: http://127.0.0.1:5001/manage

## 7) 배치 스크립트 사용
- `launch_exam_manager.bat`
- `launch_exam_manager_local_admin.bat`

두 파일 모두 `cd /d` 경로가 하드코딩되어 있으므로 본인 환경에 맞게 수정해야 합니다.

## 8) 자주 발생하는 문제
- PowerShell 실행 정책으로 Activate가 막히면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 적용 후 재시도.
- Next.js에서 API 오류: `next_app/.env.local`의 `FLASK_BASE_URL` 확인.
- 초기 테이블이 없으면 `AUTO_CREATE_DB=1` 설정 후 재실행.
