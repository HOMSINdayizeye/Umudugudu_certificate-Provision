# Certify — Kigali City Certificate Requests

Full-stack app for requesting and managing certificates (conduct, residence, community engagement, stolen computer).

## Structure

```
Certify/
├── backend/     Django 4.2 + Django REST Framework API (PostgreSQL)
│   ├── certify/           Project settings and URLs
│   ├── certificates/      App: models, API (api.py, serializers.py, api_urls.py), legacy template views
│   ├── manage.py
│   ├── requirements.txt
│   └── .env               DB credentials and secret key (not committed)
├── frontend/    React 18 + Vite single-page app
│   └── src/pages/         Login, Register, Dashboard, SubmitRequest, RequestDetail, ManageEligibility
└── venv/        Python virtual environment
```

## Running the app

Requires PostgreSQL running locally with the database from `backend/.env`.

**Backend** (http://localhost:8000):

```bash
cd backend
../venv/Scripts/python manage.py runserver 8000
```

**Frontend** (http://localhost:5173):

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to the Django backend, so both must be running.

## API overview

All endpoints are under `/api/` and use token auth (`Authorization: Token <key>`).

- `POST /api/auth/register/`, `POST /api/auth/login/` — return `{token, user}`
- `POST /api/auth/logout/`, `GET /api/auth/me/`
- `GET|POST /api/requests/` — list own requests (admins see all) / submit a request
- `GET /api/requests/<id>/` — detail
- `POST /api/requests/<id>/approve/` or `/deny/` — admin only
- `GET /api/requests/<id>/certificate/download/` — .docx for approved requests
- `GET /api/users/`, `POST /api/users/<id>/eligibility/` — admin eligibility management
- `GET /api/locations/provinces|districts|sectors|cells|villages/` — cascading location data

The old server-rendered pages remain available under `/certificates/` and the Django admin under `/admin/`.
