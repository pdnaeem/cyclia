@echo off
REM ===========================================================================
REM  One-click build of the Cyclia Windows installer.
REM  Finds Python (3.10 to 3.13) and Node.js; if one is missing it offers to
REM  install it with winget. Result: app\dist\Cyclia-Setup-<version>.exe
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
echo.
echo === Cyclia installer build ===
echo.

REM ---------------------------------------------------------------- Python
call :findpy
if not defined PY (
  echo Python 3.10 to 3.13 was not found on this PC.
  echo The "python" command that Windows shows is only a Microsoft Store shortcut.
  where winget >nul 2>nul
  if !errorlevel! equ 0 (
    choice /M "Install Python 3.12 now (winget, no admin rights needed)"
    if !errorlevel! equ 1 (
      winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
      call :findpy
    )
  )
)
if not defined PY (
  echo.
  echo Install Python 3.12 from https://www.python.org/downloads/windows/
  echo and tick "Add python.exe to PATH" on the first screen. Then run this file again.
  pause
  exit /b 1
)
echo Using Python: !PY!

REM ---------------------------------------------------------------- Node.js
call :findnode
if not defined NODEOK (
  echo Node.js was not found on this PC.
  where winget >nul 2>nul
  if !errorlevel! equ 0 (
    choice /M "Install Node.js LTS now (winget)"
    if !errorlevel! equ 1 (
      winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
      call :findnode
    )
  )
)
if not defined NODEOK (
  echo.
  echo Install the LTS version of Node.js from https://nodejs.org and run this file again.
  pause
  exit /b 1
)

REM ---------------------------------------------------------------- engine
set "SKIPENGINE="
if exist "engine\dist\cyclia-engine\cyclia-engine.exe" (
  choice /T 15 /D N /M "The engine is already built. Rebuild it (only needed after engine changes)"
  if !errorlevel! equ 2 set "SKIPENGINE=1"
)
if defined SKIPENGINE goto installer
REM A private Python environment keeps the build independent of other Python projects.
if not exist ".buildenv\Scripts\python.exe" (
  echo Creating build environment...
  !PY! -m venv .buildenv
  if errorlevel 1 ( echo Could not create the build environment. & pause & exit /b 1 )
)
".buildenv\Scripts\python.exe" -m pip install --upgrade pip >nul
".buildenv\Scripts\python.exe" engine\build-engine.py
if errorlevel 1 ( echo. & echo Engine build failed. See the messages above. & pause & exit /b 1 )

:installer
REM world map for the results (optional; needs internet, falls back to a schematic map)
!PY! engine\tools\apply_credits.py
!PY! engine\tools\fetch_world.py

REM ---------------------------------------------------------------- installer
cd app
findstr /C:"ui-fix-4" main.js >nul || ( echo. & echo app\main.js is the old version. Replace it with the new main.js and run this again. & pause & exit /b 1 )
REM remove old installers so an outdated one can never be installed by mistake
if exist dist rmdir /s /q dist
call npm install
if errorlevel 1 ( echo npm install failed. Check the internet connection. & pause & exit /b 1 )
call npm run dist:win
if errorlevel 1 ( echo Installer build failed. See the messages above. & pause & exit /b 1 )
echo.
echo Done. The installer is in %~dp0app\dist
explorer "%~dp0app\dist"
pause
exit /b 0

REM ================================================================ helpers
:findpy
set "PY="
REM 1. the py launcher that python.org installs
for %%v in (3.12 3.11 3.13 3.10) do (
  if not defined PY (
    py -%%v -c "import sys" >nul 2>nul
    if !errorlevel! equ 0 set "PY=py -%%v"
  )
)
REM 2. the usual per-user and per-machine install folders (PATH may not be refreshed yet)
for %%d in (Python312 Python311 Python313 Python310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%d\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\%%d\python.exe"
  if not defined PY if exist "%ProgramFiles%\%%d\python.exe" set PY="%ProgramFiles%\%%d\python.exe"
)
REM 3. python on PATH (the Store shortcut fails this test, which is what we want)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)" >nul 2>nul
  if !errorlevel! equ 0 set "PY=python"
)
exit /b 0

:findnode
set "NODEOK="
where npm >nul 2>nul
if !errorlevel! equ 0 ( set "NODEOK=1" & exit /b 0 )
if exist "%ProgramFiles%\nodejs\npm.cmd" (
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
  set "NODEOK=1"
)
exit /b 0
