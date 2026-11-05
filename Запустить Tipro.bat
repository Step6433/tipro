@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
where node >nul 2>nul
if errorlevel 1 (
  echo Установите Node.js LTS, затем откройте этот файл снова.
  pause
  exit /b 1
)
call npm start
if errorlevel 1 pause
endlocal
