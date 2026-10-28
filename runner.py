import os
import sys
import time
import shutil
import logging
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import BotProcess, BotLog
from apps.filemanager.models import File, Folder

logger = logging.getLogger(__name__)

_ACTIVE_SUBPROCESSES = {}
_ACTIVE_THREADS = {}

MAX_LOGS_PER_PROCESS = 1000

def is_docker_available() -> bool:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        return res.returncode == 0
    except Exception:
        return False

def load_folder_env(folder_path: Path) -> dict:
    env_file = folder_path / '.env'
    data = {}
    if env_file.exists() and env_file.is_file():
        try:
            with open(env_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k:
                            data[k] = v
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
    return data

def build_isolated_environment(working_dir: Path, secrets: dict) -> dict:
    """
    Constructs a sanitized, isolated execution environment for user bot processes.
    Strictly purges all host application secrets, Django configurations,
    database credentials, and private server tokens.
    """
    SAFE_SYSTEM_VARS = [
        'PATH', 'SYSTEMROOT', 'SYSTEMDRIVE', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT',
        'LANG', 'LC_ALL', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'WINDIR'
    ]
    env = {}
    for var in SAFE_SYSTEM_VARS:
        if var in os.environ:
            env[var] = os.environ[var]

    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(working_dir.resolve())

    FORBIDDEN_HOST_KEYS = [
        'SECRET_KEY', 'DJANGO_SETTINGS_MODULE', 'DATABASE_URL', 'REDIS_URL',
        'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT',
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'DATA_ENCRYPTION_KEY',
        'SUPABASE_URL', 'SUPABASE_KEY', 'PGPASSWORD', 'PGUSER', 'PGHOST',
        'PGDATABASE', 'PGPORT', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_CLIENT_ID',
        'CLOUDFLARE_TURNSTILE_SECRET_KEY', 'TURNSTILE_SECRET_KEY',
    ]
    for key in FORBIDDEN_HOST_KEYS:
        env.pop(key, None)

    for k in list(env.keys()):
        if k.startswith(('DJANGO_', 'DATABASE_', 'POSTGRES_', 'SUPABASE_')):
            env.pop(k, None)

    if isinstance(secrets, dict):
        for k, v in secrets.items():
            k_clean = str(k).strip()
            if k_clean and k_clean not in FORBIDDEN_HOST_KEYS and not k_clean.startswith(('DJANGO_', 'DATABASE_')):
                env[k_clean] = str(v).strip()

    return env

def make_linux_sandbox_preexec(user_quota):
    """
    On Linux POSIX systems, hardens process at kernel level before exec:
    - Limits max file size write (RLIMIT_FSIZE: 50MB)
    - Disables memory core dumps (RLIMIT_CORE: 0)
    Note: RLIMIT_NPROC is intentionally omitted because on single-UID container environments (Render),
    it restricts the total thread count of the UID across all processes, preventing Python's
    standard threading / telebot WorkerThreads from spawning ('can't start new thread').
    """
    def _preexec():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except Exception:
            pass
    return _preexec

def broadcast_log(bot_process: BotProcess, line: str, level: str = 'INFO'):
    timestamp = timezone.now()
    try:
        BotLog.objects.create(
            bot_process=bot_process,
            log_line=line,
            level=level
        )
        count = BotLog.objects.filter(bot_process=bot_process).count()
        if count > MAX_LOGS_PER_PROCESS:
            old_ids = BotLog.objects.filter(bot_process=bot_process).order_by('timestamp').values_list('id', flat=True)[:count - MAX_LOGS_PER_PROCESS]
            BotLog.objects.filter(id__in=list(old_ids)).delete()
    except Exception as e:
        logger.error(f"Error saving log: {e}")

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"bot_logs_{bot_process.file.id}",
                {
                    'type': 'bot_log_message',
                    'line': line,
                    'level': level,
                    'timestamp': timestamp.strftime('%H:%M:%S')
                }
            )
    except Exception as e:
        logger.error(f"Error broadcasting log: {e}")

def broadcast_status(bot_process: BotProcess, message: str = ""):
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"bot_logs_{bot_process.file.id}",
                {
                    'type': 'bot_status_message',
                    'status': bot_process.status,
                    'message': message
                }
            )
    except Exception as e:
        logger.error(f"Error broadcasting status: {e}")

