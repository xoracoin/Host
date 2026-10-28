#!/usr/bin/env bash
set -o errexit

echo "--- Installing dependencies ---"
pip install -r requirements.txt

echo "--- Collecting static files ---"
python manage.py collectstatic --no-input --clear || python manage.py collectstatic --no-input

echo "--- Running database migrations ---"
python manage.py migrate
