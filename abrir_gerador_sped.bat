@echo off
cd /d "%~dp0"
set "PYTHONW="

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%~fD\pythonw.exe" set "PYTHONW=%%~fD\pythonw.exe"
)
for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%~fD\pythonw.exe" set "PYTHONW=%%~fD\pythonw.exe"
)
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.*") do (
    if exist "%%~fD\pythonw.exe" set "PYTHONW=%%~fD\pythonw.exe"
)

if defined PYTHONW (
    start "" "%PYTHONW%" "%~dp0gerador_sped_c100.py"
) else (
    echo Python nao encontrado. Instale o Python para Windows com Tcl/Tk habilitado.
    echo Depois, abra novamente este arquivo para iniciar o GenTXT.
    pause
)
