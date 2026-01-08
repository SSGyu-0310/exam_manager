@echo off
chcp 65001 > nul
cd /d "d:\02_Non-Medicine\01_Coding\01_studyagent\exam_manager"
call .venv\Scripts\activate
echo Starting Exam Manager (local admin)...
start http://127.0.0.1:5001/manage
python run_local_admin.py
pause
