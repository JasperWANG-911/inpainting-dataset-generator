@echo off

echo ========================================
echo Starting Multi-Agent System
echo ========================================

REM force clean up old processes
echo Cleaning up old processes...
taskkill /IM python.exe /F 2>nul
taskkill /IM blender.exe /F 2>nul
timeout /t 3 /nobreak > nul

set BLENDER_PATH=D:\blender-launcher.exe
set PROJECT_ROOT=%cd%
set PYTHON_PATH=C:\Users\Jasper\miniconda3\python.exe

REM activate Blender Server
echo [1/3] Starting Blender Server...
start "Blender Server" "%BLENDER_PATH%" --background --python "%PROJECT_ROOT%\blender_server.py"
timeout /t 5 /nobreak > nul

REM activate Execution Agent
echo [2/3] Starting Execution Agent...
start "Execution Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\execution_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak > nul

REM activate Reviewing Agent
echo [3/3] Starting Reviewing Agent...
start "Reviewing Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\reviewing_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8002"

echo.
echo ========================================
echo All services started successfully!
echo - Blender Server on port 8089
echo - Execution Agent API on port 8001
echo - Reviewing Agent API on port 8002
echo.
echo Test APIs at:
echo - http://localhost:8001/docs (Execution)
echo - http://localhost:8002/docs (Reviewing)
echo ========================================
echo.
echo Press any key to stop all services...
pause > nul

REM stop all services
echo Stopping all services...
taskkill /IM python.exe /F
taskkill /IM blender.exe /F
echo Done!
pause