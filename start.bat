@echo off

echo ========================================
echo Starting Multi-Agent System
echo ========================================

REM force clean up old processes
echo Cleaning up old processes...
taskkill /IM python.exe /F 2>nul
taskkill /IM blender.exe /F 2>nul

REM Kill processes using specific ports
echo Cleaning up ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8002') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8003') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8004') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8089') do taskkill /PID %%a /F 2>nul

timeout /t 5 /nobreak > nul

set BLENDER_PATH=D:\blender.exe
set PROJECT_ROOT=%cd%
set PYTHON_PATH=C:\Users\Jasper\miniconda3\python.exe

REM activate Blender Server in background mode
echo [1/5] Starting Blender Server (background mode)...
start "Blender Server" cmd /k ""%BLENDER_PATH%" -b --python "%PROJECT_ROOT%\blender_server.py""
echo Waiting for Blender server to start...
timeout /t 5 /nobreak > nul

REM activate Execution Agent
echo [2/5] Starting Execution Agent...
start "Execution Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\execution_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak > nul

REM activate Reviewing Agent
echo [3/5] Starting Reviewing Agent...
start "Reviewing Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\reviewing_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8002"
timeout /t 3 /nobreak > nul

echo [4/5] Starting Scene Planning Agent...
start "Scene Planning Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\scene_planning_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8003"
timeout /t 3 /nobreak > nul

echo [5/5] Starting Coding Agent...
start "Coding Agent" cmd /k "cd /d "%PROJECT_ROOT%\agents\coding_agent" && "%PYTHON_PATH%" -m uvicorn main:app --host 0.0.0.0 --port 8004"
timeout /t 3 /nobreak > nul

echo.
echo ========================================
echo All services started successfully!
echo - Blender Server on port 8089 (background mode)
echo - Execution Agent API on port 8001
echo - Reviewing Agent API on port 8002
echo - Scene Planning Agent API on port 8003
echo - Coding Agent API on port 8004
echo.
echo Test APIs at:
echo - http://localhost:8001/docs (Execution)
echo - http://localhost:8002/docs (Reviewing)
echo - http://localhost:8003/docs (Scene Planning)
echo - http://localhost:8004/docs (Coding)
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