@echo off

echo ========================================
echo Starting Multi-Agent System
echo ========================================

set BLENDER_PATH=D:\blender-launcher.exe
set PROJECT_ROOT=%cd%

REM activate Blender Server
echo [1/2] Starting Blender Server...
start "Blender Server" "%BLENDER_PATH%" --background --python "%PROJECT_ROOT%\blender_server.py"
timeout /t 5 /nobreak > nul

REM activate Execution Agent
echo [2/2] Starting Execution Agent...
start "Execution Agent" cmd /k "call C:\Users\Jasper\miniconda3\Scripts\activate.bat && cd /d "%PROJECT_ROOT%\agents\execution_agent" && python -m uvicorn main:app --host 0.0.0.0 --port 8001"

echo.
echo ========================================
echo All services started successfully!
echo - Blender Server on port 8089
echo - Execution Agent API on port 8001
echo.
echo Test the API at: http://localhost:8001/docs
echo ========================================
echo.
pause