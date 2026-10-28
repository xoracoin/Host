"""
PyHosting Enterprise Email Verification & Activation Service
Handles cryptographic token generation, verification, and branded HTML email dispatch.
"""
import logging
import threading
import socket
import traceback
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

logger = logging.getLogger(__name__)
User = get_user_model()

def generate_activation_token(user) -> tuple[str, str]:
    """
    Generates a secure, cryptographically signed one-time activation token and base64 encoded user ID.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token

def verify_activation_token(uidb64: str, token: str) -> tuple[bool, object | None, str]:
    """
    Validates the base64 user ID and token.
    If valid, activates user account.
    Returns: (is_valid: bool, user: User | None, message: str)
    """
    if not uidb64 or not token:
        return False, None, "Faollashtirish parametrlari (uid/token) yetishmaydi."

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return False, None, "Foydalanuvchi topilmadi yoki havola formati xato."

    if user.is_active:
        return True, user, "Ushbu hisob allaqachon faollashtirilgan. Tizimga kirishingiz mumkin."

    if default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active', 'updated_at'])
        logger.info(f"User #{user.id} ({user.username}) successfully activated via email verification.")
        return True, user, "Hisobingiz muvaffaqiyatli faollashtirildi!"
    else:
        return False, user, "Faollashtirish havolasi eskirgan yoki yaroqsiz. Yangi havola so'rashingiz mumkin."

def diagnose_smtp_network():
    """
    Performs full network, socket, and DNS diagnostics for SMTP connectivity.
    Logs step-by-step connection status, DNS records, IPv4/IPv6 support, and port availability.
    """
    host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
    port = getattr(settings, 'EMAIL_PORT', 587)
    use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
    user = getattr(settings, 'EMAIL_HOST_USER', '')

    logger.info("==================== 📡 [EMAIL SMTP TARMOQ DIAGNOSTIKASI] ====================")
    logger.info(f"1. Sozlamalar: HOST='{host}', PORT={port}, TLS={use_tls}, FOYDALANUVCHI='{user}'")

    try:
        addr_info = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        resolved_ips = list(set(ai[4][0] for ai in addr_info))
        logger.info(f"2. DNS Lookup: '{host}' bo'yicha topilgan IP manzillar: {resolved_ips}")
    except Exception as dns_err:
        logger.error(f"2. DNS Lookup Xatosi: {dns_err}")

    ipv4_587_ok = False
    try:
        s587 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s587.settimeout(5.0)
        s587.connect((host, port))
        banner = s587.recv(1024).decode('utf-8', errors='ignore').strip()
        s587.close()
        logger.info(f"3. Port {port} (IPv4): ✅ MUVAFFAQIYATLI ULANDI! Server javobi: '{banner}'")
        ipv4_587_ok = True
    except Exception as s587_err:
        logger.error(f"3. Port {port} (IPv4): ❌ ULANIB BO'LMADI! Xatolik turi: {type(s587_err).__name__}, Tafsilot: {s587_err}")

    try:
        s465 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s465.settimeout(4.0)
        s465.connect((host, 465))
        s465.close()
        logger.info("4. Port 465 (SSL): ✅ Port ochiq, ulanish mavjud.")
    except Exception as s465_err:
        logger.error(f"4. Port 465 (SSL): ❌ Ulanib bo'lmadi ({type(s465_err).__name__}: {s465_err})")

    try:
        s_http = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_http.settimeout(3.0)
        s_http.connect(('google.com', 443))
        s_http.close()
        logger.info("5. Tashqi Internet (Port 443 HTTPS): ✅ ISHLAMOQDA (Internetga chiqish bor).")
    except Exception as h_err:
        logger.error(f"5. Tashqi Internet (Port 443 HTTPS): ❌ Internet yo'q ({h_err})")

    if not ipv4_587_ok:
        logger.warning(
            "6. 🔴 ANIQ DIAGNOZ: Sayt serverida internet bor (443 ochiq), lekin hosting tizimi (Render/Docker) "
            "tashqi SMTP portlariga (587 va 465) chiquvchi TCP ulanishlarni firewall orqali qat'iy bloklamoqda "
            "([Errno 101] Network is unreachable)."
        )
    else:
        logger.info(
            "6. 🟢 ANIQ DIAGNOZ: Port 587 ga tarmoq orqali ulanish muvaffaqiyatli! "
            "Agar xat ketmasa, Gmail App Password, login yoki Google xavfsizlik sozlamasini tekshirish kerak."
        )

    logger.info("=============================================================================")

def _send_email_async(subject, recipient_email, html_content, text_content):
    """
    Sends email in a separate thread so the user registration response is returned immediately.
    Logs rich diagnostics on connection or authentication failure.
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Py Hosting <noreply@pyhosting.uz>')
    host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

    if not host_user or not host_password or 'change-to' in str(host_password):
        logger.warning(
            f"[Gmail SMTP Ogohlantirish] EMAIL_HOST_USER yoki EMAIL_HOST_PASSWORD sozlamalari to'ldirilmagan. "
            f"Xat '{recipient_email}' ga yuborilmadi, lekin havola konsolga chiqarildi."
        )
        return

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"✅ Activation email successfully sent to {recipient_email}")
    except Exception as e:
        logger.error(f"❌ Error sending activation email to {recipient_email}: {type(e).__name__}: {e}")
        logger.error(f"Stack Trace:\n{traceback.format_exc()}")
        try:
            diagnose_smtp_network()
        except Exception as diag_e:
            logger.error(f"Diagnostika paytida xatolik yuz berdi: {diag_e}")

