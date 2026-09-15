
#!/bin/bash

# Script per instal·lar dependències i executar el servidor del Dashboard de l'IOC.

trap 'echo; echo "Operació cancel·lada."; exit 130' INT

install_apt_packages() {
    if ! command -v apt-get &> /dev/null; then
        echo "ERROR: No s'ha trobat apt-get per instal·lar paquets automàticament."
        echo "Instal·la manualment: $*"
        exit 1
    fi

    local apt_cmd
    if [ "$(id -u)" -eq 0 ]; then
        apt_cmd=(apt-get)
    elif command -v sudo &> /dev/null; then
        echo "Calen permisos d'administrador per instal·lar: $*"
        apt_cmd=(sudo apt-get)
    else
        echo "ERROR: No s'ha trobat sudo per instal·lar paquets automàticament."
        echo "Instal·la manualment: $*"
        exit 1
    fi

    echo "Si apt/dpkg està ocupat, s'esperarà fins a 5 minuts..."
    "${apt_cmd[@]}" -o DPkg::Lock::Timeout=300 update
    if [ $? -ne 0 ]; then
        echo "ERROR: No s'ha pogut actualitzar la llista de paquets."
        echo "Comprova si hi ha un altre apt en execució i torna-ho a provar."
        return 1
    fi

    "${apt_cmd[@]}" -o DPkg::Lock::Timeout=300 install -y "$@"
}

validate_python() {
    local python_bin="$1"

    "$python_bin" - <<'PY' &> /dev/null
import sys
if sys.version_info < (3, 9):
    raise SystemExit(1)
import ensurepip
import ssl
import venv
import xml.parsers.expat
PY
}

python_version() {
    "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2> /dev/null
}

find_working_python() {
    local candidate candidate_path seen_candidates

    if [ -n "${DASHBOARD_PYTHON:-}" ]; then
        if validate_python "$DASHBOARD_PYTHON"; then
            PYTHON_BIN="$DASHBOARD_PYTHON"
            return 0
        fi

        echo "ERROR: DASHBOARD_PYTHON no apunta a un Python compatible: $DASHBOARD_PYTHON"
        echo "Cal Python >= 3.9 amb venv, ensurepip, ssl i xml.parsers.expat funcionals."
        return 1
    fi

    # Preferim versions estables i explícites abans que el python3 per defecte del sistema.
    for candidate in python3.12 python3.11 python3.13 python3.10 python3.9 python3.14 python3; do
        candidate_path="$(command -v "$candidate" 2> /dev/null)"
        if [ -z "$candidate_path" ]; then
            continue
        fi

        case " $seen_candidates " in
            *" $candidate_path "*) continue ;;
        esac
        seen_candidates="$seen_candidates $candidate_path"

        if validate_python "$candidate_path"; then
            PYTHON_BIN="$candidate_path"
            return 0
        fi
    done

    return 1
}

ensure_python_runtime() {
    if find_working_python; then
        echo "Python seleccionat: $PYTHON_BIN ($(python_version "$PYTHON_BIN"))"
        return
    fi

    if command -v apt-get &> /dev/null; then
        echo "Python compatible no disponible. Intentant instal·lar-lo..."
        install_apt_packages python3 python3-pip python3-venv

        if find_working_python; then
            echo "Python seleccionat: $PYTHON_BIN ($(python_version "$PYTHON_BIN"))"
            return
        fi
    fi

    echo "ERROR: No s'ha trobat cap Python compatible per executar el dashboard."
    echo "Cal Python >= 3.9 amb venv, ensurepip, ssl i xml.parsers.expat funcionals."
    echo "macOS/Homebrew: prova amb 'brew install python@3.12' o executa amb DASHBOARD_PYTHON=/ruta/al/python."
    exit 1
}

ensure_python_runtime

# Canviar al directori de l'aplicació
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/app"
cd "$APP_DIR"

# 1. Comprovar i crear l'entorn virtual si no existeix.
venv_python_version() {
    .venv/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2> /dev/null
}

selected_python_version() {
    "$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2> /dev/null
}

venv_is_usable() {
    [ -x ".venv/bin/python3" ] || return 1
    [ -f ".venv/bin/activate" ] || return 1
    .venv/bin/python3 - <<'PY' &> /dev/null || return 1
import ensurepip
import ssl
import venv
import xml.parsers.expat
PY
    .venv/bin/python3 -m pip --version &> /dev/null
}

if [ -d ".venv" ] && ! venv_is_usable; then
    echo "S'ha trobat un entorn virtual incomplet o trencat. Es recrearà..."
    rm -rf .venv
fi

if [ -d ".venv" ] && [ "$(venv_python_version)" != "$(selected_python_version)" ]; then
    echo "L'entorn virtual existent fa servir Python $(venv_python_version), però s'ha seleccionat $(selected_python_version). Es recrearà..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "Creant entorn virtual a $(pwd)..."
    "$PYTHON_BIN" -m venv .venv
    if [ $? -ne 0 ]; then
        echo "ERROR: No s'ha pogut crear l'entorn virtual."
        echo "Revisa que el paquet venv de Python estigui instal·lat correctament."
        exit 1
    fi
fi

# 2. Activar l'entorn virtual i instal·lar les dependències.
echo "Instal·lant/actualitzant dependències..."
.venv/bin/python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: No s'han pogut instal·lar les dependències des de requirements.txt."
    exit 1
fi

# 3. Comprovar que el fitxer de configuració existeix.
if [ ! -f "../config.json" ]; then
    echo "Error: El fitxer de configuració 'config.json' no s'ha trobat al directori arrel."
    exit 1
fi

# 4. Executar el servidor de Flask.
DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5050}"

echo "\n*** Iniciant el servidor del Dashboard ***"
echo "Obre el teu navegador i ves a http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
echo "Per aturar el servidor, prem CTRL+C en aquesta terminal."
DASHBOARD_HOST="$DASHBOARD_HOST" DASHBOARD_PORT="$DASHBOARD_PORT" .venv/bin/python3 dashboard.py
