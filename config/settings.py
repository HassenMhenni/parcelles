import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")

# local run dev mode
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# every host is allowed since we are in dev mode
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.gis",  # GeoDjango
    "rest_framework",
    "rest_framework_gis",  # GeoJSON <-> GEOSGeometry serializer field
    "parcelles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
# The ENGINE is what turns a plain PostgreSQL connection into a spatial one:
# it teaches the ORM about geometry columns and the spatial lookups.
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "parcelles"),
        "USER": os.environ.get("POSTGRES_USER", "parcelles"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "parcelles"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SCHEMA_SQL = BASE_DIR / "db" / "schema.sql"

PARCELLES_CSV = BASE_DIR / "data" / "parcelles.csv"

# ---------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "parcelles.pagination.FeatureCollectionPagination",
}

# ---------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_TZ = True
