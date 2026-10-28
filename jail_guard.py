"""
PyHosting Enterprise Zero-Trust Jail Sandbox Guard
Enforces kernel-level filesystem confinement, disables subprocess/shell execution,
and eliminates path traversal vulnerabilities during Python bot execution.
"""
import sys
import os
import io
import builtins
import pathlib
import runpy
from pathlib import Path

if len(sys.argv) < 3:
    print("Xato: Jail Guard noto'g'ri argumentlar bilan chaqirildi.", file=sys.stderr)
    sys.exit(1)

JAIL_USER_ROOT = Path(sys.argv[1]).resolve()
TARGET_SCRIPT = Path(sys.argv[2]).resolve()

USER_ARGV = [str(TARGET_SCRIPT)] + sys.argv[3:]

SYSTEM_READ_ALLOWED = set()
for p in [sys.prefix, sys.base_prefix, getattr(sys, 'real_prefix', None)]:
    if p:
        try:
            SYSTEM_READ_ALLOWED.add(Path(p).resolve())
        except Exception:
            pass

for sp in sys.path:
    if sp:
        try:
            res_sp = Path(sp).resolve()
            if any(res_sp == s or s in res_sp.parents for s in SYSTEM_READ_ALLOWED):
                SYSTEM_READ_ALLOWED.add(res_sp)
        except Exception:
            pass

def _is_path_allowed(target, for_write: bool = False) -> bool:
    """
    Validates if a file/directory path is strictly permitted.
    Write is strictly restricted to JAIL_USER_ROOT.
    Read is restricted to JAIL_USER_ROOT or standard Python interpreter libraries.
    """
    try:
        if isinstance(target, (int, bytes)):
            if isinstance(target, bytes):
                target = target.decode('utf-8', errors='ignore')
            else:
                return True
        
        target_path = Path(target).resolve()
    except Exception:
        return False

    try:
        if target_path == JAIL_USER_ROOT or JAIL_USER_ROOT in target_path.parents:
            return True
    except Exception:
        pass

    if for_write:
        return False

    try:
        for allowed_sys in SYSTEM_READ_ALLOWED:
            if target_path == allowed_sys or allowed_sys in target_path.parents:
                return True
    except Exception:
        pass

    return False

def _blocked_execution(*args, **kwargs):
    raise PermissionError("🚨 [PyHosting Jail Himoyasi] Tizim buyruqlarini (subprocess/shell/system) bajarish qat'iy taqiqlangan!")

import subprocess
subprocess.Popen = _blocked_execution
subprocess.run = _blocked_execution
subprocess.call = _blocked_execution
subprocess.check_call = _blocked_execution
subprocess.check_output = _blocked_execution

os.system = _blocked_execution
os.popen = _blocked_execution
if hasattr(os, 'spawnl'):
    for attr in ['spawnl', 'spawnle', 'spawnlp', 'spawnlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe']:
        setattr(os, attr, _blocked_execution)
if hasattr(os, 'execl'):
    for attr in ['execl', 'execle', 'execlp', 'execlpe', 'execv', 'execve', 'execvp', 'execvpe']:
        setattr(os, attr, _blocked_execution)

_orig_open = builtins.open
_orig_io_open = io.open
_orig_os_open = os.open
_orig_listdir = os.listdir
_orig_scandir = os.scandir
_orig_walk = os.walk
_orig_stat = os.stat
_orig_remove = os.remove
_orig_rename = os.rename
_orig_mkdir = os.mkdir

def _jail_open(file, *args, **kwargs):
    mode = args[0] if len(args) > 0 else kwargs.get('mode', 'r')
    is_write = any(m in mode for m in ['w', 'a', 'x', '+'])
    if not _is_path_allowed(file, for_write=is_write):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Ruxsat etilmagan fayl yo'liga murojaat: '{file}'")
    return _orig_open(file, *args, **kwargs)

def _jail_io_open(file, *args, **kwargs):
    mode = args[0] if len(args) > 0 else kwargs.get('mode', 'r')
    is_write = any(m in mode for m in ['w', 'a', 'x', '+'])
    if not _is_path_allowed(file, for_write=is_write):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Ruxsat etilmagan fayl yo'liga murojaat: '{file}'")
    return _orig_io_open(file, *args, **kwargs)

def _jail_os_open(path, flags, *args, **kwargs):
    is_write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | getattr(os, 'O_TRUNC', 0)))
    if not _is_path_allowed(path, for_write=is_write):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Ruxsat etilmagan fayl yo'liga murojaat: '{path}'")
    return _orig_os_open(path, flags, *args, **kwargs)

