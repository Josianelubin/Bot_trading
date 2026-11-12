#!/usr/bin/env bash
set -o errexit
pip install -r requirements-prod.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py create_owner || echo "create_owner ignore (variables KPS_ADMIN_* absentes ou compte existant)"
