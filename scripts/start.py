"""One local launcher for PostgreSQL, migrations, FastAPI and Vite."""
import argparse
import asyncio
import json
import ipaddress
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
WINDOWS = os.name == 'nt'
PYTHON = BACKEND / '.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
CHILDREN = []
sys.path.insert(0, str(BACKEND))

class LaunchError(Exception):
    pass

def say(message):
    print(message, flush=True)

def start(command, cwd=ROOT):
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
    child = subprocess.Popen(list(map(str, command)), cwd=cwd, **options)
    CHILDREN.append(child)
    return child

def run(command, cwd=ROOT):
    child = start(command, cwd)
    result = child.wait()
    CHILDREN.remove(child)
    if result != 0:
        raise LaunchError('Команда завершилась с ошибкой. Подробности — выше в терминале.')

def stop_children():
    # Only stop processes created by this launcher; keep PostgreSQL and existing servers running.
    for child in reversed(CHILDREN):
        try:
            if WINDOWS:
                if child.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in reversed(CHILDREN):
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if WINDOWS:
                    child.kill()
                else:
                    os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()

def read_url(url):
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=1) as response:
            return response.read(1024 * 1024).decode('utf-8')
    except Exception:
        return ''

def api_ready(base):
    try:
        data = json.loads(read_url(base + '/api/health'))
        return data.get('status') == 'ok' and data.get('database') == 'postgresql'
    except (ValueError, AttributeError):
        return False

def frontend_ready(base):
    html = read_url(base)
    return '<title>Tipro — онлайн-чаевые</title>' in html and '/src/main.js' in html

def port_busy(port):
    for host in ('127.0.0.1', '::1'):
        try:
            with socket.create_connection((host, port), timeout=.3):
                return True
        except OSError:
            pass
    return False

def wait_ready(check, label):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in CHILDREN):
            raise LaunchError(f'{label}: процесс завершился с ошибкой, см. вывод выше.')
        if check():
            return
        time.sleep(.3)
    raise LaunchError(f'{label}: сервер не ответил за 60 секунд.')

async def database_ready(settings):
    import asyncpg
    from sqlalchemy.engine import make_url
    url = make_url(settings.database_url)
    try:
        connection = await asyncpg.connect(host=url.host, port=url.port or 5432,
            user=url.username, password=url.password, database=url.database, timeout=3)
        await connection.execute('SELECT 1')
        await connection.close()
        return True
    except Exception:
        # Connection errors may contain credentials: don't print exception details.
        return False

def postgres_bin():
    version_file = BACKEND / '.runtime/pgdata/PG_VERSION'
    data_version = version_file.read_text().strip() if version_file.exists() else '18'
    candidates = [os.environ.get('TIPRO_PG_BIN'), '/private/tmp/tipro-postgres18/bin',
                  '/opt/homebrew/opt/postgresql@18/bin', '/usr/local/opt/postgresql@18/bin',
                  str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'PostgreSQL' / data_version / 'bin')]
    pg_ctl = shutil.which('pg_ctl')
    if pg_ctl:
        candidates.append(str(Path(pg_ctl).parent))
    for candidate in filter(None, candidates):
        directory = Path(candidate)
        if not all((directory / (name + '.exe' if WINDOWS else name)).is_file() for name in ('postgres', 'pg_ctl', 'initdb')):
            continue
        version = subprocess.run([str(directory / ('postgres.exe' if WINDOWS else 'postgres')), '--version'], capture_output=True, text=True)
        if version.returncode == 0 and version.stdout.split()[-1].split('.')[0] == data_version:
            return directory
    raise LaunchError('Не найдены бинарники PostgreSQL ' + data_version +
        '. Установите эту версию и укажите папку bin через TIPRO_PG_BIN. Данные БД сохранены.')

def lan_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
        return any(address in network for network in (
            ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16')))
    except (ValueError, TypeError):
        return False

def detect_lan_host():
    override = os.environ.get('TIPRO_LAN_HOST')
    if override:
        if not lan_ipv4(override):
            raise LaunchError('TIPRO_LAN_HOST должен содержать IPv4-адрес компьютера в локальной сети.')
        return override
    if WINDOWS:
        # A VPN can own the default route. Prefer a private physical adapter address.
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                "Get-NetIPConfiguration | Where-Object { $_.NetAdapter.HardwareInterface -and $_.IPv4DefaultGateway } | ForEach-Object { $_.IPv4Address.IPAddress }"], capture_output=True, text=True, timeout=5)
            for address in result.stdout.splitlines():
                if lan_ipv4(address.strip()):return address.strip()
        except (OSError, subprocess.TimeoutExpired):pass
    # On this Mac the default route can belong to a VPN (utun). Prefer physical Wi-Fi/Ethernet.
    if sys.platform == 'darwin':
        for interface in ('en0', 'en1', 'en2'):
            try:
                result = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', interface],
                    capture_output=True, text=True, timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                continue
            address = result.stdout.strip()
            if result.returncode == 0 and lan_ipv4(address):
                return address
    try:
        # UDP connect only asks the OS to select a route; it does not send a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 80))
            address = probe.getsockname()[0]
            if lan_ipv4(address):
                return address
    except OSError:
        pass
    return None

def configured_frontend(base):
    try:
        return json.loads(read_url(base + '/api/capabilities')).get('frontendUrl')
    except (ValueError, AttributeError):
        return None

