FROM python:3.11-slim

# Xavfsizlik: Root bo'lmagan foydalanuvchi yaratish
RUN groupadd -r pyuser && useradd -r -g pyuser -d /app -s /sbin/nologin pyuser

WORKDIR /app

# Asosiy paketlar va Python unbuffered chiqish sozlamasi
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# entrypoint skripti
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Ruxsatlarni to'g'rilash
RUN chown -R pyuser:pyuser /app

# Xavfsizlik talabi: Hech qachon root huquqida ishlamaydi
USER pyuser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
