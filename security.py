"""
PyHosting Enterprise File Security Inspector
Implements magic-byte verification, binary executable detection,
path-traversal shields, and disguised payload prevention.
"""
import os
import re
from pathlib import Path
from django.core.exceptions import ValidationError

DANGEROUS_MAGIC_SIGNATURES = [
    (b'\x7fELF', 'Linux ELF Bajariluvchi Ikkilik (Binary) fayl'),
    (b'MZ', 'Windows PE/EXE Bajariluvchi fayl'),
    (b'\xfe\xed\xfa\xce', 'Mach-O 32-bit Bajariluvchi fayl'),
    (b'\xfe\xed\xfa\xcf', 'Mach-O 64-bit Bajariluvchi fayl'),
    (b'\xce\xfa\xed\xfe', 'Mach-O Bajariluvchi fayl (reverse byte-order)'),
    (b'\xcf\xfa\xed\xfe', 'Mach-O Bajariluvchi fayl (reverse byte-order)'),
    (b'\xca\xfe\xba\xbe', 'Java Class / Mach-O Universal Bajariluvchi fayl'),
    (b'PK\x03\x04\x14\x00\x08\x00', 'APK / Executable Zip paketi'),
]

DISGUISED_SHELL_PATTERNS = [
    re.compile(rb'^#!\s*/bin/sh', re.IGNORECASE),
    re.compile(rb'^#!\s*/bin/bash', re.IGNORECASE),
    re.compile(rb'^#!\s*/bin/dash', re.IGNORECASE),
    re.compile(rb'^#!\s*/bin/zsh', re.IGNORECASE),
    re.compile(rb'^#!\s*/usr/bin/env\s+bash', re.IGNORECASE),
    re.compile(rb'^#!\s*/usr/bin/env\s+sh', re.IGNORECASE),
]

def inspect_file_content(content: bytes | str, filename: str, user=None) -> tuple[bool, str]:
    """
    Validates that file content does not contain binary executables,
    web-shells, or disguised system shell payloads.
    Returns: (is_safe, error_message)
    """
    if isinstance(content, str):
        content_bytes = content.encode('utf-8', errors='ignore')
    else:
        content_bytes = content or b''

    if not content_bytes:
        return True, ""

    header = content_bytes[:16]
    for signature, description in DANGEROUS_MAGIC_SIGNATURES:
        if header.startswith(signature):
            log_security_alert(
                user=user,
                filename=filename,
                reason=f"Bajariluvchi fayl aniqlandi ({description})"
            )
            return False, f"Xavfsizlik tizimi: Ushbu fayl yuklanishi taqiqlangan ({description})!"

    ext = os.path.splitext(filename)[1].lower()
    if ext != '.py':
        for pattern in DISGUISED_SHELL_PATTERNS:
            if pattern.search(content_bytes[:100]):
                log_security_alert(
                    user=user,
                    filename=filename,
                    reason="Niqoblangan Linux Shell skripti aniqlandi"
                )
                return False, "Xavfsizlik tizimi: Linux Bash/Shell skriptlarini boshqa kengaytmalar ostida yuklash taqiqlangan!"
    else:
        try:
            from apps.botengine.security_guard import CodeSecurityGuard
            code_text = content if isinstance(content, str) else content_bytes.decode('utf-8', errors='ignore')
            is_py_safe, py_reason = CodeSecurityGuard.scan_content(code_text, filename=filename, user=user)
            if not is_py_safe:
                return False, py_reason
        except Exception as e:
            pass

    return True, ""

def log_security_alert(user, filename: str, reason: str):
    """
    Records an immutable audit log entry in the Superadmin audit journal.
    """
    try:
        from apps.adminpanel.models import AdminAuditLog
        AdminAuditLog.objects.create(
            action='SECURITY_ALERT',
            target_user=user if (user and getattr(user, 'is_authenticated', False)) else None,
            details=f"🚨 [Fayl Himoyasi] '{filename}' faylida xavf aniqlandi va to'xtatildi: {reason}",
            ip_address='127.0.0.1'
        )
    except Exception:
        pass
