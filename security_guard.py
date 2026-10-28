"""
PyHosting Enterprise Python Code Security Guard
Deep AST (Abstract Syntax Tree) & Heuristic Static Code Analysis
Prevents reverse shells, web-shells, host memory tampering,
fork bombs, unauthorized system command execution, and host file access.
"""
import ast
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FORBIDDEN_CALL_PATTERNS = {
    ('pty', 'spawn'): "Tizim terminalini qamrab olish (PTY Spawn / Reverse Shell)",
    ('pty', 'fork'): "Interaktiv PTY Fork orqali tizimni boshqarish",
    ('os', 'dup2'): "Standart kiritish/chiqarish oqimlarini qayta yo'naltirish (Reverse Shell belgisi)",
    ('os', 'dup'): "Oqimlarni soxtalashtirish (I/O Redirection)",
    ('os', 'setuid'): "Tizim imtiyozlarini o'zgartirishga urinish (Privilege Escalation)",
    ('os', 'seteuid'): "Tizim imtiyozlarini o'zgartirishga urinish (Privilege Escalation)",
    ('os', 'setgid'): "Tizim guruh imtiyozlarini o'zgartirishga urinish",
    ('os', 'chroot'): "Tizim ildiz katalogini o'zgartirishga urinish",

    ('subprocess', 'Popen'): "Tizim buyruqlarini subprocess orqali bajarish taqiqlangan",
    ('subprocess', 'run'): "Tizim buyruqlarini subprocess orqali bajarish taqiqlangan",
    ('subprocess', 'call'): "Tizim buyruqlarini subprocess orqali bajarish taqiqlangan",
    ('subprocess', 'check_call'): "Tizim buyruqlarini subprocess orqali bajarish taqiqlangan",
    ('subprocess', 'check_output'): "Tizim buyruqlarini subprocess orqali bajarish taqiqlangan",
    ('os', 'system'): "Tizim buyruqlarini os.system orqali chaqirish taqiqlangan",
    ('os', 'popen'): "Tizim buyruqlarini os.popen orqali chaqirish taqiqlangan",

    ('ctypes', 'CDLL'): "Tizim darajasidagi ikkilik (C library) kutubxonasini chaqirish taqiqlangan",
    ('ctypes', 'windll'): "Windows tizim kutubxonalarini to'g'ridan-to'g'ri chaqirish taqiqlangan",
    ('ctypes', 'pythonapi'): "Python yadrosi xotirasini manipulyatsiya qilish taqiqlangan",
}

DANGEROUS_PAYLOAD_PATTERNS = [
    (re.compile(r'/bin/(?:ba)?sh\s+-i', re.IGNORECASE), "Interaktiv Linux Shell chaqiruvi (/bin/sh -i)"),
    (re.compile(r'nc(?:\.traditional)?\s+-[e|c]', re.IGNORECASE), "Netcat teskari ulanishi (Netcat Reverse Shell)"),
    (re.compile(r'(?:bash|sh)\s+-c\s+["\'].*?(?:/dev/tcp/|telnet|nc)', re.IGNORECASE), "Bash /dev/tcp teskari ulanish ssenariysi"),
    (re.compile(r'mkfifo\s+/tmp/', re.IGNORECASE), "Nomlangan kanal (Named Pipe) orqali Reverse Shell ochish"),
    (re.compile(r'/etc/(?:shadow|sudoers|master\.passwd)', re.IGNORECASE), "Tizim maxfiy parollar fayliga murojaat qilish"),
    (re.compile(r'/proc/\d+/(?:environ|cmdline)', re.IGNORECASE), "Tizim jarayonlari xotirasiga ruxsatsiz murojaat"),
    (re.compile(r'rm\s+-rf\s+/(?:\s|$)', re.IGNORECASE), "Tizimning butun ildiz fayllarini o'chirish buyrug'i"),
    (re.compile(r'(?:\.\./|\.\.\\)', re.IGNORECASE), "Katalogdan tashqariga chiqishga urinish (Path Traversal `../`)"),
    (re.compile(r'import\s+pyhosting', re.IGNORECASE), "Hosting asosiy yadrosiga ruxsatsiz murojaat qilish"),
    (re.compile(r'from\s+pyhosting', re.IGNORECASE), "Hosting ichki modullariga ruxsatsiz murojaat qilish"),
    (re.compile(r'import\s+subprocess', re.IGNORECASE), "Subprocess moduli orqali tizimni boshqarish taqiqlangan"),
    (re.compile(r'from\s+subprocess', re.IGNORECASE), "Subprocess moduli orqali tizimni boshqarish taqiqlangan"),
    (re.compile(r'import\s+pty', re.IGNORECASE), "PTY terminal moduli taqiqlangan"),
    (re.compile(r'from\s+pty', re.IGNORECASE), "PTY terminal moduli taqiqlangan"),
]

