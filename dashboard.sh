
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

ensure_python3() {
    if command -v python3 &> /dev/null; then
        return
    fi

    echo "Python 3 no està instal·lat. Intentant instal·lar-lo..."
    install_apt_packages python3 python3-pip python3-venv

    if ! command -v python3 &> /dev/null; then
        echo "ERROR: No s'ha pogut instal·lar Python 3."
        exit 1
    fi
}

ensure_python_venv() {
    if python3 -c "import venv, ensurepip" &> /dev/null; then
        return
    fi

    local python_version
    python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

    echo "El mòdul venv/ensurepip de Python no està disponible. Intentant instal·lar-lo..."
    if ! install_apt_packages "python${python_version}-venv"; then
        echo "ERROR: No s'ha pogut instal·lar python${python_version}-venv."
        echo "Comprova si hi ha un altre apt en execució i torna-ho a provar."
        exit 1
    fi

    if ! python3 -c "import venv, ensurepip" &> /dev/null; then
        echo "ERROR: No s'ha pogut instal·lar el mòdul venv/ensurepip de Python."
        echo "Prova manualment amb: sudo apt install python${python_version}-venv"
        exit 1
    fi
}

ensure_python3
ensure_python_venv

# Canviar al directori de l'aplicació
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/app"
cd "$APP_DIR"

# 1. Comprovar i crear l'entorn virtual si no existeix.
if [ -d ".venv" ] && { [ ! -x ".venv/bin/python3" ] || [ ! -f ".venv/bin/activate" ] || [ ! -x ".venv/bin/pip" ]; }; then
    echo "S'ha trobat un entorn virtual incomplet. Es recrearà..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "Creant entorn virtual a $(pwd)..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "ERROR: No s'ha pogut crear l'entorn virtual."
        echo "Revisa que el paquet venv de Python estigui instal·lat correctament."
        exit 1
    fi
fi

# 2. Activar l'entorn virtual i instal·lar les dependències.
echo "Instal·lant/actualitzant dependències..."
source .venv/bin/activate && pip install -r requirements.txt
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
source .venv/bin/activate && DASHBOARD_HOST="$DASHBOARD_HOST" DASHBOARD_PORT="$DASHBOARD_PORT" python3 dashboard.py
