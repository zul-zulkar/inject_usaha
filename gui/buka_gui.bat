@echo off
rem Klik dua kali utk membuka GUI Inject Usaha SE2026 di browser.
rem Biarkan jendela hitam ini terbuka selama memakai GUI (Ctrl+C utk menutup).
cd /d "%~dp0.."
where python >nul 2>nul
if errorlevel 1 (
  echo Python belum terpasang atau belum ada di PATH. Pasang Python 3.10+ dari python.org ^(centang "Add python.exe to PATH"^).
  pause
  exit /b 1
)
python gui\server.py %*
if errorlevel 1 pause