def lock_launcher(file):
    if WINDOWS:
        import msvcrt
        if file.seek(0, os.SEEK_END) == 0:
            file.write(b'0');file.flush()
        file.seek(0)
        try:msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:raise BlockingIOError from error
    else:
        import fcntl
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-open', action='store_true', help='Не открывать браузер автоматически')
    args = parser.parse_args()
    if not (BACKEND / '.env').is_file():
        raise LaunchError('Отсутствует backend/.env. Выполните первоначальную настройку из backend/README.md.')
    if not (ROOT / 'node_modules/vite/bin/vite.js').is_file():
        raise LaunchError('Не установлены зависимости Vue. Один раз выполните npm install.')
    node = shutil.which('node')
    if not node:
        raise LaunchError('Не найден Node.js. Установите Node.js и повторите запуск.')
    try:
        from app.config import get_settings
        settings = get_settings()
    except Exception:
        raise LaunchError('Не удалось загрузить backend/.env или зависимости Python. Проверьте настройку по backend/README.md.')
    frontend = urlsplit(settings.frontend_url)
    if frontend.scheme != 'http' or frontend.path not in ('', '/') or frontend.username or frontend.password:
        raise LaunchError('Локальный запуск требует FRONTEND_URL=http://localhost:5173 либо локального IPv4-адреса.')
    if frontend.hostname not in ('localhost', '127.0.0.1') and not lan_ipv4(frontend.hostname):
        raise LaunchError('FRONTEND_URL должен указывать на localhost или локальный IPv4-адрес.')
    frontend_port = frontend.port or 80
    host = detect_lan_host()
    if host:
        frontend_url = f'http://{host}:{frontend_port}'
    else:
        frontend_url = f'http://localhost:{frontend_port}'
        say('Нет адреса локальной сети: сайт будет доступен только на этом компьютере. Подключите Wi-Fi и перезапустите.')
    # Child API gets the same public address as Vue and the QR issuer. Secrets stay in .env.
    os.environ['FRONTEND_URL'] = frontend_url
    os.environ['CORS_ORIGINS'] = json.dumps(list(dict.fromkeys([
        *settings.cors_origins, frontend_url, f'http://localhost:{frontend_port}',
        f'http://127.0.0.1:{frontend_port}'])))
    api_url = 'http://127.0.0.1:8000'
    runtime = BACKEND / '.runtime'
    runtime.mkdir(exist_ok=True)
    # Retain the handle for the whole session. OS releases it even after a crash.
    with (runtime / 'launcher.lock').open('a+b') as lock:
        try:
            lock_launcher(lock)
        except BlockingIOError:
            say('Tipro уже запускается или работает в другом окне.')
            wait_ready(lambda: frontend_ready(frontend_url) and api_ready(api_url), 'Tipro')
            if not args.no_open:
                webbrowser.open(frontend_url)
            return
        say('1/4 · Проверка PostgreSQL…')
        if not asyncio.run(database_ready(settings)):
            from sqlalchemy.engine import make_url
            db_url = make_url(settings.database_url)
            if db_url.host not in ('localhost', '127.0.0.1'):
                raise LaunchError('База из DATABASE_URL недоступна. Проверьте подключение; инструкция — backend/README.md.')
            run([PYTHON, BACKEND / 'scripts/local_postgres.py', '--bin-dir', postgres_bin()])
            if not asyncio.run(database_ready(settings)):
                raise LaunchError('PostgreSQL не отвечает. Проверьте backend/.runtime/postgres.log.')
        say('2/4 · Применение миграций…')
        run([PYTHON, '-m', 'alembic', 'upgrade', 'head'], BACKEND)
        say('3/4 · Запуск FastAPI…')
        if port_busy(8000):
            if not api_ready(api_url):
                raise LaunchError('Порт 8000 занят другим приложением. Освободите его и повторите запуск.')
            if configured_frontend(api_url) != frontend_url:
                raise LaunchError('FastAPI запущен со старым адресом QR. Остановите прежнее окно Tipro (Ctrl+C) и снова нажмите файл запуска.')
            say('FastAPI уже работает — использую запущенный сервер.')
        else:
            start([PYTHON, '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1',
                   '--port', '8000', '--no-access-log'], BACKEND)
            wait_ready(lambda: api_ready(api_url), 'FastAPI')
        say('4/4 · Запуск Vue…')
        if port_busy(frontend_port):
            if not frontend_ready(frontend_url):
                raise LaunchError(f'Порт {frontend_port} занят другим приложением. Освободите его и повторите запуск.')
            say('Vue уже работает — использую запущенный сервер.')
        else:
            start([node, ROOT / 'node_modules/vite/bin/vite.js', '--host', '0.0.0.0',
                   '--port', str(frontend_port), '--strictPort'])
            wait_ready(lambda: frontend_ready(frontend_url), 'Vue')
        wait_ready(lambda: api_ready(frontend_url), 'Прокси Vue → FastAPI')
        say(f'\nTipro готов: {frontend_url}\nТелефон: подключитесь к тому же Wi-Fi и сканируйте QR ресторана.\nДля остановки нажмите Ctrl+C в этом окне. PostgreSQL продолжит работать.\n')
        if not args.no_open:
            webbrowser.open(frontend_url)
        while True:
            if any(child.poll() is not None for child in CHILDREN):
                raise LaunchError('Один из серверов остановился. Подробности — выше в терминале.')
            time.sleep(.5)

def terminate(signum, frame):
    raise KeyboardInterrupt

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, terminate)
    if hasattr(signal, 'SIGHUP'):signal.signal(signal.SIGHUP, terminate)
    try:
        main()
    except KeyboardInterrupt:
        say('\nОстанавливаю серверы, запущенные этим окном…')
    except LaunchError as error:
        say('\nНе удалось запустить Tipro: ' + str(error))
        sys.exit(1)
    finally:
        # npm/Terminal may forward the same interrupt more than once during shutdown.
        for event in (signal.SIGINT, signal.SIGTERM, getattr(signal, 'SIGHUP', signal.SIGTERM)):
            signal.signal(event, signal.SIG_IGN)
        stop_children()
