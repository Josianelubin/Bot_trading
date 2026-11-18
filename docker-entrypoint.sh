#!/bin/sh
# Demarrage Render (Docker). Le worker du bot n'applique pas les migrations (le service web s'en charge).
set -e
if [ "$KPS_ROLE" = "bot" ]; then
  exec python manage.py run_bot
fi
python manage.py migrate --no-input
python manage.py collectstatic --no-input
python manage.py create_owner || echo "create_owner ignore (variables KPS_ADMIN_* absentes ou compte deja existant)"
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60