def _trigger_delayed_restart(file_id, owner_user, delay_sec=3):
    def _target():
        time.sleep(delay_sec)
        from django.db import close_old_connections
        close_old_connections()
        try:
            p = BotProcess.objects.filter(file_id=file_id, owner=owner_user).first()
            if p and p.status in ['crashed', 'starting']:
                start_bot_process(file_id, owner_user)
        except Exception as err:
            logger.error(f"Auto-restart watchdog error: {err}")
    threading.Thread(target=_target, daemon=True).start()

def stream_process_output(bot_process: BotProcess, proc: subprocess.Popen):
    from django.db import close_old_connections
    from .dependency_manager import parse_missing_module_from_error

    missing_module = None
    has_syntax_error = False

    try:
        for raw_line in iter(proc.stdout.readline, ''):
            if not raw_line:
                break
            line = raw_line.rstrip('\r\n')
            level = 'ERROR' if any(w in line.lower() for w in ['traceback', 'error:', 'exception:', 'critical']) else 'INFO'
            broadcast_log(bot_process, line, level=level)

            parsed_mod = parse_missing_module_from_error(line)
            if parsed_mod:
                missing_module = parsed_mod
            if any(err in line for err in ['SyntaxError:', 'IndentationError:', 'TabError:']):
                has_syntax_error = True

        proc.stdout.close()
        return_code = proc.wait()

        close_old_connections()
        try:
            bot_process.refresh_from_db()
        except Exception:
            return

        if bot_process.status == 'running':
            if return_code == 0:
                bot_process.status = 'stopped'
                bot_process.restart_count = 0
                broadcast_log(bot_process, "[Py Hosting] Bot o'z ishini muvaffaqiyatli yakunladi (kod: 0)", level='INFO')
                bot_process.stopped_at = timezone.now()
                bot_process.save(update_fields=['status', 'restart_count', 'stopped_at', 'updated_at'])
                broadcast_status(bot_process, "Bot to'xtatildi")
            else:
                bot_process.status = 'crashed'
                bot_process.last_error = f"Jarayon {return_code} xato kodi bilan to'xtadi"
                bot_process.stopped_at = timezone.now()
                broadcast_log(bot_process, f"[Py Hosting Xato] Bot xato bilan to'xtadi (kod: {return_code})", level='ERROR')

                if missing_module:
                    bot_process.status = 'stopped'
                    bot_process.last_error = f"Kutubxona topilmadi yoki ruxsat etilmagan: {missing_module}"
                    bot_process.stopped_at = timezone.now()
                    bot_process.save(update_fields=['status', 'stopped_at', 'last_error', 'updated_at'])
                    broadcast_log(
                        bot_process,
                        f"[❌ PyHosting] '{missing_module}' kutubxonasi topilmadi yoki bu serverda ruxsat berilmagan. "
                        f"PyHosting serverida faqat 'telebot' va 'requests' kutubxonalari mavjud.",
                        level='ERROR'
                    )
                    broadcast_status(bot_process, f"Modul topilmadi: {missing_module}")
                    return

                if has_syntax_error:
                    broadcast_log(
                        bot_process,
                        "[❌ Py Hosting] Kodingizda sintaktik xatolik (SyntaxError) mavjud. Serverni asrash uchun avtomatik qayta yoqish to'xtatildi. Iltimos, kodingizni to'g'rilang.",
                        level='ERROR'
                    )
                    bot_process.save(update_fields=['status', 'stopped_at', 'last_error', 'updated_at'])
                    broadcast_status(bot_process, "Sintaksis xatosi tufayli to'xtatildi")
                    return

                MAX_RESTARTS = 5
                if bot_process.auto_restart and bot_process.restart_count < MAX_RESTARTS:
                    bot_process.restart_count += 1
                    bot_process.save(update_fields=['status', 'restart_count', 'stopped_at', 'last_error', 'updated_at'])
                    backoff_sec = 3
                    broadcast_log(
                        bot_process,
                        f"[🛡️ Watchdog Himoyasi] Avtomatik qayta yoqish faol: {backoff_sec} soniyadan so'ng qayta ishga tushiriladi ({bot_process.restart_count}/{MAX_RESTARTS})...",
                        level='WARNING'
                    )
                    broadcast_status(bot_process, f"Avtomatik qayta yoqilmoqda ({bot_process.restart_count}/{MAX_RESTARTS})...")
                    _trigger_delayed_restart(bot_process.file.id, bot_process.owner, delay_sec=backoff_sec)
                else:
                    if bot_process.auto_restart and bot_process.restart_count >= MAX_RESTARTS:
                        broadcast_log(
                            bot_process,
                            f"[🛡️ Watchdog Himoyasi] Crash-loop aniqlandi: Bot ketma-ket {MAX_RESTARTS} marta xatolik bilan to'xtadi. Serverni asrash uchun avtomatik qayta yoqish to'xtatildi.",
                            level='ERROR'
                        )
                    bot_process.save(update_fields=['status', 'stopped_at', 'last_error', 'updated_at'])
                    broadcast_status(bot_process, "Bot xatolik tufayli to'xtadi")

    except Exception as ex:
        logger.exception("Error in stream_process_output")
    finally:
        _ACTIVE_SUBPROCESSES.pop(bot_process.id, None)
        close_old_connections()

