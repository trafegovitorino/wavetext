@echo off
chcp 65001 >nul
title WaveText
cd /d "%~dp0"

REM Se ja instalado, abre direto
if exist ".venv\Scripts\python.exe" goto LAUNCH

echo.
echo  ============================================
echo   WaveText - Primeira execucao
echo   Isso pode levar 5-10 minutos. Aguarde.
echo  ============================================
echo.

REM Localiza Python (varias localizacoes possiveis)
set PYTHON=
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%PROGRAMFILES%\Python313\python.exe"
    "%PROGRAMFILES%\Python312\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        goto FOUND_PYTHON
    )
)

REM Tenta python do PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto FOUND_PYTHON
)

REM Baixa e instala Python
echo  [1/4] Baixando Python (pode demorar)...
powershell -NoProfile -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe' -OutFile '%TEMP%\pysetup.exe'}"
echo  [2/4] Instalando Python...
"%TEMP%\pysetup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%TEMP%\pysetup.exe" >nul 2>&1
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe

:FOUND_PYTHON
echo  [3/4] Criando ambiente virtual...
"%PYTHON%" -m venv .venv
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip

echo  [4/4] Instalando dependencias (pode demorar 5-10 min)...
.venv\Scripts\python.exe -m pip install faster-whisper customtkinter tkinterdnd2 openai pillow

REM Cria atalho na Area de Trabalho apontando para o VBS (sem terminal)
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\WaveText.lnk');$s.TargetPath='%~dp0WaveText.vbs';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1

echo.
echo  Instalacao concluida! Abrindo WaveText...
echo.

:LAUNCH
start "" /b wscript.exe "%~dp0WaveText.vbs"
