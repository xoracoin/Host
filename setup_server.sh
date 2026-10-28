#!/bin/bash

set -e

echo "=========================================================="
echo "   Py Hosting: Production Server Sozlanmoqda..."
echo "=========================================================="

echo "[1/7] Tizim paketlari yangilanmoqda..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git ufw nginx certbot python3-certbot-nginx

echo "[2/7] 4GB Swap xotira tekshirilmoqda..."
if ! grep -q '/swapfile' /etc/fstab; then
    echo "Swap yaratilmoqda..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "4GB Swap muvaffaqiyatli qo'shildi!"
else
    echo "Swap allaqachon mavjud."
fi

echo "[3/7] Docker o'rnatilmoqda..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker muvaffaqiyatli o'rnatildi!"
else
    echo "Docker allaqachon o'rnatilgan."
fi

echo "[4/7] Docker xavfsiz tarmog'i yaratilmoqda..."
sudo docker network create bot_restricted_network || true

echo "[5/7] Bot Runner obrazi yig'ilmoqda (pyhosting/bot-runner)..."
sudo docker build -f docker/bot_runner.Dockerfile -t pyhosting/bot-runner .

echo "[6/7] Asosiy xizmatlar (Postgres, Redis, Daphne) ko'tarilmoqda..."
sudo docker compose up -d --build

echo "[7/7] Django migratsiyalari qo'llanmoqda..."
sudo docker compose exec web python manage.py migrate
sudo docker compose exec web python manage.py collectstatic --noinput

echo "=========================================================="
echo "   ✓ Py Hosting muvaffaqiyatli ishga tushirildi!"
echo "   Sayt: http://$(curl -s ifconfig.me)"
echo "=========================================================="
