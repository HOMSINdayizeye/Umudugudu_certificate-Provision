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

## User roles & approval workflow

Public registration always creates a **citizen** (with their village and optional isibo). The **system admin** creates all other users from the "Add User" page: isibo leader, village leader, cell leader, sector leader, security volunteer, cleaning service volunteer, or another system admin.

Certificate requests move through a three-stage approval chain, each leader only seeing requests inside their own jurisdiction (matched by hierarchical location codes):

```
pending → (village leader approves) → village_approved
        → (cell leader approves)    → cell_approved
        → (sector leader approves)  → approved  → certificate downloadable
```

Any leader in the chain can deny; the system admin can approve/deny directly.

**Service payments**: cleaning and security volunteers see the citizens of their village and mark trimester payments (RWF) for their own service — single trimester or the whole year at once. Village/cell/sector leaders see payment records within their village/cell/sector (read-only), filterable by service, trimester, year, this month, last month, or all time.

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
