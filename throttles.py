"""
PyHosting Anti-Brute-Force & Rate Limiting Throttles
Protects authentication endpoints from automated credential stuffing,
dictionary attacks, and brute-force botnets.
"""

from rest_framework.throttling import SimpleRateThrottle
from django.core.cache import cache

class AuthRateThrottle(SimpleRateThrottle):
    """
    Limits authentication attempts (Login, Register, Password Change)
    to prevent brute-force attacks. Defaults to 5 requests per minute per IP.
    """
    scope = 'auth'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class BruteForceProtector:
    """
    Tracks consecutive failed login attempts by IP and username.
    Locks out after 5 consecutive failures for 15 minutes (900 seconds).
    """
    MAX_ATTEMPTS = 5
    LOCKOUT_SECONDS = 900
    ATTEMPT_WINDOW_SECONDS = 300

    @classmethod
    def _get_key(cls, ip: str, username: str) -> str:
        clean_user = (username or '').strip().lower()
        return f"bf_attempts:{ip}:{clean_user}"

    @classmethod
    def _get_lockout_key(cls, ip: str, username: str) -> str:
        clean_user = (username or '').strip().lower()
        return f"bf_lockout:{ip}:{clean_user}"

    @classmethod
    def is_locked_out(cls, ip: str, username: str) -> bool:
        lockout_key = cls._get_lockout_key(ip, username)
        return bool(cache.get(lockout_key))

    @classmethod
    def record_failure(cls, ip: str, username: str) -> int:
        lockout_key = cls._get_lockout_key(ip, username)
        key = cls._get_key(ip, username)
        
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, cls.ATTEMPT_WINDOW_SECONDS)

        if attempts >= cls.MAX_ATTEMPTS:
            cache.set(lockout_key, True, cls.LOCKOUT_SECONDS)
            cache.delete(key)
        return attempts

    @classmethod
    def record_success(cls, ip: str, username: str):
        key = cls._get_key(ip, username)
        lockout_key = cls._get_lockout_key(ip, username)
        cache.delete(key)
        cache.delete(lockout_key)
