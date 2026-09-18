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

## Deploying to Vercel (two projects)

The repository holds two independently deployable folders. Create **two Vercel projects** from the same Git repository, each with a different *Root Directory*.

### 1. Backend project (Root Directory: `backend`)

`backend/vercel.json` builds Django with the Python runtime (`certify/wsgi.py` exposes `app`) and runs `build_files.sh` to collect the admin's static files. Set these environment variables in the Vercel project:

| Variable | Value |
|---|---|
| `SECRET_KEY` | long random string |
| `DEBUG` | `False` |
| `DATABASE_URL` | Postgres URL from Neon, Supabase, Railway… (Vercel has no database of its own) |
| `CORS_ALLOWED_ORIGINS` | the frontend URL, e.g. `https://certify-frontend.vercel.app` |
| `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_ENDPOINT`, `STORAGE_REGION` | an S3-compatible bucket for uploads and generated letters (Supabase Storage, Cloudflare R2, AWS S3). **Required**: Vercel's disk is wiped after every request, so without a bucket letters and attachments would vanish. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | only when using a custom API domain; `*.vercel.app` is always accepted |

After the first deploy, run the migrations and import locations against the production database from your machine:

```bash
set DATABASE_URL=postgresql://...   # PowerShell: $env:DATABASE_URL="postgresql://..."
..\venv\Scripts\python manage.py migrate
..\venv\Scripts\python manage.py createsuperuser
```

### Alternative: backend on Render

`render.yaml` at the repository root is a Render Blueprint for the backend (Root Directory `backend`, gunicorn, migrations run during build). In Render choose **New → Blueprint**, select the repository, then fill in the two variables marked `sync: false`: `DATABASE_URL` (Neon) and `CORS_ALLOWED_ORIGINS` (the frontend URL). `SECRET_KEY` is generated for you and `*.onrender.com` is already an allowed host.

Files: the free plan has no persistent disk, so set the `STORAGE_*` bucket variables as for Vercel. On a paid plan you can instead attach a Render Disk at `/var/data` and set `MEDIA_ROOT=/var/data/media` (the commented block in `render.yaml`). The free instance sleeps after 15 minutes idle; the first request afterwards takes a few seconds.

### 2. Frontend project (Root Directory: `frontend`)

`frontend/vercel.json` sets the Vite build and the SPA rewrite so deep links like `/requests/12` load. Set one environment variable:

| Variable | Value |
|---|---|
| `VITE_API_URL` | the backend project's URL, e.g. `https://certify-backend.vercel.app` (no trailing slash) |

Redeploy the frontend after changing it; Vite bakes the value in at build time. Locally leave it empty (`frontend/.env.example`) and the dev proxy keeps working.

### Notes

- Token auth is sent in the `Authorization` header, so cookies and cross-site rules are not involved between the two domains.
- Vercel functions have a 10 s execution limit on the free plan; letter generation and PDF conversion take well under a second.
- `backend/.vercelignore` keeps `media/`, `venv/` and the SQLite file out of the upload.

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

The **village leader** (whose village matches the applicant's) reviews the details and attachments and approves or denies with a message. Approval generates the `.docx` letter immediately (letterhead, body, leader signature and phone) under `backend/media/generated/`, and the citizen can open it from then on. The **cell leader** and then the **sector leader** endorse the same letter afterwards: each endorsement re-issues the file with an endorsement line under the signature and a **new verification code** whose prefix is that level's location code. The previous level is notified with the new code linked to the old one, and old codes still resolve in the verifier as "superseded".

```
pending → village leader approves → village_approved  (code 11090309nn, letter opens)
        → cell leader endorses    → cell_approved     (code 110903nn, endorsement line added)
        → sector leader endorses  → approved          (code 1109nn, final)
        → any leader denies       → denied
```

Letter text lives in `backend/certificates/documents.py` (one builder per type). Leaders can **Regenerate** a letter after fixing details.

Every letter is A4 portrait and can be downloaded as **Word (.docx)** or **PDF** (`?as=pdf`, rendered with reportlab from the stored .docx). Generated files stay under `backend/media/` (`generated/` for letters, `announcements/` for notices) and the **Documents** page lists them with the date each was created, newest first.

### Verification codes & notifications

Every approved letter receives a **verification code**: the village location code followed by a running number of at least two digits (e.g. `1109030905` = village `11090309`, letter 05). The bare code is printed in the footer of the Word and PDF file. The code is visible to village, cell and sector leaders and admins only; the API blanks it for citizens. Leaders see recent codes as cards on the Dashboard and all of them on the **Codes** page, which also has a "Verify a document" box to check any code someone presents (`GET /api/codes/<code>/`).

When a letter is issued the **cell leader(s)** of that cell receive an in-app notification with the code, and the citizen receives a "your letter is ready" notice without it. The bell in the navbar lists notifications (`/api/notifications/`).

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
- `GET /api/requests/<id>/certificate/download/` — generated .docx (`?as=pdf` for PDF, `?regenerate=1` for leaders/admins)
- `GET /api/documents/` — archive of generated letters and announcements visible to the user, with Word/PDF links
- `GET|POST /api/requests/<id>/attachments/` — list / multipart upload (`kind`, `files[]`)
- `GET /api/attachments/<id>/download/`, `DELETE /api/attachments/<id>/`
- `GET|POST /api/announcements/`, `GET|PATCH|DELETE /api/announcements/<id>/`
- `POST /api/announcements/preview/` — letter paragraphs for the given fields
- `GET /api/announcements/<id>/download/` — stored .docx (`?as=pdf` for PDF)
- `GET /api/users/`, `POST /api/users/<id>/eligibility/` — admin eligibility management
- `GET /api/locations/provinces|districts|sectors|cells|villages/` — cascading location data

The old server-rendered pages remain available under `/certificates/` and the Django admin under `/admin/`.
