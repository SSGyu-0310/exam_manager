# WSL 설치/실행 가이드

이 문서는 WSL2 + Ubuntu 기준으로 작성되었습니다. WSL에서 실행한 Flask/Next.js는 Windows 브라우저에서 `http://localhost:5000` 또는 `http://localhost:3000`으로 접근 가능합니다.

## 0) 전제
- WSL2 설치 및 Ubuntu 배포판 준비
- Git 사용 가능
- Python 3.10+ 설치 가능
- Node.js 18+ 설치 가능 (nvm 권장)

## 1) 기본 도구 설치 (필요 시)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 --version  # 3.10+ 권장
```

Node.js는 `nvm` 사용을 권장합니다.
```bash
# nvm 설치 (이미 설치되어 있다면 생략)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Node 설치 (예: 20)
nvm install 20
nvm use 20
node --version
```

## 2) 프로젝트 준비
```bash
cd /home/ksw6895/Projects/exam_manager
```

## 3) Python 가상환경
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) 환경변수(.env)
```bash
cp .env.example .env
```
- AI 기능을 사용할 경우 `.env`에 `GEMINI_API_KEY`를 입력합니다.

## 5) Next.js 환경변수
```bash
cat <<'EOT' > next_app/.env.local
FLASK_BASE_URL=http://127.0.0.1:5000
EOT
```
- SSR에서 올바른 base URL이 필요하면 `NEXT_PUBLIC_SITE_URL`을 추가합니다.

## 6) 서버 실행
### Flask (관리 UI + API)
```bash
python run.py
```
접속: http://127.0.0.1:5000

### Next.js (관리/연습 UI)
```bash
cd next_app
npm install
npm run dev
```
접속: http://localhost:3000/lectures

## 7) Local admin (실험용)
```bash
python run_local_admin.py
```
접속: http://127.0.0.1:5001/manage

## 8) 자주 발생하는 문제
- `/manage`가 404: `LOCAL_ADMIN_ONLY`가 활성화되어 있으면 localhost 접근만 허용됩니다.
- Next.js에서 API 오류: `next_app/.env.local`의 `FLASK_BASE_URL` 확인.
- 초기 테이블이 없으면 `AUTO_CREATE_DB=1` 설정 후 재실행.
