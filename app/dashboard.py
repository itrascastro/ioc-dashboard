import requests
from bs4 import BeautifulSoup
import json
import re
import os
import threading
from flask import Flask, render_template, jsonify
import time
import base64
from datetime import datetime

# Clase para colores de la consola
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_boxed_summary(title, lines, color=bcolors.OKBLUE):
    """Dibuja un recuadro elegante en la consola con un resumen de tiempos."""
    # Limpiar líneas vacías al final
    while lines and not lines[-1].strip():
        lines.pop()

    # Calcular el ancho máximo necesario, ignorando los códigos de color ANSI
    clean_title = re.sub(r'\033\[[0-9;]*m', '', title)
    max_len = len(clean_title) + 4
    for line in lines:
        clean_line = re.sub(r'\033\[[0-9;]*m', '', line)
        if len(clean_line) > max_len:
            max_len = len(clean_line)

    # --- Dibujar la caja con caracteres gruesos ---
    # Borde superior
    print(f"{color}┏━ {bcolors.BOLD}{title}{bcolors.ENDC}{color} {'━' * (max_len - len(clean_title) - 1)}┓{bcolors.ENDC}")

    # Líneas de contenido
    for line in lines:
        clean_line = re.sub(r'\033\[[0-9;]*m', '', line)
        padding = ' ' * (max_len - len(clean_line))
        print(f"{color}┃{bcolors.ENDC} {line} {padding}{color}┃{bcolors.ENDC}")

    # Borde inferior
    print(f"{color}┗{'━' * (max_len + 2)}┛{bcolors.ENDC}")

# --- LECTURA DE CONFIGURACIÓN ---
# Construir la ruta al config.json, que está un nivel por encima del script
script_dir = os.path.dirname(__file__)
config_path = os.path.join(script_dir, '..', 'config.json')

CONFIG = {}
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        CONFIG = json.load(f)
else:
    print(f"ERROR: El fitxer de configuració no existeix a la ruta esperada: {os.path.abspath(config_path)}")
    exit()

USERNAME = CONFIG.get('MOODLE_USERNAME', '')
PASSWORD = CONFIG.get('MOODLE_PASSWORD', '')

# --- CONFIGURACIÓN MOODLE ---
LOGIN_URL = 'https://ioc.xtec.cat/campus/login/index.php'
DASHBOARD_URL = 'https://ioc.xtec.cat/campus/my/'
AJAX_COURSE_URL = 'https://ioc.xtec.cat/campus/local/courseoverview/ajax.php?courseid={course_id}'
AJAX_SERVICE_URL = 'https://ioc.xtec.cat/campus/lib/ajax/service.php'

# --- CONFIGURACIÓN GITHUB ---
GITHUB_TOKEN = CONFIG.get('GITHUB_TOKEN', '')
GITHUB_USERNAME = CONFIG.get('GITHUB_USERNAME', '')
GITHUB_REPO = CONFIG.get('GITHUB_REPO', '')
GITHUB_FILE_PATH = CONFIG.get('GITHUB_FILE_PATH', '')
STATIC_FILENAME = 'dashboard_static.html'

CURSOS_A_MONITORIZAR = [
    {'id': '836'}, {'id': '5626'}, {'id': '841'}, {'id': '16025'},
    {'id': '15805'}, {'id': '16071'}, {'id': '15821'}, {'id': '15820'},
    {'id': '15824'}, {'id': '15826'}, {'id': '15827'}, {'id': '1576'},
    {'id': '16088'}, {'id': '848'}, {'id': '16018'}, {'id': '840'},
    {'id': '3326'}, {'id': '16093'}, {'id': '15338'}, {'id': '1521'}, {'id': '1519'}
]

# --- FUNCIONES DE OBTENCIÓN DE DATOS (RÁPIDAS) ---
def login_and_get_session_data(session):
    print(f"{bcolors.OKBLUE}Iniciant sessió amb Requests...{bcolors.ENDC}")
    payload = {'username': USERNAME, 'password': PASSWORD}
    try:
        login_response = session.post(LOGIN_URL, data=payload, timeout=10)
        login_response.raise_for_status()
        if "loginerrors" in login_response.text or "login/index.php" in login_response.url: 
            print(f"{bcolors.FAIL}ERROR: Credencials invàlides o pàgina de login inesperada.{bcolors.ENDC}")
            return None
        dashboard_response = session.get(DASHBOARD_URL, timeout=10)
        dashboard_response.raise_for_status()
        match = re.search(r'"sesskey":"([^"]+)"', dashboard_response.text)
        if match: 
            print(f"{bcolors.OKGREEN}Sessió obtinguda correctament.{bcolors.ENDC}")
            return match.group(1)
        return None
    except requests.exceptions.RequestException as e:
        print(f"{bcolors.FAIL}ERROR de xarxa durant el login: {e}{bcolors.ENDC}")
        return None

