#!/usr/bin/env bash
# ==========================================================================
#  RD5 PageStudio 2.0 - cria o ambiente virtual, instala as dependencias
#  (se necessario), ativa o venv e abre o aplicativo.
#
#  Uso:
#      ./iniciar_pagestudio.sh                abre o editor
#      ./iniciar_pagestudio.sh pagina.htm     abre o editor com uma pagina
#      ./iniciar_pagestudio.sh --shell        so ativa o venv e para
#      ./iniciar_pagestudio.sh --reinstall    reinstala as dependencias
#
#  Em Linux o Tkinter vem do sistema:  sudo apt install python3-tk
# ==========================================================================
set -euo pipefail
cd "$(dirname "$0")"

APPFILE="rd5_pagestudio.py"
VENV=".venv"
REQ="requirements.txt"
FORCE=0
SHELLONLY=0
ARGFILE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --reinstall) FORCE=1 ;;
        --shell)     SHELLONLY=1 ;;
        *)           ARGFILE="$1" ;;
    esac
    shift
done

PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
        PYTHON="${PYTHON:-$candidate}"
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERRO] Python nao encontrado. Instale o Python 3.10 ou mais novo."
    exit 1
fi
echo "[1/4] Python localizado: $PYTHON ($("$PYTHON" -V 2>&1))"

if [ ! -x "$VENV/bin/python" ]; then
    echo "[2/4] Criando o ambiente virtual em $VENV ..."
    "$PYTHON" -m venv "$VENV"
    FORCE=1
else
    echo "[2/4] Ambiente virtual ja existe: $VENV"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"
echo "      Ambiente virtual ativado: $(command -v python)"

if [ -f "$REQ" ]; then
    if [ "$FORCE" = "1" ] || ! python -c 'import tkinterweb' >/dev/null 2>&1; then
        echo "[3/4] Instalando as dependencias do $REQ ..."
        python -m pip install --upgrade pip >/dev/null 2>&1 || true
        python -m pip install -r "$REQ" || echo "[AVISO] Falha ao instalar (sem internet?)."
    else
        echo "[3/4] Dependencias ja instaladas."
    fi
fi

if [ "$SHELLONLY" = "1" ]; then
    echo "Ambiente pronto. Para abrir o editor: python $APPFILE"
    exit 0
fi

echo "[4/4] Abrindo o RD5 PageStudio..."
if [ -n "$ARGFILE" ]; then
    exec python "$APPFILE" "$ARGFILE"
fi
exec python "$APPFILE"
