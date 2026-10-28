#!/bin/sh
set -e

echo "[PyHosting] Bot konteyneri ishga tushirilmoqda..."

if [ -f "requirements.txt" ]; then
    echo "[PyHosting] requirements.txt kutubxonalari o'rnatilmoqda (timeout 60s)..."
    pip install --timeout 60 -r requirements.txt || echo "[PyHosting Ogohlantirish] Ayrim kutubxonalarni o'rnatishda xatolik yuz berdi"
fi

TARGET_FILE="${BOT_ENTRY_FILE:-bot.py}"

if [ ! -f "$TARGET_FILE" ]; then
    echo "[PyHosting Xato] Ishga tushirish uchun fayl topilmadi: $TARGET_FILE"
    exit 1
fi

echo "[PyHosting] '$TARGET_FILE' ishga tushmoqda..."
exec python -u "$TARGET_FILE"
