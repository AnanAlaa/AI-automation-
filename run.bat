@echo off
REM Convenience launcher for Businessy - بيزنسي (Windows)

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo Starting Businessy - بيزنسي ...
echo Make sure "ollama serve" is running and "qwen2.5:7b" is pulled.
echo.

python frontend\app.py