def get_unread_mail_count(session, sesskey, mail_data, timing_results):
    start_time = time.monotonic()
    count = 0
    try:
        if not sesskey:
            raise ValueError("Sesskey no disponible.")
        ajax_payload = [{"index": 0, "methodname": "local_mail_get_courses", "args": {}}]
        ajax_url = f"{AJAX_SERVICE_URL}?sesskey={sesskey}&info=local_mail_get_courses"
        response = session.post(ajax_url, json=ajax_payload, timeout=20)
        response.raise_for_status()
        # Si la respuesta contiene texto de login, la sesión ha caducado
        if "login/index.php" in response.text:
            mail_data['count'] = 'SESSION_EXPIRED'
        else:
            data = response.json()
            if data and not data[0].get("error"): 
                count = sum(c.get("unread", 0) for c in data[0].get("data", []))
            mail_data['count'] = count
    except Exception:
        mail_data['count'] = 0 # En caso de otro error, asumimos 0
    timing_results['Correu'] = time.monotonic() - start_time

def get_course_notifications(session, course_id, results_dict, timing_results):
    start_time = time.monotonic()
    try:
        ajax_url = AJAX_COURSE_URL.format(course_id=course_id)
        response = session.get(ajax_url, timeout=20)
        response.raise_for_status()
        html_content = response.text
        # Comprobación de sesión caducada
        if "login/index.php" in html_content and "loginerrors" not in html_content:
            results_dict[course_id] = 'SESSION_EXPIRED'
        elif "local-course-overview-item" in html_content:
            results_dict[course_id] = html_content
        else:
            results_dict[course_id] = None
    except Exception:
        results_dict[course_id] = None
    timing_results[f'Curs {course_id}'] = time.monotonic() - start_time