def send_activation_email(user, request=None) -> tuple[bool, str]:
    """
    Generates activation link, renders HTML email template, and triggers asynchronous dispatch.
    Returns: (success: bool, activation_url: str)
    """
    uid, token = generate_activation_token(user)

    if request:
        try:
            base_url = request.build_absolute_uri('/').rstrip('/')
        except Exception:
            protocol = 'https' if (request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https') else 'http'
            host = request.get_host()
            base_url = f"{protocol}://{host}"
    else:
        base_url = "https://pyhosting.onrender.com"

    activation_url = f"{base_url}/auth/activate/?uid={uid}&token={token}"

    logger.info(f"[🔑 Faollashtirish Havolasi] Foydalanuvchi: {user.username} ({user.email}) -> {activation_url}")

    subject = "🚀 PyHosting — Akkauntingizni faollashtiring"
    context = {
        'user': user,
        'activation_url': activation_url,
        'site_name': 'Py Hosting',
        'support_email': 'support@pyhosting.uz'
    }

    try:
        html_content = render_to_string('emails/activation_email.html', context)
    except Exception as e:
        logger.error(f"Error rendering activation email template: {e}")
        html_content = f"<p>Salom {user.username}, hisobingizni faollashtirish uchun ushbu havolani bosing:</p><p><a href='{activation_url}'>{activation_url}</a></p>"

    text_content = strip_tags(html_content)

    email_thread = threading.Thread(
        target=_send_email_async,
        args=(subject, user.email, html_content, text_content),
        daemon=True
    )
    email_thread.start()

    return True, activation_url

def generate_email_change_token(user, new_email: str) -> str:
    """
    Generates a cryptographically signed, timestamped token containing user ID and new email.
    """
    signer = TimestampSigner(salt='pyhosting.email_change')
    return signer.sign_object({'uid': user.pk, 'new_email': new_email.strip().lower()})

def verify_email_change_token(token: str) -> tuple[bool, object | None, str | None, str]:
    """
    Validates email change token and updates user.email to new_email.
    Returns: (success: bool, user: User | None, new_email: str | None, message: str)
    """
    if not token:
        return False, None, None, "Tasdiqlash tokeni taqdim etilmadi."

    signer = TimestampSigner(salt='pyhosting.email_change')
    try:
        data = signer.unsign_object(token, max_age=86400)
    except SignatureExpired:
        return False, None, None, "Tasdiqlash havolasining muddati o'tgan (24 soat). Iltimos, sozlamalardan qayta so'rang."
    except BadSignature:
        return False, None, None, "Tasdiqlash havolasi noto'g'ri yoki buzilgan."

    uid = data.get('uid')
    new_email = (data.get('new_email') or '').strip().lower()

    if not uid or not new_email:
        return False, None, None, "Token tarkibida zarur ma'lumotlar topilmadi."

    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        return False, None, None, "Foydalanuvchi hisobi topilmadi."

    if user.email.lower() == new_email:
        return True, user, new_email, "Ushbu elektron pochta allaqachon hisobingizga biriktirilgan."

    if User.objects.exclude(pk=user.pk).filter(email__iexact=new_email).exists():
        return False, user, new_email, "Ushbu elektron pochta allaqachon boshqa hisob tomonidan band qilingan."

    old_email = user.email
    user.email = new_email
    user.save(update_fields=['email', 'updated_at'])
    logger.info(f"User #{user.id} ({user.username}) successfully changed email from '{old_email}' to '{new_email}'.")

    return True, user, new_email, f"Elektron pochtangiz muvaffaqiyatli '{new_email}' ga yangilandi!"

def send_email_change_verification(user, new_email: str, request=None) -> tuple[bool, str]:
    """
    Generates email change token, renders HTML email template, and sends to the NEW email address.
    """
    token = generate_email_change_token(user, new_email)

    if request:
        try:
            base_url = request.build_absolute_uri('/').rstrip('/')
        except Exception:
            protocol = 'https' if (request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https') else 'http'
            host = request.get_host()
            base_url = f"{protocol}://{host}"
    else:
        base_url = "https://pyhosting.onrender.com"

    confirm_url = f"{base_url}/auth/confirm-email/?token={token}"

    logger.info(f"[🔑 Pochta Yangilash Havolasi] Foydalanuvchi: {user.username} -> Yangi pochta: {new_email} -> {confirm_url}")

    subject = "📧 PyHosting — Yangi pochtani tasdiqlang"
    context = {
        'user': user,
        'new_email': new_email,
        'confirm_url': confirm_url,
        'site_name': 'Py Hosting',
        'support_email': 'support@pyhosting.uz'
    }

    try:
        html_content = render_to_string('emails/email_change_email.html', context)
    except Exception as e:
        logger.error(f"Error rendering email_change_email template: {e}")
        html_content = f"<p>Salom {user.username}, yangi pochtangizni tasdiqlash uchun ushbu havolani bosing:</p><p><a href='{confirm_url}'>{confirm_url}</a></p>"

    text_content = strip_tags(html_content)

    email_thread = threading.Thread(
        target=_send_email_async,
        args=(subject, new_email, html_content, text_content),
        daemon=True
    )
    email_thread.start()

    return True, confirm_url
