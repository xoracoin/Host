#!/bin/bash
echo "[Py Hosting] Bot Runner Docker obrazi yig'ilmoqda (pyhosting/bot-runner)..."
docker build -f bot_runner.Dockerfile -t pyhosting/bot-runner .
echo "[Py Hosting] Obraz muvaffaqiyatli tayyorlandi!"