def generate_static_html(final_data):
    try:
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        course_containers = soup.find_all('div', class_='course-container')
        for container in course_containers:
            link = container.find('a', href=lambda x: x and 'ioc.xtec.cat/campus/course/view.php' in x)
            if link:
                course_id_match = re.search(r'id=(\d+)', link.get('href', ''))
                if course_id_match:
                    course_id = course_id_match.group(1)
                    if final_data["courses"].get(course_id):
                        wrapper = soup.new_tag('div', **{'class': 'ajax-notification-wrapper content-updated'})
                        notification_soup = BeautifulSoup(final_data["courses"][course_id], 'html.parser')
                        wrapper.append(notification_soup)
                        container.append(wrapper)

        mail_count = final_data.get("mail", 0)
        if mail_count > 0:
            mail_link = soup.find('a', href=lambda x: x and 't=inbox' in x)
            if mail_link:
                mail_badge = soup.new_tag('span', **{'class': 'mail-notification content-updated'})
                mail_icon_soup = BeautifulSoup(f'''
                    <img class="icon" alt="Correus no llegits" title="Correus no llegits" 
                         src="https://ioc.xtec.cat/campus/theme/image.php/boostioc/mod_forum/1749649652/icon">
                    <span class="mail-count">{mail_count}</span>
                ''', 'html.parser')
                for element in mail_icon_soup:
                    if element.name: mail_badge.append(element)
                mail_link.append(mail_badge)

        for script in soup.find_all('script'): script.decompose()
        new_script = soup.new_tag('script')
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        fecha_corta = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        javascript_code = f"""
        // === VERSIÓ ESTÁTICA GENERADA EL {fecha_actual} ===
        
        const moodleStatusEl = document.getElementById('moodle-status');
        const refreshButton = document.getElementById('refresh-moodle');
        const countdownEl = document.getElementById('auto-refresh-countdown');
        
        function disableAjaxFeatures() {{
            if (refreshButton) {{ refreshButton.style.display = 'none'; }}
            if (moodleStatusEl) {{ moodleStatusEl.textContent = 'Versió estàtica - Última actualització: {fecha_corta}'; }}
            if (countdownEl) {{ countdownEl.style.display = 'none'; }}
        }}
        
        function startStaticAutoRefresh() {{
            setInterval(() => window.location.reload(), 6 * 60 * 1000);
        }}
        
        function setupAjaxClickHandlers() {{
            document.querySelectorAll('.local-course-overview-item').forEach(item => {{
                item.addEventListener('click', function(e) {{
                    e.preventDefault(); e.stopPropagation();
                    const courseContainer = this.closest('[id*="local-course-overview-container-"]');
                    if (courseContainer) {{
                        const courseId = courseContainer.id.split('-').pop();
                        const hiddenDiv = document.getElementById(`local-course-overview-forum-${{courseId}}`);
                        if (hiddenDiv) {{ hiddenDiv.style.display = (hiddenDiv.style.display === 'none' || hiddenDiv.style.display === '') ? 'block' : 'none'; }}
                    }}
                }});
            }});
        }}
        
        function showDateTime() {{ 
            const now = new Date(); 
            document.getElementById('datetime').innerHTML = `${{now.toLocaleDateString('ca-ES')}} ${{now.toLocaleTimeString('ca-ES')}}`; 
        }}
        
        const toggleButton = document.getElementById('theme-toggle');
        function applyTheme() {{ 
            const d = window.matchMedia('(prefers-color-scheme: dark)').matches; 
            document.body.classList.toggle('dark-mode',d); 
            document.body.classList.toggle('light-mode',!d); 
            toggleButton.textContent=d?'Light':'Dark';
        }}
        
        toggleButton.addEventListener('click', () => {{ 
            document.body.classList.toggle('dark-mode'); 
            document.body.classList.toggle('light-mode'); 
            toggleButton.textContent = document.body.classList.contains('dark-mode') ? 'Light' : 'Dark'; 
        }});
        
        document.addEventListener('DOMContentLoaded', function() {{
            disableAjaxFeatures();
            setupAjaxClickHandlers();
            startStaticAutoRefresh();
            showDateTime(); 
            setInterval(showDateTime, 1000);
            applyTheme(); 
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
        }});
        """
        new_script.string = javascript_code
        soup.find('body').append(new_script)
        
        with open(STATIC_FILENAME, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        return (str(soup), f"Fitxer '{STATIC_FILENAME}' generat correctament.")
    except Exception as e:
        return (None, f"ERROR generant HTML estàtic: {e}")

def upload_to_github(html_content):
    if not html_content: return "No s'ha generat HTML, pujada cancel·lada."
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    try:
        get_response = requests.get(api_url, headers=headers)
        sha = get_response.json()['sha'] if get_response.status_code == 200 else None
        commit_data = {
            'message': f'Dashboard Update - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'content': base64.b64encode(html_content.encode('utf-8')).decode('utf-8'),
            'branch': 'master'
        }
        if sha: commit_data['sha'] = sha
        put_response = requests.put(api_url, headers=headers, json=commit_data)
        if put_response.status_code in [200, 201]: 
            return "Pujat a GitHub correctament!"
        else: 
            return f"ERROR pujant a GitHub: {put_response.text}"
    except Exception as e: 
        return f"ERROR durant la pujada a GitHub: {e}"

def update_static_site_in_background(final_data):
    start_time_str = datetime.now().strftime('%H:%M:%S')
    total_bg_start = time.monotonic()
    summary_lines = []

    # Generación de HTML
    gen_start = time.monotonic()
    static_html, gen_message = generate_static_html(final_data)
    gen_time = time.monotonic() - gen_start
    summary_lines.append(f"- Generació HTML: {gen_time:.2f}s. ({gen_message})")

    # Subida a GitHub
    upload_start = time.monotonic()
    upload_message = upload_to_github(static_html)
    upload_time = time.monotonic() - upload_start
    summary_lines.append(f"- Pujada a GitHub: {upload_time:.2f}s. ({upload_message})")

    summary_lines.append("")
    total_time = time.monotonic() - total_bg_start
    summary_lines.append(f"{bcolors.BOLD}Temps Total Procés de Fons: {total_time:.2f} segons{bcolors.ENDC}")

    print_boxed_summary(f"FASE 2: PROCÉS DE FONS - {start_time_str}", summary_lines, color=bcolors.HEADER)

# --- LÓGICA DEL SERVIDOR FLASK ---

app = Flask(__name__)
moodle_session = None
moodle_sesskey = None
session_lock = threading.Lock()

# --- VERSIÓ ANTERIOR DE LA GESTIÓ DE SESSIÓ (PROACTIVA) ---
# def check_session_is_valid(session):
#     """Comprueba si la sesión actual de Moodle sigue siendo válida."""
#     if not session:
#         return False
#     try:
#         # Hacemos una petición a una página que requiere login
#         response = session.get(DASHBOARD_URL, timeout=10, allow_redirects=False)
#         response.raise_for_status()
#         # Si nos redirige a la página de login, la sesión ha caducado
#         if response.status_code == 200 and "login/index.php" not in response.url:
#             return True
#         return False
#     except requests.exceptions.RequestException:
#         return False

# def ensure_moodle_session():
#     """
#     Asegura que tenemos una sesión de Moodle válida.
#     Si no la tenemos o ha caducado, crea una nueva.
#     Usa un Lock para evitar que múltiples hilos intenten loguearse a la vez.
#     """
#     global moodle_session, moodle_sesskey
#     with session_lock:
#         if check_session_is_valid(moodle_session):
#             print("\n--- La sessió de Moodle existent és vàlida. Reutilitzant. ---")
#         else:
#             # ... (lógica de creación de nueva sesión) ...
#     return True

def create_new_moodle_session():
    """Crea y guarda una nueva sesión de Moodle."""
    global moodle_session, moodle_sesskey
    with session_lock:
        print(f"\n{bcolors.WARNING}--- Iniciant nova sessió de Moodle... ---{bcolors.ENDC}")
        new_session = requests.Session()
        new_session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'})
        
        login_start = time.monotonic()
        new_sesskey = login_and_get_session_data(new_session)
        
        if new_sesskey:
            moodle_session = new_session
            moodle_sesskey = new_sesskey
            print(f"{bcolors.OKGREEN}--- Nova sessió de Moodle establerta. {bcolors.BOLD}Temps Login: {time.monotonic() - login_start:.2f} segons{bcolors.ENDC}")
            return True
        else:
            print(f"{bcolors.FAIL}--- ERROR FATAL: No s'ha pogut establir la sessió de Moodle. ---")
            moodle_session = None
            moodle_sesskey = None
            return False

@app.route('/')
def dashboard_page():
    return render_template('index.html')

@app.route('/get-moodle-data')
def get_moodle_data():
    start_time_str = datetime.now().strftime('%H:%M:%S')
    print_boxed_summary(f"NOVA PETICIÓ - {start_time_str}", [], color=bcolors.OKGREEN)
    total_start = time.monotonic()

    if not moodle_session:
        print(f"{bcolors.WARNING}Sessió no existent, forçant nou login.{bcolors.ENDC}")
        if not create_new_moodle_session():
            return jsonify({"error": "No s'ha pogut establir la sessió amb Moodle."}), 500

    session = moodle_session
    sesskey = moodle_sesskey

    course_results, mail_result, threads, timing_results = {}, {'count': 0}, [], {}
    
    mail_thread = threading.Thread(target=get_unread_mail_count, args=(session, sesskey, mail_result, timing_results))
    threads.append(mail_thread)
    mail_thread.start()

    for curso in CURSOS_A_MONITORIZAR:
        thread = threading.Thread(target=get_course_notifications, args=(session, curso['id'], course_results, timing_results))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    session_expired = mail_result.get('count') == 'SESSION_EXPIRED' or any(r == 'SESSION_EXPIRED' for r in course_results.values())

    if session_expired:
        print(f"{bcolors.FAIL}\n--- S'ha detectat una sessió caducada! Forçant un nou login per al pròxim cicle. ---{bcolors.ENDC}")
        create_new_moodle_session()
        mail_result['count'] = 0 # Reset para no romper el JSON

    # Preparar resumen para la caja
    summary_lines = []
    for task, duration in sorted(timing_results.items(), key=lambda item: item[1], reverse=True):
        summary_lines.append(f"  - {task:<15}: {duration:.2f} segons")
    
    total_time = time.monotonic() - total_start
    summary_lines.append("") # Línea en blanco
    summary_lines.append(f"{bcolors.BOLD}Temps Total Obtenció Dades: {total_time:.2f} segons{bcolors.ENDC}")

    print_boxed_summary(f"FASE 1: OBTENCIÓ DE DADES - {start_time_str}", summary_lines, color=bcolors.OKBLUE)

    final_data = {"courses": course_results, "mail": mail_result['count']}
    threading.Thread(target=update_static_site_in_background, args=(final_data,)).start()
    
    return jsonify(final_data)

if __name__ == '__main__':
    if not os.path.exists('templates/index.html'):
        print("ERROR: El fitxer 'templates/index.html' no existeix.")
    else:
        # Silenciar los logs de acceso de Flask/Werkzeug
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        print("Establiment de la sessió inicial de Moodle...")
        create_new_moodle_session() # Login inicial al arrancar
        print(f"{bcolors.OKGREEN}Servidor Flask iniciat. Obre http://127.0.0.1:5000.{bcolors.ENDC}")
        app.run(host='127.0.0.1', port=5000, debug=False)