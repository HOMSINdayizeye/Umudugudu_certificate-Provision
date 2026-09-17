#!/usr/bin/env bash
# Runs on Vercel at build time: collect the admin's static files into staticfiles/ for the /static route.
# The build image's Python is "externally managed" (PEP 668), so install into a private virtualenv.
set -e
python3 -m venv .buildenv
. .buildenv/bin/activate
pip install --quiet -r requirements.txt
python manage.py collectstatic --noinput --clear
