@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================
echo  Git Graph - n8n Workflow Style Updater
echo ====================================================
echo Regenerating git_data.js from Git Repository...
python generate_dag.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Git graph updated successfully!
    echo Refresh your browser (F5) on index.html to see latest changes.
) else (
    echo.
    echo [ERROR] Failed to generate Git graph!
)
echo.
pause
