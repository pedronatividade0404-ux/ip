@echo off
cd /d "%~dp0"
if not exist .env (
  echo [ERRO] Crie cloud\.env usando .env.example antes de iniciar.
  pause
  exit /b 1
)
py -m uvicorn app:app --host 0.0.0.0 --port 8100
pause
