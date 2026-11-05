@echo off
cd /d "%~dp0"
python job_agent.py
start "" report.html
pause
