#!/usr/bin/env bash
# Runs on Vercel at build time: collect the admin's static files into staticfiles/ for the /static route.
# The build image's Python is "externally managed" (PEP 668), so install into a private virtualenv.
# It lives in /tmp, outside the project: anything created inside the project gets zipped into the
# serverless function and a second copy of the dependencies pushed it past Vercel's 225 MB limit.
set -e
python3 -m venv /tmp/buildenv
. /tmp/buildenv/bin/activate
pip install --quiet -r requirements.txt
python manage.py collectstatic --noinput --clear
