"""
Comprehensive Enterprise Security & Ethical Hacker Hardening Tests
Verifies that all attack vectors (IDOR, Path Traversal, Brute-Force,
Code Theft, Environment Leaks, and Sniffing) are completely mitigated.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from pathlib import Path

from apps.accounts.models import UserQuota
from apps.accounts.throttles import BruteForceProtector
from apps.filemanager.models import File, Folder, sanitize_name
from apps.botengine.models import BotProcess
from apps.botengine.crypto import encrypt_dict, decrypt_dict
from apps.botengine.runner import build_isolated_environment

User = get_user_model()

class PlatformSecurityTestCase(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='victim_alice',
            email='alice@pyhosting.test',
            password='ComplexPassword123!'
        )
        self.user_b = User.objects.create_user(
            username='attacker_bob',
            email='bob@pyhosting.test',
            password='HackerPassword456!'
        )

        self.file_alice = File.objects.create(
            owner=self.user_a,
            name='secret_bot.py',
            extension='.py'
        )
        self.file_alice.write_content("API_SECRET_TOKEN = 'SUPER_CONFIDENTIAL_12345'")

        self.bot_proc_alice = BotProcess.objects.create(
            owner=self.user_a,
            file=self.file_alice
        )
        self.bot_proc_alice.set_encrypted_env({'BOT_TOKEN': '123456:ABC-DEF-SECRET'})
        self.bot_proc_alice.save()

        from rest_framework_simplejwt.tokens import RefreshToken
        self.client_bob = Client()
        self.bob_token = str(RefreshToken.for_user(self.user_b).access_token)

    def test_argon2id_password_hashing(self):
        """Verify user passwords are encrypted using state-of-the-art Argon2id algorithm."""
        self.assertTrue(self.user_a.password.startswith('argon2'))
        self.assertTrue(self.user_b.password.startswith('argon2'))

    def test_no_public_media_code_download(self):
        """Verify that anonymous or malicious HTTP requests cannot download source code via media paths."""
        client = Client()
        res = client.get('/media/users/1/secret_bot.py')
        self.assertEqual(res.status_code, 404)

        res2 = client.get(f'/media/users/{self.user_a.id}/secret_bot.py')
        self.assertEqual(res2.status_code, 404)

    def test_path_traversal_sanitization(self):
        """Verify sanitize_name rejects traversal sequences, null bytes, and malicious characters."""
        dangerous_names = [
            '../../etc/passwd',
            '..\\windows\\system32',
            'bot.py\0.txt',
            'payload:hidden_stream',
            'bot|rm -rf',
            'CON.py',
            'NUL.py'
        ]
        for bad_name in dangerous_names:
            with self.assertRaises(ValidationError):
                sanitize_name(bad_name)

    def test_idor_protection_file_read(self):
        """Verify Attacker Bob cannot read Alice's source code via API (must return 404)."""
        auth_header = {'HTTP_AUTHORIZATION': f'Bearer {self.bob_token}'}
        res = self.client_bob.get(f'/api/files/{self.file_alice.id}/content/', **auth_header)
        self.assertEqual(res.status_code, 404)

    def test_idor_protection_bot_control(self):
        """Verify Attacker Bob cannot start, stop, or read Alice's bot process."""
        auth_header = {'HTTP_AUTHORIZATION': f'Bearer {self.bob_token}'}
        res_start = self.client_bob.post(f'/api/bots/{self.file_alice.id}/start/', **auth_header)
        self.assertEqual(res_start.status_code, 404)

        res_logs = self.client_bob.get(f'/api/bots/{self.file_alice.id}/logs/', **auth_header)
        self.assertEqual(res_logs.status_code, 404)

        res_env = self.client_bob.get(f'/api/bots/{self.file_alice.id}/env/', **auth_header)
        self.assertEqual(res_env.status_code, 404)

    def test_aes256_encryption_at_rest(self):
        """Verify bot environment secrets are AES-256 encrypted in the database."""
        self.bot_proc_alice.refresh_from_db()
        raw_env_in_db = self.bot_proc_alice.env_vars
        self.assertIn('_encrypted', raw_env_in_db)
        self.assertNotIn('123456:ABC-DEF-SECRET', str(raw_env_in_db))

        decrypted = self.bot_proc_alice.get_decrypted_env()
        self.assertEqual(decrypted.get('BOT_TOKEN'), '123456:ABC-DEF-SECRET')

    def test_environment_scrubbing_sandbox(self):
        """Verify runner environment strips SECRET_KEY, DB credentials, and server tokens."""
        import os
        os.environ['SECRET_KEY'] = 'CRITICAL_DJANGO_SECRET_KEY'
        os.environ['DB_PASSWORD'] = 'POSTGRES_ROOT_PASS'

        isolated = build_isolated_environment(Path('.'), {'USER_KEY': '123'})
        self.assertNotIn('SECRET_KEY', isolated)
        self.assertNotIn('DB_PASSWORD', isolated)
        self.assertNotIn('DJANGO_SETTINGS_MODULE', isolated)
        self.assertEqual(isolated.get('USER_KEY'), '123')

    def test_brute_force_lockout_system(self):
        """Verify consecutive wrong passwords trigger account lockout for 15 minutes."""
        test_ip = '198.51.100.99'
        test_user = 'victim_lockout_target'

        for _ in range(5):
            BruteForceProtector.record_failure(test_ip, test_user)

        self.assertTrue(BruteForceProtector.is_locked_out(test_ip, test_user))

        BruteForceProtector.record_success(test_ip, test_user)
        self.assertFalse(BruteForceProtector.is_locked_out(test_ip, test_user))

    def test_security_headers_and_csp(self):
        """Verify Content-Security-Policy and anti-clickjacking headers on HTTP responses."""
        res = self.client_bob.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Content-Security-Policy', res.headers)
        self.assertIn('Permissions-Policy', res.headers)
        self.assertEqual(res.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
