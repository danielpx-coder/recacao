@echo off
rem ==========================================================================
rem  RD5 PageStudio 2.0 - cria o ambiente virtual, instala as dependencias
rem  (se necessario), ativa o venv e abre o aplicativo.
rem
rem  Uso:
rem      iniciar_pagestudio.bat                 abre o editor
rem      iniciar_pagestudio.bat pagina.htm      abre o editor com uma pagina
rem      iniciar_pagestudio.bat --dev           abre e mantem o console ativo
rem      iniciar_pagestudio.bat --shell         so ativa o venv e para
rem      iniciar_pagestudio.bat --reinstall     reinstala as dependencias
rem      iniciar_pagestudio.bat --sem-venv      usa o Python do sistema
rem ==========================================================================
setlocal enableextensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title RD5 PageStudio

set "APPFILE=rd5_pagestudio.py"
set "VENV=.venv"
set "REQ=requirements.txt"
set "PYTHON="
set "FORCE=0"
set "KEEP=0"
set "NOVENV=0"
set "SHELLONLY=0"
set "ARGFILE="

:args
if "%~1"=="" goto args_done
if /i "%~1"=="--reinstall" ( set "FORCE=1" & shift & goto args )
if /i "%~1"=="--dev"       ( set "KEEP=1"  & shift & goto args )
if /i "%~1"=="--shell"     ( set "SHELLONLY=1" & set "KEEP=1" & shift & goto args )
if /i "%~1"=="--sem-venv"  ( set "NOVENV=1" & shift & goto args )
if /i "%~1"=="--no-venv"   ( set "NOVENV=1" & shift & goto args )
set "ARGFILE=%~1"
shift
goto args
:args_done

echo.
echo  ==========================================================
echo   RD5 PageStudio 2.0 - editor de paginas HTML
echo  ==========================================================
echo.

rem ---------------------------------------------------------------- Python
where py >nul 2>&1
if errorlevel 1 goto try_python3
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYTHON (
        py -%%V -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYTHON=py -%%V"
    )
)
if defined PYTHON goto python_ok

:try_python3
python3 -c "import sys" >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python3" & goto python_ok )
python -c "import sys" >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python" & goto python_ok )

echo  [ERRO] Python nao encontrado neste computador.
echo.
echo  Instale o Python 3.10 ou mais novo em https://www.python.org/downloads/
echo  IMPORTANTE: marque a opcao "Add python.exe to PATH" durante a instalacao.
echo.
pause
exit /b 1

:python_ok
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo  [AVISO] O Python encontrado e mais antigo que 3.10. Pode funcionar,
    echo          mas o recomendado e instalar uma versao mais nova.
    echo.
)
echo  [1/4] Python localizado: %PYTHON%
%PYTHON% -c "import sys; print('        versao ' + sys.version.split()[0])"

rem ---------------------------------------------------------------- venv
if "%NOVENV%"=="1" (
    echo  [2/4] venv ignorado ^(--sem-venv^)
    goto deps
)
if exist "%VENV%\Scripts\python.exe" (
    echo  [2/4] Ambiente virtual ja existe: %VENV%
) else (
    echo  [2/4] Criando o ambiente virtual em %VENV% ...
    %PYTHON% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo  [ERRO] Nao foi possivel criar o ambiente virtual.
        echo         Em alguns PCs e preciso instalar o componente "venv" do Python
        echo         ou executar este arquivo como Administrador.
        echo.
        pause
        exit /b 1
    )
    set "FORCE=1"
)
call "%VENV%\Scripts\activate.bat"
if errorlevel 1 (
    echo  [ERRO] Falha ao ativar o ambiente virtual.
    pause
    exit /b 1
)
echo        Ambiente virtual ativado.
echo        python = "%VENV%\Scripts\python.exe"

rem -------------------------------------------------------- dependencias
:deps
if "%NOVENV%"=="1" (
    set "PYRUN=%PYTHON%"
) else (
    set "PYRUN="%VENV%\Scripts\python.exe""
)
if not exist "%REQ%" (
    echo  [3/4] Sem arquivo %REQ% - nada para instalar.
    goto run
)
%PYRUN% -c "import tkinterweb" >nul 2>&1
if not errorlevel 1 if "%FORCE%"=="0" (
    echo  [3/4] Dependencias ja instaladas.
    goto run
)
echo  [3/4] Instalando as dependencias do %REQ% ...
%PYRUN% -m pip install --upgrade pip >nul 2>&1
%PYRUN% -m pip install -r "%REQ%"
if errorlevel 1 (
    echo.
    echo  [AVISO] A instalacao das dependencias falhou ^(sem internet ou sem permissao^).
    echo          O RD5 PageStudio funciona mesmo assim: a visualizacao embutida
    echo          fica indisponivel e a pagina abre no navegador ^(tecla F12^).
    echo.
) else (
    echo        Dependencias instaladas.
)

rem ------------------------------------------------------------ executar
:run
if "%SHELLONLY%"=="1" (
    echo.
    echo  Ambiente pronto. O venv esta ativado neste console.
    echo  Para abrir o editor digite:  python %APPFILE%
    echo.
    cmd /k
    endlocal
    exit /b 0
)
echo  [4/4] Abrindo o RD5 PageStudio...
echo.
if defined ARGFILE (
    %PYRUN% "%APPFILE%" "%ARGFILE%"
) else (
    %PYRUN% "%APPFILE%"
)
set "RC=%errorlevel%"
if not "%RC%"=="0" (
    echo.
    echo  O aplicativo terminou com o codigo %RC%.
    pause
)
if "%KEEP%"=="1" (
    echo.
    echo  Console mantido aberto ^(--dev^). Digite "exit" para sair.
    cmd /k
)
endlocal
exit /b 0