def stream_docker_logs(bot_process: BotProcess, container_id: str):
    try:
        cmd = ["docker", "logs", "-f", container_id]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        for raw_line in iter(proc.stdout.readline, ''):
            if not raw_line:
                break
            line = raw_line.rstrip('\r\n')
            level = 'ERROR' if any(w in line.lower() for w in ['traceback', 'error:', 'exception:']) else 'INFO'
            broadcast_log(bot_process, line, level=level)

        proc.stdout.close()
        proc.wait()
    except Exception as e:
        logger.error(f"Error tailing docker logs: {e}")

def get_python_executable() -> str:
    venv_win = Path(settings.BASE_DIR) / '.venv' / 'Scripts' / 'python.exe'
    if venv_win.exists():
        return str(venv_win)
    venv_unix = Path(settings.BASE_DIR) / '.venv' / 'bin' / 'python'
    if venv_unix.exists():
        return str(venv_unix)
    return sys.executable

def start_bot_process(file_id: int, user) -> BotProcess:
    file_obj = File.objects.get(id=file_id, owner=user)

    user_quota = user.quota
    running_count = BotProcess.objects.filter(owner=user, status='running').exclude(file=file_obj).count()
    if running_count >= user_quota.max_running_bots:
        raise ValueError(f"Sizning hisobingizda bir vaqtning o'zida ko'pi bilan {user_quota.max_running_bots} ta bot ishlashi mumkin!")

    bot_process, _ = BotProcess.objects.get_or_create(
        owner=user,
        file=file_obj
    )

    kill_existing_bot_process(bot_process)
    time.sleep(0.3)

    bot_process.status = 'starting'
    bot_process.started_at = timezone.now()
    bot_process.stopped_at = None
    bot_process.last_error = ""
    bot_process.save()
    broadcast_status(bot_process, "Bot ishga tushirilmoqda...")

    for fld in Folder.objects.filter(owner=user):
        try:
            fld.ensure_on_disk()
        except Exception:
            pass
    for f in File.objects.filter(owner=user):
        try:
            f.ensure_on_disk()
        except Exception:
            pass

    file_path = file_obj.ensure_on_disk()
    if not file_path.exists():
        bot_process.status = 'crashed'
        bot_process.last_error = "Fayl diskda topilmadi!"
        bot_process.save()
        broadcast_status(bot_process, bot_process.last_error)
        raise FileNotFoundError("Fayl diskda topilmadi!")

    storage_base = getattr(settings, 'USER_STORAGE_ROOT', Path(settings.MEDIA_ROOT) / 'users')
    user_root = (storage_base / str(user.id)).resolve()
    try:
        if not file_path.resolve().is_relative_to(user_root):
            err_msg = "Xavfsizlik xatosi: Fayl ruxsat etilgan foydalanuvchi katalogidan tashqarida!"
            bot_process.status = 'stopped'
            bot_process.last_error = err_msg
            bot_process.save()
            broadcast_log(bot_process, f"[🚨 XAVFSIZLIK BLOKI] {err_msg}", level='ERROR')
            broadcast_status(bot_process, err_msg)
            raise PermissionError(err_msg)
    except AttributeError:
        try:
            file_path.resolve().relative_to(user_root)
        except ValueError:
            err_msg = "Xavfsizlik xatosi: Fayl ruxsat etilgan foydalanuvchi katalogidan tashqarida!"
            bot_process.status = 'stopped'
            bot_process.last_error = err_msg
            bot_process.save()
            raise PermissionError(err_msg)

    from .security_guard import CodeSecurityGuard
    is_safe, sec_reason = CodeSecurityGuard.scan_file(file_path, user=user)
    if not is_safe:
        bot_process.status = 'stopped'
        bot_process.last_error = sec_reason
        bot_process.save()
        broadcast_log(bot_process, f"[🚨 XAVFSIZLIK BLOKI] {sec_reason}", level='ERROR')
        broadcast_status(bot_process, f"Xavfsizlik tizimi to'xtatdi: {sec_reason}")
        raise PermissionError(sec_reason)

    from .dependency_manager import validate_bot_dependencies
    try:
        code_text = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        code_text = ""
    is_valid_deps, forbidden_modules = validate_bot_dependencies(code_text, folder_path=file_path.parent)
    if not is_valid_deps:
        forbidden_str = ", ".join(forbidden_modules)
        err_msg = f"Ruxsat etilmagan kutubxona aniqlandi: '{forbidden_str}'"
        bot_process.status = 'stopped'
        bot_process.last_error = err_msg
        bot_process.stopped_at = timezone.now()
        bot_process.save()
        broadcast_log(bot_process, f"[🚨 PyHosting Cheklov] Ruxsat etilmagan kutubxona aniqlandi: '{forbidden_str}'!", level='ERROR')
        broadcast_log(
            bot_process,
            "[⚠️ Ma'lumot] PyHosting bepul serverida 24/7 barqaror ishlashni ta'minlash uchun "
            "faqat 'telebot' (pyTelegramBotAPI) va 'requests' kutubxonalariga ruxsat berilgan.",
            level='WARNING'
        )
        broadcast_log(bot_process, "[💡 Yechim] Iltimos, botingizni 'telebot' kutubxonasiga moslashtiring!", level='INFO')
        broadcast_status(bot_process, f"Ruxsat etilmagan kutubxona: {forbidden_str}")
        raise PermissionError(err_msg)

    from .dependency_manager import check_telegram_bot_signature
    is_tg_bot, tg_err = check_telegram_bot_signature(code_text, folder_path=file_path.parent)
    if not is_tg_bot:
        bot_process.status = 'stopped'
        bot_process.last_error = tg_err
        bot_process.stopped_at = timezone.now()
        bot_process.save()
        broadcast_log(bot_process, f"[🚨 PyHosting Cheklov] {tg_err}", level='ERROR')
        broadcast_status(bot_process, "Faqat Telegram bot ruxsat etilgan")
        raise PermissionError(tg_err)

    docker_available = is_docker_available()

    folder_env = load_folder_env(file_path.parent)
    db_env = bot_process.get_decrypted_env()
    merged_env = {**folder_env, **db_env}

    if merged_env:
        broadcast_log(bot_process, f"[🔐 Secrets] {len(merged_env)} ta muhit o'zgaruvchisi (.env) bot jarayoniga uzatildi.", level='INFO')

    if docker_available:
        img_check = subprocess.run(["docker", "image", "inspect", "pyhosting/bot-runner"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if img_check.returncode != 0:
            broadcast_log(bot_process, "[Docker] 'pyhosting/bot-runner' obrazi mavjud emas, avtomatik yig'ilmoqda...", level='INFO')
            docker_dir = Path(settings.BASE_DIR) / 'docker'
            subprocess.run(
                ["docker", "build", "-f", "bot_runner.Dockerfile", "-t", "pyhosting/bot-runner", "."],
                cwd=str(docker_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        container_name = f"bot_{user.id}_{file_obj.id}"
        subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        mount_dir = str(file_path.parent.resolve())
        user_ram = getattr(user_quota, 'max_ram_mb', 256) or 256
        cmd = [
            "docker", "run", "-d",
            f"--memory={user_ram}m",
            "--cpus=0.5",
            "--pids-limit=50",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--name", container_name,
            "-v", f"{mount_dir}:/app",
            "-e", f"BOT_ENTRY_FILE={file_obj.name}"
        ]

        for k, v in merged_env.items():
            cmd.extend(["-e", f"{str(k).strip()}={str(v).strip()}"])

        cmd.append("pyhosting/bot-runner")

        broadcast_log(bot_process, f"[Docker] Konteyner ishga tushirilmoqda: {container_name}...", level='INFO')
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_id = res.stdout.strip()
            bot_process.container_id = container_id
            bot_process.status = 'running'
            bot_process.save()
            broadcast_status(bot_process, "Bot muvaffaqiyatli ishga tushdi")
            broadcast_log(bot_process, f"[Docker] Konteyner ID: {container_id[:12]} ({user_ram}MB RAM, 0.5 CPU limit, sandbox himoyalangan)", level='INFO')

            t = threading.Thread(target=stream_docker_logs, args=(bot_process, container_id), daemon=True)
            t.start()
            return bot_process

        except subprocess.CalledProcessError as e:
            bot_process.status = 'crashed'
            bot_process.last_error = f"Docker start xatosi: {e.stderr}"
            bot_process.save()
            broadcast_log(bot_process, f"[Docker Xato] {e.stderr}", level='ERROR')
            broadcast_status(bot_process, "Docker xatosi")
            raise RuntimeError(bot_process.last_error)
    else:
        broadcast_log(bot_process, "[Py Hosting Runner] Xavfsiz izolyatsiyalangan Python jarayonida ishga tushirilmoqda...", level='INFO')
        broadcast_log(bot_process, f"[Py Hosting Runner] Fayl: {file_obj.get_relative_path()}", level='INFO')

        env = build_isolated_environment(file_path.parent, merged_env)

        extra_kwargs = {}
        if os.name == 'posix':
            extra_kwargs['preexec_fn'] = make_linux_sandbox_preexec(user_quota)

        jail_guard_path = Path(settings.BASE_DIR) / 'apps' / 'botengine' / 'jail_guard.py'
        cmd_args = [
            get_python_executable(),
            "-u",
            str(jail_guard_path),
            str(user_root),
            str(file_path)
        ]

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=str(file_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                env=env,
                **extra_kwargs
            )

            bot_process.pid = proc.pid
            bot_process.status = 'running'
            bot_process.container_id = f"proc-{proc.pid}"
            bot_process.save()

            _ACTIVE_SUBPROCESSES[bot_process.id] = proc

            broadcast_status(bot_process, "Bot muvaffaqiyatli ishga tushdi")
            broadcast_log(bot_process, f"[Py Hosting Runner] Jarayon PID #{proc.pid} sifatida ishga tushirildi (24/7 faol)", level='INFO')

            t = threading.Thread(target=stream_process_output, args=(bot_process, proc), daemon=True)
            _ACTIVE_THREADS[bot_process.id] = t
            t.start()

            return bot_process

        except Exception as e:
            bot_process.status = 'crashed'
            bot_process.last_error = str(e)
            bot_process.save()
            broadcast_log(bot_process, f"[Py Hosting Xato] Jarayonni boshlashda xatolik: {e}", level='ERROR')
            broadcast_status(bot_process, "Ishga tushirishda xatolik")
            raise

def kill_existing_bot_process(bot_process: BotProcess):
    """
    Safely and aggressively terminates any running subprocess, thread, or OS process tree
    associated with this bot. Guarantees zero zombie processes to prevent Telegram API 409 Conflict.
    """
    if bot_process.container_id and not bot_process.container_id.startswith("proc-"):
        try:
            subprocess.run(["docker", "rm", "-f", bot_process.container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Error stopping docker container: {e}")

    proc = _ACTIVE_SUBPROCESSES.pop(bot_process.id, None)
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as e:
            logger.debug(f"Error terminating in-memory subprocess: {e}")

    if bot_process.pid:
        try:
            import psutil
            if psutil.pid_exists(bot_process.pid):
                p = psutil.Process(bot_process.pid)
                if p.pid != os.getpid():
                    for child in p.children(recursive=True):
                        try:
                            child.kill()
                        except Exception:
                            pass
                    p.kill()
        except Exception as e:
            logger.debug(f"Error killing PID tree #{bot_process.pid}: {e}")
        bot_process.pid = None

def stop_bot_process(bot_process: BotProcess) -> BotProcess:
    broadcast_log(bot_process, "[Py Hosting] Bot to'xtatilmoqda...", level='INFO')

    kill_existing_bot_process(bot_process)

    bot_process.status = 'stopped'
    bot_process.stopped_at = timezone.now()
    bot_process.restart_count = 0
    bot_process.save()

    broadcast_log(bot_process, "[Py Hosting] Bot to'xtatildi.", level='INFO')
    broadcast_status(bot_process, "Bot to'xtatildi")

    return bot_process