def _jail_listdir(path='.'):
    if not _is_path_allowed(path, for_write=False):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Kataloglarni ko'rish taqiqlangan: '{path}'")
    return _orig_listdir(path)

def _jail_scandir(path='.'):
    if not _is_path_allowed(path, for_write=False):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Kataloglarni skanerlash taqiqlangan: '{path}'")
    return _orig_scandir(path)

def _jail_walk(top, *args, **kwargs):
    if not _is_path_allowed(top, for_write=False):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Kataloglar daraxtini aylanib chiqish taqiqlangan: '{top}'")
    return _orig_walk(top, *args, **kwargs)

def _jail_stat(path, *args, **kwargs):
    if not _is_path_allowed(path, for_write=False):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Fayl ma'lumotlarini olish taqiqlangan: '{path}'")
    return _orig_stat(path, *args, **kwargs)

def _jail_remove(path, *args, **kwargs):
    if not _is_path_allowed(path, for_write=True):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Faylni o'chirish taqiqlangan: '{path}'")
    return _orig_remove(path, *args, **kwargs)

def _jail_rename(src, dst, *args, **kwargs):
    if not _is_path_allowed(src, for_write=True) or not _is_path_allowed(dst, for_write=True):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Fayl nomini o'zgartirish taqiqlangan: '{src}' -> '{dst}'")
    return _orig_rename(src, dst, *args, **kwargs)

def _jail_mkdir(path, *args, **kwargs):
    if not _is_path_allowed(path, for_write=True):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Yangi katalog yaratish taqiqlangan: '{path}'")
    return _orig_mkdir(path, *args, **kwargs)

builtins.open = _jail_open
io.open = _jail_io_open
os.open = _jail_os_open
os.listdir = _jail_listdir
os.scandir = _jail_scandir
os.walk = _jail_walk
os.stat = _jail_stat
os.remove = _jail_remove
os.unlink = _jail_remove
os.rename = _jail_rename
if hasattr(os, 'replace'):
    os.replace = _jail_rename
os.mkdir = _jail_mkdir
if hasattr(os, 'makedirs'):
    _orig_makedirs = os.makedirs
    def _jail_makedirs(name, *args, **kwargs):
        if not _is_path_allowed(name, for_write=True):
            raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Kataloglar yaratish taqiqlangan: '{name}'")
        return _orig_makedirs(name, *args, **kwargs)
    os.makedirs = _jail_makedirs

_orig_path_open = pathlib.Path.open
def _jail_path_open(self, *args, **kwargs):
    mode = args[0] if len(args) > 0 else kwargs.get('mode', 'r')
    is_write = any(m in mode for m in ['w', 'a', 'x', '+'])
    if not _is_path_allowed(self, for_write=is_write):
        raise PermissionError(f"🚨 [PyHosting Jail Himoyasi] Ruxsat etilmagan fayl yo'liga murojaat: '{self}'")
    return _orig_path_open(self, *args, **kwargs)
pathlib.Path.open = _jail_path_open

FORBIDDEN_ENV_KEYS = [
    'DATABASE_URL', 'SECRET_KEY', 'REDIS_URL', 'EMAIL_HOST_PASSWORD',
    'SUPABASE_URL', 'SUPABASE_KEY', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_CLIENT_ID',
    'TURNSTILE_SECRET_KEY', 'CLOUDFLARE_TURNSTILE_SECRET_KEY', 'DATA_ENCRYPTION_KEY',
    'PGPASSWORD', 'PGUSER', 'PGHOST', 'PGDATABASE', 'PGPORT', 'DJANGO_SETTINGS_MODULE'
]
for k in list(os.environ.keys()):
    if k in FORBIDDEN_ENV_KEYS or k.startswith(('DJANGO_', 'DATABASE_', 'POSTGRES_', 'SUPABASE_')):
        os.environ.pop(k, None)

sys.argv = USER_ARGV
sys.path.insert(0, str(JAIL_USER_ROOT))
os.chdir(str(JAIL_USER_ROOT))

try:
    from telebot import apihelper
    apihelper.SESSION_TIME_TO_LIVE = 180
except Exception:
    pass

try:
    runpy.run_path(str(TARGET_SCRIPT), run_name='__main__')
except PermissionError as e:
    print(f"\n{e}", file=sys.stderr)
    sys.exit(13)
except Exception:
    raise
