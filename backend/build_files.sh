#!/usr/bin/env bash
# Runs on Vercel at build time: collect the admin's static files into staticfiles/ for the static route
set -e
python3 -m pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
