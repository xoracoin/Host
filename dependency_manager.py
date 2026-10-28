"""
PyHosting Dependency Whitelisting & Isolation Guard
Enforces strict third-party module whitelist (telebot, requests)
to guarantee ultra-low memory usage and zero-crash 24/7 runtime.
"""
import ast
import re
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BUILTIN_STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
    'dis', 'distutils', 'doctest', 'email', 'encodings', 'ensurepip', 'enum',
    'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'fractions',
    'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib',
    'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr',
    'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
    'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal',
    'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt', 'multiprocessing',
    'netrc', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'parser',
    'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
    'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd',
    'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline',
    'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
    'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 'smtplib',
    'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'sre_constants', 'sre_compile',
    'sre_parse', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
    'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny',
    'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading',
    'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback',
    'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing', 'unicodedata',
    'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
    'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc',
    'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo'
}

ALLOWED_THIRD_PARTY_MODULES = {
    'telebot',
    'requests',
}

FORBIDDEN_STDLIB_MODULES = {
    'subprocess', 'pty', 'ctypes', 'commands', 'posix'
}

def is_stdlib(module_name: str) -> bool:
    """Check if module is part of Python standard library and safe for user bots."""
    if module_name in FORBIDDEN_STDLIB_MODULES:
        return False
    if hasattr(sys, 'stdlib_module_names'):
        if module_name in sys.stdlib_module_names:
            return True
    return module_name in BUILTIN_STDLIB_MODULES and module_name not in FORBIDDEN_STDLIB_MODULES

def get_imported_modules(code: str, folder_path: Path = None) -> set[str]:
    """
    Extracts root external module names imported in Python code via AST.
    Filters out stdlib and local folder modules.
    """
    imported = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return imported

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split('.')[0]
                imported.add(root_pkg)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                root_pkg = node.module.split('.')[0]
                imported.add(root_pkg)

    external_modules = set()
    for mod in imported:
        if not mod or is_stdlib(mod) or mod.startswith('pyhosting'):
            continue

        if folder_path and folder_path.exists():
            local_py = folder_path / f"{mod}.py"
            local_dir = folder_path / mod
            if local_py.exists() or local_dir.is_dir():
                continue

        external_modules.add(mod)

    return external_modules

def validate_bot_dependencies(code: str, folder_path: Path = None) -> tuple[bool, list[str]]:
    """
    Performs static AST analysis on code imports.
    Returns (is_valid: bool, forbidden_modules: list[str]).
    Any module outside stdlib, user local files, and ALLOWED_THIRD_PARTY_MODULES
    will be rejected before execution.
    """
    external_modules = get_imported_modules(code, folder_path=folder_path)
    forbidden = []
    for mod in external_modules:
        if mod not in ALLOWED_THIRD_PARTY_MODULES:
            forbidden.append(mod)

    if forbidden:
        return False, sorted(list(set(forbidden)))
    return True, []

def check_telegram_bot_signature(code: str, folder_path: Path = None) -> tuple[bool, str]:
    """
    Enforces that the project contains an authorized Telegram Bot framework (telebot).
    Rejects generic shell scripts, port scanners, and non-bot executables.
    """
    import ast
    all_code_samples = [code]

    if folder_path and folder_path.exists():
        for py_file in folder_path.glob("*.py"):
            try:
                all_code_samples.append(py_file.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                pass

    has_telegram_bot = False
    for code_sample in all_code_samples:
        try:
            tree = ast.parse(code_sample)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in ['telebot', 'aiogram', 'telegram']:
                        has_telegram_bot = True
                        break
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in ['telebot', 'aiogram', 'telegram']:
                    has_telegram_bot = True
                    break
        if has_telegram_bot:
            break

    if not has_telegram_bot:
        return False, "Faqat Telegram botlarni ishga tushirish mumkin! Loyihada 'telebot' (pyTelegramBotAPI) kutubxonasi aniqlanmadi."

    return True, ""

def parse_missing_module_from_error(error_line: str) -> str | None:
    """
    Parses 'ModuleNotFoundError: No module named 'xyz'' or
    'ImportError: No module named 'xyz'' from error line.
    """
    m = re.search(r"(?:ModuleNotFoundError|ImportError):\s+No module named ['\"]([^'\"]+)['\"]", error_line)
    if m:
        full_name = m.group(1).strip()
        return full_name.split('.')[0]
    return None