FORBIDDEN_MODULE_IMPORTS = {'subprocess', 'pty', 'ctypes', 'commands', 'pyhosting'}

class CodeSecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.has_socket_connect = False
        self.has_stream_redirection = False
        self.in_loop = False
        self.has_os_fork = False

    def visit_Import(self, node):
        for alias in node.names:
            root_mod = alias.name.split('.')[0]
            if root_mod in FORBIDDEN_MODULE_IMPORTS or alias.name.startswith('pyhosting'):
                self.violations.append(f"Xavfsizlik sababli '{alias.name}' modulidan foydalanish taqiqlangan")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            root_mod = node.module.split('.')[0]
            if root_mod in FORBIDDEN_MODULE_IMPORTS or node.module.startswith('pyhosting'):
                self.violations.append(f"Xavfsizlik sababli '{node.module}' modulidan import qilish taqiqlangan")
        self.generic_visit(node)

    def visit_While(self, node):
        prev = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = prev

    def visit_For(self, node):
        prev = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = prev

    def visit_Call(self, node):
        func = node.func

        if isinstance(func, ast.Attribute):
            val_id = getattr(func.value, 'id', None)
            attr_name = func.attr

            if val_id and (val_id, attr_name) in FORBIDDEN_CALL_PATTERNS:
                self.violations.append(FORBIDDEN_CALL_PATTERNS[(val_id, attr_name)])

            if val_id == 'socket' and attr_name == 'connect':
                self.has_socket_connect = True
            elif attr_name == 'connect' and isinstance(func.value, ast.Call):
                self.has_socket_connect = True

            if val_id == 'os' and attr_name in ['dup2', 'dup']:
                self.has_stream_redirection = True

            if val_id == 'os' and attr_name == 'fork':
                if self.in_loop:
                    self.violations.append("Cheksiz sikl ichida 'os.fork' chaqiruvi (Fork Bomb hujumi) aniqlandi")

            if val_id == 'shutil' and attr_name == 'rmtree':
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and str(arg0.value).strip() in ['/', 'C:\\', 'C:/', '\\']:
                        self.violations.append("Tizim ildiz katalogini o'chirishga urinish aniqlandi")

            if val_id in ['subprocess', 'os'] and attr_name in ['Popen', 'call', 'run', 'system', 'popen']:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        s = arg.value.lower()
                        if any(bad in s for bad in ['/bin/sh -i', '/bin/bash -i', 'bash -i', 'nc -e', 'nc.traditional -e', 'rm -rf /']):
                            self.violations.append(f"Subprocess ichida xavfli buyruq aniqlandi: '{arg.value[:50]}'")

        self.generic_visit(node)

class CodeSecurityGuard:
    """
    Validates Python files against security policies before execution.
    """

    @classmethod
    def scan_file(cls, file_path: Path, user=None) -> tuple[bool, str]:
        """
        Scans a python file on disk.
        Returns: (is_safe: bool, reason: str)
        """
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return False, f"Faylni o'qib bo'lmadi: {e}"

        return cls.scan_content(content, filename=file_path.name, user=user)

    @classmethod
    def scan_content(cls, code: str, filename: str = "kod.py", user=None) -> tuple[bool, str]:
        if not code or not code.strip():
            return True, ""

        for pattern, desc in DANGEROUS_PAYLOAD_PATTERNS:
            if pattern.search(code):
                cls.log_violation(user, filename, desc)
                return False, f"Xavfsizlik tizimi: {desc}"

        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError:
            return True, ""

        visitor = CodeSecurityVisitor()
        try:
            visitor.visit(tree)
        except Exception as e:
            logger.warning(f"AST inspection warning: {e}")

        if visitor.has_socket_connect and visitor.has_stream_redirection:
            violation_msg = "Klassik teskari ulanish (Reverse Shell) shabloni aniqlandi (socket + os.dup2)"
            cls.log_violation(user, filename, violation_msg)
            return False, f"Xavfsizlik tizimi: {violation_msg}"

        if visitor.violations:
            violation_msg = visitor.violations[0]
            cls.log_violation(user, filename, violation_msg)
            return False, f"Xavfsizlik tizimi: {violation_msg}"

        return True, ""

    @classmethod
    def log_violation(cls, user, filename: str, reason: str):
        try:
            from apps.adminpanel.models import AdminAuditLog
            AdminAuditLog.objects.create(
                action='SECURITY_ALERT',
                target_user=user if (user and getattr(user, 'is_authenticated', False)) else None,
                details=f"🚨 [Kod Skaneri] '{filename}' faylida xavfli kod bloklandi: {reason}",
                ip_address='127.0.0.1'
            )
        except Exception:
            pass
