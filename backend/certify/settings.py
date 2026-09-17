import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from decouple import config

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=''):
    return [v.strip() for v in os.getenv(name, default).split(',') if v.strip()]


SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
# Local defaults plus every Vercel deployment URL; add your custom domain in ALLOWED_HOSTS
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1') + ['.vercel.app']
# True on Vercel (VERCEL=1 is set automatically) — no writable disk, HTTPS behind a proxy
ON_VERCEL = os.getenv('VERCEL') == '1'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'certificates',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Serves the admin's CSS/JS from staticfiles/ without a separate web server
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'certify.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # or include custom paths if needed
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'certify.wsgi.application'

# Production: a single DATABASE_URL (Neon, Supabase, Railway…). Local: the DB_* values in .env.
if os.getenv('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=not DEBUG),
    }
else:
    # Defaults let `collectstatic` run at build time even when no database variables are set
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='certify'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
AUTH_USER_MODEL = 'certificates.CustomUser'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kigali'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Uploaded attachments and generated letters; served only through authenticated API endpoints.
# Locally they live in backend/media/. On Vercel the disk is not persistent, so set the STORAGE_*
# variables to any S3-compatible bucket (Supabase Storage, Cloudflare R2, AWS S3, MinIO…).
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MAX_ATTACHMENT_MB = 10

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
if os.getenv('STORAGE_BUCKET'):
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': os.getenv('STORAGE_BUCKET'),
            'access_key': os.getenv('STORAGE_ACCESS_KEY'),
            'secret_key': os.getenv('STORAGE_SECRET_KEY'),
            'endpoint_url': os.getenv('STORAGE_ENDPOINT') or None,
            'region_name': os.getenv('STORAGE_REGION') or 'auto',
            'default_acl': 'private',
            'file_overwrite': False,
            'querystring_auth': True,
        },
    }

# Behind Vercel's proxy the request is HTTPS even though Django sees plain HTTP
if ON_VERCEL or not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app'] + env_list('CSRF_TRUSTED_ORIGINS')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/certificates/login/'

LOGIN_REDIRECT_URL = '/certificates/dashboard/'

LOGOUT_REDIRECT_URL = '/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Frontend origins allowed to call the API: local Vite servers plus whatever CORS_ALLOWED_ORIGINS lists
# (e.g. https://certify-frontend.vercel.app). Preview deployments of the frontend match the regex.
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
] + env_list('CORS_ALLOWED_ORIGINS')
CORS_ALLOWED_ORIGIN_REGEXES = [r'^https://[\w-]+\.vercel\.app$']


