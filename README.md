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

### Document applications

Citizens apply for one of the village letters, fill in the details the letter needs, and upload supporting files (ID copy, student card, proof — PDF/JPG/PNG/DOC up to 10 MB each, max 10 per request):

| Type | Letter produced | Language |
|---|---|---|
| `conduct` | Icyangombwa cy'imico n'imyifatire (Certificate of Conduct) | Kinyarwanda |
| `residence` | Icyangombwa kigaragaza ko umuturage azwi (Residence Recognition, valid 30 days) | Kinyarwanda |
| `stolen_computer` | Report of Stolen Laptop / Electronic Device | English |
| `community` | Community Engagement Referral Letter | English |
| `other` | Generic attestation from the free-text description | English |

The **village leader** (whose village matches the applicant's) reviews the details and attachments and approves or denies with a message. Approval is final: the system immediately generates the `.docx` letter in the same layout as the Isibo office documents (letterhead, body, leader signature and phone) and stores it under `backend/media/generated/`. Cell and sector leaders can view requests in their jurisdiction; the legacy `village_approved`/`cell_approved` stages remain only so older requests can still be completed.

```
pending → (village leader approves) → approved → letter downloadable (.docx)
        → (village leader denies)   → denied
```

Letter text lives in `backend/certificates/documents.py` (one builder per type). Leaders can **Regenerate** a letter after fixing details.

### Announcements

Village, cell and sector leaders have an **Announcements** page to write Umuganda communiqués, meeting notices or general announcements in English or Kinyarwanda. The changeable parts (letter date, event date, start time, venue, gathering point, partner, audience, note) are filled in a form with a live preview; the letter can be downloaded as `.docx`. Publishing an announcement makes it visible to citizens of that village.

**Service payments**: cleaning and security volunteers see the citizens of their village and mark trimester payments (RWF) for their own service — single trimester or the whole year at once. Village/cell/sector leaders see payment records within their village/cell/sector (read-only), filterable by service, trimester, year, this month, last month, or all time.

## API overview

All endpoints are under `/api/` and use token auth (`Authorization: Token <key>`).

- `POST /api/auth/register/`, `POST /api/auth/login/` — return `{token, user}`
- `POST /api/auth/logout/`, `GET /api/auth/me/`
- `GET|POST /api/requests/` — list own requests (leaders: their jurisdiction, admins: all) / submit `{cert_type, details, other_description?}`
- `GET /api/requests/<id>/` — detail incl. `details`, `attachments`, `approved_by_name`, `has_document`
- `POST /api/requests/<id>/approve/` or `/deny/` with optional `{message}` — village leader in scope, or admin
- `GET /api/requests/<id>/certificate/download/` — generated .docx (`?regenerate=1` for leaders/admins)
- `GET|POST /api/requests/<id>/attachments/` — list / multipart upload (`kind`, `files[]`)
- `GET /api/attachments/<id>/download/`, `DELETE /api/attachments/<id>/`
- `GET|POST /api/announcements/`, `GET|PATCH|DELETE /api/announcements/<id>/`
- `POST /api/announcements/preview/` — letter paragraphs for the given fields
- `GET /api/announcements/<id>/download/` — .docx
- `GET /api/users/`, `POST /api/users/<id>/eligibility/` — admin eligibility management
- `GET /api/locations/provinces|districts|sectors|cells|villages/` — cascading location data

The old server-rendered pages remain available under `/certificates/` and the Django admin under `/admin/`.
