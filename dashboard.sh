
#!/bin/bash

# Script per instal·lar dependències i executar el servidor del Dashboard de l'IOC.

# 0. Comprovar si Python 3 està instal·lat
if ! command -v python3 &> /dev/null
then
    echo "ERROR: Python 3 no està instal·lat."
    echo "Si us plau, instal·la Python 3 per poder executar aquest script."
    echo "En sistemes Debian/Ubuntu, pots provar amb: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Canviar al directori de l'aplicació
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/app"
cd "$APP_DIR"

# 1. Comprovar i crear l'entorn virtual si no existeix.
if [ ! -d ".venv" ]; then
    echo "Creant entorn virtual a $(pwd)..."
    python3 -m venv .venv
    # Comprovació d'error millorada
    if [ $? -ne 0 ]; then
        echo "ERROR: No s'ha pogut crear l'entorn virtual."
        echo "Això normalment passa si falta el paquet 'python3-venv'."
        echo "En sistemes Debian/Ubuntu, prova d'instal·lar-lo amb: sudo apt install python3-venv"
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
echo "\n*** Iniciant el servidor del Dashboard ***"
echo "Obre el teu navegador i ves a http://127.0.0.1:5000"
echo "Per aturar el servidor, prem CTRL+C en aquesta terminal."
source .venv/bin/activate && python3 dashboard.py
