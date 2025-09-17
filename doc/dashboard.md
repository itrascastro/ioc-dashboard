# IOC Dashboard — Informe d'auditoria

## Índex
- [Resum executiu](#resum-executiu)
- [Objectiu i abast](#objectiu-i-abast)
- [Arquitectura i funcionament](#arquitectura-i-funcionament)
- [Estructura del repositori](#estructura-del-repositori)
- [Dependències](#dependències)
- [Configuració](#configuració)
- [Personalització per professorat](#personalització-per-professorat)
- [Ús i operativa](#ús-i-operativa)
- [Publicació estàtica a GitHub Pages](#publicació-estàtica-a-github-pages)
- [Seguretat](#seguretat)
- [Qualitat i mantenibilitat](#qualitat-i-mantenibilitat)
- [Limitacions conegudes](#limitacions-conegudes)
- [Roadmap recomanat](#roadmap-recomanat)
- [Procediments de troubleshooting](#procediments-de-troubleshooting)
- [Annex: Fitxers clau](#annex-fitxers-clau)

## Resum executiu
- Objectiu: proveir un panell personalitzat per a professorat de l’IOC que centralitza enllaços habituals i informa de novetats dels cursos Moodle i de correu intern.
- Funcionament: una app Flask serveix una pàgina (`/`) i un endpoint (`/get-moodle-data`) que, amb credencials configurades, inicia sessió a Moodle, consulta endpoints AJAX, composa resultats i actualitza el DOM. En paral·lel genera un HTML estàtic i el puja a GitHub (opcional, segons `config.json`).
- Stack: Python 3 (Flask, requests, BeautifulSoup), HTML/JS/CSS senzill sense build tooling.
- Estat: projecte compacte, amb configuració via `config.json`, sense tests automatitzats, i amb llista de cursos codificada al codi.

## Objectiu i abast
- Per a què serveix: accelerar l’accés diari a recursos i fer visible l’activitat recent (fòrums/avisos) dels cursos i el compte de correus no llegits al Moodle.
- Abast de l’auditoria: revisió de codi i estructura, configuració, mecanismes d’autenticació i scraping, publicació estàtica, seguretat, personalització i operativa.

## Arquitectura i funcionament
- Components principals:
  - Servidor (`app/dashboard.py`): Flask amb rutes `/` i `/get-moodle-data`. Gestiona sessió a Moodle amb `requests.Session`, fa crides a endpoints AJAX i retorna JSON. En segon pla genera un HTML estàtic i, si es configura, el puja a GitHub via API.
  - Client (`app/templates/index.html`): pàgina HTML amb enllaços categorizats, botó de refresc, auto-refresc, toggle de tema i lògica JS per injectar resultats al DOM i mostrar/ocultar contingut.
  - HTML estàtic (`app/dashboard_static.html`): versió generada amb el contingut ja injectat i JS adaptat per entorn sense servidor.
- Flux de dades (en temps real):
  1) L’usuari obre `/` (serveix `index.html`).
  2) El client crida `/get-moodle-data`.
  3) El servidor, si cal, crea sessió a Moodle, obté `sesskey` i llança fils per:
     - Comptar correus no llegits via `lib/ajax/service.php` (mètode `local_mail_get_courses`).
     - Demanar les notificacions per curs via `local/courseoverview/ajax.php?courseid=ID` per a cada curs de `CURSOS_A_MONITORIZAR`.
  4) Retorna JSON amb `courses` (HTML de cada curs) i `mail` (enter).
  5) El client actualitza la UI i configura auto-refresc.
  6) En un fil de fons es genera HTML estàtic i (si s’ha configurat) es puja a GitHub.
- Concurrència: ús de `threading.Thread` per paral·lelitzar consultes (una per curs + correu). Lock per protegir la sessió en logins.

## Estructura del repositori
- Arrel
  - `config.json` / `config.json.example`: configuració d’entorn i secrets (vegeu Seguretat). `config.json` està ignorat per git.
  - `dashboard.sh`: script d’arrencada i preparació de venv + execució del servidor.
  - `doc/`: documentació del projecte (aquí es desa aquest informe).
  - `app/`: codi de l’aplicació.
    - `dashboard.py`: lògica del servidor, scraping i generació d’estàtic.
    - `templates/index.html`: interfície d’usuari i JS de client.
    - `dashboard_static.html`: exemplar d’HTML estàtic generat.
    - `requirements.txt`: dependències Python.

## Dependències
- Python: `Flask`, `requests`, `beautifulsoup4` (vegeu `app/requirements.txt`).
- Sistema: Python 3 i `python3-venv` per crear l’entorn virtual.
- No hi ha gestor de build front-end; el JS/CSS està inline.

## Configuració
- Fitxer `config.json` (no es versiona):
  - `MOODLE_USERNAME`, `MOODLE_PASSWORD`: credencials personals del Moodle.
  - `GITHUB_TOKEN`: token personal per pujar contingut (si cal publicació estàtica).
  - `GITHUB_USERNAME`, `GITHUB_REPO`, `GITHUB_FILE_PATH`: repo i ruta de destí per desar l’HTML estàtic.
  - Recomanat copiar des de `config.json.example` i omplir valors. No publicar aquests valors.
- Cursos a monitoritzar: constants a `app/dashboard.py` en `CURSOS_A_MONITORIZAR` (llista d’IDs del Moodle). Afegiu/traieu IDs segons les necessitats del professorat.
- Plantilla/Enllaços: `app/templates/index.html` conté totes les categories i enllaços (Moodle, Google Drive, eines, etc.). Editeu lliurement per adaptar-los.
- Client (paràmetres):
  - `AUTO_REFRESH_MINUTES` al JS de `index.html` (per defecte 5 minuts).
  - Òptica de tema: mode clar/fosc i automàtic via `prefers-color-scheme`.

## Personalització per professorat
- Credencials: creeu `config.json` amb les credencials personals de Moodle. Manteniu el fitxer fora de control de versions.
- Llista de cursos: actualitzeu `CURSOS_A_MONITORIZAR` a `app/dashboard.py` amb els IDs dels vostres cursos.
- Enllaços de la pàgina: editeu `app/templates/index.html` per:
  - Afegir/ordenar categories.
  - Canviar enllaços (cursos, eines, documents propis, etc.).
- Publicació estàtica (opcional):
  - Definiu `GITHUB_*` a `config.json` per publicar l’HTML generat cap a un repositori (p. ex. `user.github.io/ioc/dashboard/index.html`).
  - Si no voleu publicar, deixeu aquests camps buits; el servidor seguirà funcionant en local i generant el fitxer `dashboard_static.html` localment.

## Ús i operativa
- Preparació i arrencada:
  - Executeu `./dashboard.sh` a l’arrel del projecte. L’script:
    - Crea/activa un entorn virtual `.venv` a `app/`.
    - Instal·la dependències de `requirements.txt`.
    - Verifica `config.json` a l’arrel.
    - Inicia el servidor Flask a `http://127.0.0.1:5000`.
- Interfície:
  - Botó “Refresca Moodle”: llança la consulta en temps real.
  - Auto-refresc: per defecte cada 5 minuts (configurable).
  - Indicadors d’estat: barra de progrés i missatges de fase (sol·licitud/processament/actualització).
  - Tema clar/fosc: toggle i autodetecció.
  - Interacció amb cursos: clic a elements amb classe `local-course-overview-item` desplega/oculta contingut del fòrum.

## Publicació estàtica a GitHub Pages
- Condició d’activació: només s’activa si `GITHUB_TOKEN` no és buit. Si és buit, la generació i la pujada s’ometen i a la consola es mostra la “FASE 2: PROCÉS DE FONS - DESACTIVAT”.
- Generació: després de cada refresc (quan està activada), `dashboard.py` crea `app/dashboard_static.html` injectant-hi el contingut obtingut de Moodle i adaptant el JS (desactiva AJAX, activa auto-reload cada 6 minuts, mostra la data d’actualització, etc.).
- Puja a GitHub (si configurat):
  - Fa un `GET` al contingut per obtenir `sha` si existeix i després un `PUT` a l’API de GitHub amb el fitxer codificat en Base64.
  - Commit a la branca `master` (configurable al codi si cal).
  - Camp destinatari: `GITHUB_USERNAME`/`GITHUB_REPO` i `GITHUB_FILE_PATH`.
- Ús típic: publicar a `user.github.io` i servir l’HTML estàtic com a “dashboard lleuger” sense dependència del servidor local.

## Seguretat
- Secrets i credencials:
  - `config.json` conté secrets i està ignorat via `.gitignore`. Manteniu-lo fora de repos públics i no compartiu’l.
  - Token de GitHub: utilitzeu el mínim abast necessari (repo:contents) i rotació periòdica. Revocar-lo si es sospita d’exposició.
  - Recomanació: considerar `.env` + `python-dotenv` o KMS/gestor de secrets per producció.
- Sessió Moodle i peticions:
  - Gestió de sessió amb `requests.Session` i detecció de sessió expirada per text de login. Existeix recomputació de sessió quan cal.
  - Timeouts establerts (10–20s). No hi ha reintents/backoff; recomanable afegir-los per resiliència.
- Dependències:
  - `requirements.txt` no fixa versions. Recomanable “pinning” (p. ex. `Flask==2.3.3`, etc.) i actualització regular.
- Superfície d’atac:
  - L’app no exposa credencials en respostes. No obstant, qualsevol accés a la màquina on corre el servidor podria llegir `config.json`. Protegiu l’host.
- Publicació estàtica:
  - El contingut generat pot incloure fragments HTML de Moodle. Verifiqueu que no s’hi filtren dades sensibles.

## Qualitat i mantenibilitat
- Estructura clara i compacta; codi llegible i comentat.
- Paral·lelització per fils simple i adequada al volum actual; no hi ha pool ni límits configurables.
- Logging útil a consola amb una utilitat de “caixa” per resum de temps.
- Falta de tests automatitzats i linter/formatador configurat.
- Configuració mixta (fitxer + constants al codi). Millorable externalitzant també `CURSOS_A_MONITORIZAR` i altres paràmetres a `config.json`.

## Limitacions conegudes
- Fragilitat davant canvis d’HTML/DOM o d’endpoints d’IOC Moodle (no es fan servir APIs públiques documentades, sinó endpoints AJAX i scraping parcial).
- Autenticació: si el Moodle aplica 2FA o canvis en el flux de login, el mecanisme actual fallarà.
- Concurrència: sense control de taxa ni reintents; risc de rate limiting o errors transitoris que no es recuperen.
- Publicació: la branca i ruta són literals; canvis d’estratègia (main vs master) calen tocar codi.

## Roadmap recomanat
- Configuració
  - Moure `CURSOS_A_MONITORIZAR`, intervals i paràmetres a `config.json`.
  - Afegir suport `.env` i encriptar secrets en entorns compartits.
- Robustesa
  - Afegir reintents amb backoff i límit de concurrència.
  - Detectar canvis de sessió de manera proactiva amb ping lleuger abans de disparar múltiples crides.
- Publicació
  - Fer opcional l’upload a GitHub amb flag de config.
  - Permetre seleccionar branca i repositori via config.
- Qualitat
  - Pinning de versions i actualització periòdica.
  - Afegir tests bàsics (per exemple, de generació d’HTML estàtic amb fixtures) i un linter.

## Procediments de troubleshooting
- Error “Python 3 no instal·lat” en `dashboard.sh`:
  - Instal·leu `python3`, `python3-pip` i `python3-venv` (Debian/Ubuntu: `sudo apt install python3 python3-pip python3-venv`).
- Error en instal·lar dependències:
  - Comproveu la connexió i permisos del venv. Executeu manualment: `cd app && source .venv/bin/activate && pip install -r requirements.txt`.
- “El fitxer de configuració no existeix”: 
  - Copieu `config.json.example` a `config.json` a l’arrel i ompliu els camps.
- Credencials invàlides o sessió expirada constantment:
  - Reviseu usuari/contrasenya, canvis de política al Moodle i que no hi hagi 2FA. Mireu la consola del servidor per missatges.
- Pujada a GitHub falla:
  - Reviseu `GITHUB_TOKEN` (abasts), usuari/repositori i `GITHUB_FILE_PATH`. Comproveu si la branca és `master` o `main` i adapteu el codi si cal.

## Annex: Fitxers clau
- `dashboard.sh`: script d’arrencada, crea venv, instal·la deps i llança el servidor.
- `app/dashboard.py`:
  - Rutes: `/` i `/get-moodle-data`.
  - Funcions clau: login a Moodle, obtenció de correus no llegits, obtenció de notificacions per curs, generació d’HTML estàtic i pujada via API de GitHub.
  - Constants: `CURSOS_A_MONITORIZAR`, URLs de Moodle i `STATIC_FILENAME`.
- `app/templates/index.html`: interfície, categories/enllaços i lògica de refresc, auto-refresc i tema.
- `app/dashboard_static.html`: sortida generada (exemple). Es sobreescriu en cada cicle.
- `config.json.example`: plantilla de configuració sense secrets.
