import time
import logging
import threading
import subprocess
from django.utils import timezone
from .models import BotProcess
from .runner import broadcast_log, broadcast_status, is_docker_available, _ACTIVE_SUBPROCESSES, start_bot_process

logger = logging.getLogger(__name__)

_MONITOR_RUNNING = False
_MONITOR_THREAD = None

def check_bot_alive(process: BotProcess) -> bool:
    if process.status != 'running':
        return False

    if process.id in _ACTIVE_SUBPROCESSES:
        p = _ACTIVE_SUBPROCESSES[process.id]
        if p.poll() is None:
            return True
        return False

    if process.container_id and not process.container_id.startswith("proc-") and is_docker_available():
        try:
            res = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", process.container_id],
                capture_output=True, text=True, timeout=2
            )
            return res.returncode == 0 and 'true' in res.stdout.lower()
        except Exception:
            return False

    if process.pid:
        try:
            import psutil
            if psutil.pid_exists(process.pid):
                p = psutil.Process(process.pid)
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    return True
        except Exception:
            pass

    return False

def check_bot_resources(bot: BotProcess) -> bool:
    """
    Subprocess rejimida bot xotirasini tekshiradi (128 MB limit).
    Agar limit oshsa, server qotmasligi uchun jarayon to'xtatiladi.
    """
    if bot.pid and bot.status == 'running':
        try:
            import psutil
            from django.conf import settings
            p = psutil.Process(bot.pid)
            mem_mb = p.memory_info().rss / (1024 * 1024)
            quota = getattr(bot.owner, 'quota', None) or getattr(bot.owner, 'userquota', None)
            limit_mb = getattr(quota, 'max_ram_mb', getattr(settings, 'MAX_PER_BOT_RAM_MB', 180)) or 180
            if mem_mb > limit_mb * 1.25:
                p.kill()
                bot.status = 'crashed'
                bot.last_error = f"Xotira limiti ({limit_mb} MB) oshib ketdi ({mem_mb:.1f} MB)! Server barqarorligi uchun bot to'xtatildi."
                bot.stopped_at = timezone.now()
                bot.save()
                broadcast_log(bot, f"[Py Hosting Himoya] {bot.last_error}", level='ERROR')
                broadcast_status(bot, "Xotira limiti oshgani sababli to'xtatildi")
                return False
        except Exception:
            pass
    return True

def run_monitor_cycle():
    running_bots = BotProcess.objects.filter(status='running')
    for bot in running_bots:
        try:
            if not check_bot_resources(bot):
                continue

            alive = check_bot_alive(bot)
            if not alive:
                bot.refresh_from_db()
                if bot.status != 'running':
                    continue

                bot.status = 'crashed'
                bot.stopped_at = timezone.now()

                if bot.restart_count < 3:
                    bot.restart_count += 1
                    bot.save()
                    broadcast_log(
                        bot,
                        f"[Py Hosting Himoya] Bot to'xtab qolgani aniqlandi. Avtomatik qayta ishga tushirilmoqda ({bot.restart_count}/3)...",
                        level='WARNING'
                    )
                    try:
                        start_bot_process(bot.file.id, bot.owner)
                    except Exception as e:
                        broadcast_log(bot, f"[Py Hosting Himoya] Qayta ishga tushirishda xatolik: {e}", level='ERROR')
                else:
                    bot.last_error = "Crash-loop aniqlandi: Bot 3 martadan ko'p xatolik bilan to'xtadi."
                    bot.save()
                    broadcast_log(
                        bot,
                        f"[Py Hosting Himoya] {bot.last_error} Bot to'xtatildi.",
                        level='ERROR'
                    )
                    broadcast_status(bot, "Crash-loop sababli to'xtatildi")
        except Exception as e:
            logger.error(f"Error checking bot #{bot.id}: {e}")

def start_monitoring_daemon():
    global _MONITOR_RUNNING, _MONITOR_THREAD
    if _MONITOR_RUNNING:
        return

    _MONITOR_RUNNING = True

    def loop():
        time.sleep(15)
        sync_counter = 0
        while _MONITOR_RUNNING:
            try:
                run_monitor_cycle()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            sync_counter += 1
            if sync_counter >= 4:
                sync_counter = 0
                try:
                    from .startup import sync_disk_changes_to_database
                    sync_disk_changes_to_database()
                except Exception as se:
                    logger.debug(f"Storage sync error: {se}")

            time.sleep(15)

    _MONITOR_THREAD = threading.Thread(target=loop, daemon=True, name="PyHosting-MonitorDaemon")
    _MONITOR_THREAD.start()
