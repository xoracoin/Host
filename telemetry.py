import logging
import subprocess
from django.utils import timezone
from .models import BotProcess
from .runner import is_docker_available

logger = logging.getLogger(__name__)

def get_bot_telemetry(bot_process: BotProcess) -> dict:
    default_stats = {
        'status': bot_process.status,
        'cpu_percent': 0.0,
        'memory_mb': 0.0,
        'max_memory_mb': 128.0,
        'cpu_limit': 0.25,
        'uptime_seconds': 0,
        'restart_count': bot_process.restart_count,
        'auto_restart': bot_process.auto_restart
    }

    if bot_process.status != 'running':
        return default_stats

    if bot_process.started_at:
        uptime = int((timezone.now() - bot_process.started_at).total_seconds())
        default_stats['uptime_seconds'] = max(0, uptime)

    if bot_process.pid:
        try:
            import psutil
            if psutil.pid_exists(bot_process.pid):
                p = psutil.Process(bot_process.pid)
                if p.is_running():
                    mem_bytes = p.memory_info().rss
                    cpu = p.cpu_percent(interval=None)
                    for child in p.children(recursive=True):
                        try:
                            mem_bytes += child.memory_info().rss
                            cpu += child.cpu_percent(interval=None)
                        except Exception:
                            pass
                    default_stats['memory_mb'] = round(mem_bytes / (1024 * 1024), 2)
                    default_stats['cpu_percent'] = round(min(cpu, 100.0), 1)
                    return default_stats
        except Exception as e:
            logger.debug(f"psutil telemetry error: {e}")

    if bot_process.container_id and not bot_process.container_id.startswith("proc-") and is_docker_available():
        try:
            res = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}},{{.MemUsage}}", bot_process.container_id],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split(',')
                if len(parts) >= 2:
                    cpu_str = parts[0].replace('%', '').strip()
                    mem_str = parts[1].split('/')[0].strip()
                    cpu_val = float(cpu_str) if cpu_str else 0.0
                    mem_mb = 0.0
                    m_lower = mem_str.lower()
                    if 'gib' in m_lower:
                        mem_mb = float(m_lower.replace('gib', '').strip()) * 1024
                    elif 'mib' in m_lower:
                        mem_mb = float(m_lower.replace('mib', '').strip())
                    elif 'kib' in m_lower:
                        mem_mb = float(m_lower.replace('kib', '').strip()) / 1024
                    elif 'b' in m_lower:
                        mem_mb = float(m_lower.replace('b', '').strip()) / (1024 * 1024)

                    default_stats['cpu_percent'] = round(cpu_val, 1)
                    default_stats['memory_mb'] = round(mem_mb, 2)
                    return default_stats
        except Exception as e:
            logger.debug(f"Docker stats telemetry error: {e}")

    return default_stats
