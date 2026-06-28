@echo off
cd /d "%~dp0"
python -m uvicorn main:app --host 0.0.0.0 --port 8003 > _uvicorn_8003_cmd.log 2>&1
