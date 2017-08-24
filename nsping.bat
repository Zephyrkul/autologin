@echo off
chcp 65001 > nul
pushd %~dp0

::attempts to start py launcher without relying on path
%systemroot%\py.exe --version > nul 2>&1
if %errorlevel% neq 0 goto attempt
%systemroot%\py.exe -3 nsping.py
goto end

::attempts to start py launcher by relying on path
:attempt
py.exe --version > nul 2>&1
if %errorlevel% neq 0 goto lastattempt
py.exe -3 nsping.py
goto end

::as a last resort, attempts to start whatever python there is
:lastattempt
python.exe --version > nul 2>&1
if %errorlevel% neq 0 goto message
python.exe nsping.py
goto end

:message
echo Couldn't find a valid Python installation.
echo https://www.python.org/downloads/
pause

:end
