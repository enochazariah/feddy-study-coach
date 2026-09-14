import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database configuration (safely rooted inside the backend directory)
DB_DIR = BASE_DIR / "backend" / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH = DB_DIR / "feddy_study.db"

# Environment / App settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
SESSION_JWT_SECRET = os.getenv("SESSION_JWT_SECRET", "")
ALLOW_DEMO_LOGIN = os.getenv("ALLOW_DEMO_LOGIN", "False").lower() == "true"
DEMO_LOGIN_EMAIL = os.getenv("DEMO_LOGIN_EMAIL", "feddy.demo@gmail.com").lower()
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
if not SECRET_KEY or not SESSION_JWT_SECRET:
    raise ImproperlyConfigured("SECRET_KEY and SESSION_JWT_SECRET must be configured.")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be configured when DEBUG is false.")

# --- THIS IS WHERE APPS ARE REGISTERED ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # 3rd Party
    'rest_framework',
    'corsheaders',
    
    # Local Apps
    'accounts',
    'tutoring',
]

# --- THIS IS WHERE MIDDLEWARE (LIKE CORS) LIVES ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # <-- Must be high up!
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    parsed_database = urlparse(DATABASE_URL)
    if parsed_database.scheme in {"postgres", "postgresql"}:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": unquote(parsed_database.path.lstrip("/")),
                "USER": unquote(parsed_database.username or ""),
                "PASSWORD": unquote(parsed_database.password or ""),
                "HOST": parsed_database.hostname or "",
                "PORT": str(parsed_database.port or "5432"),
                "OPTIONS": {
                    key: values[-1]
                    for key, values in parse_qs(parsed_database.query).items()
                },
            }
        }
    elif parsed_database.scheme == "sqlite":
        DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": parsed_database.path}}
    else:
        raise ImproperlyConfigured("DATABASE_URL must use postgres://, postgresql://, or sqlite://.")
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_DB_PATH,
        }
    }
else:
    raise ImproperlyConfigured("DATABASE_URL is required when DEBUG is false.")

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
MEDIA_ROOT = BASE_DIR / "backend" / "media"
MEDIA_URL = "/media/"
# Documents are streamed to storage by the upload view; do not reject large study files.
DATA_UPLOAD_MAX_MEMORY_SIZE = None
# Zero forces Django to use temporary files instead of buffering uploads in memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CORS CONFIGURATION TO ALLOW VITE FRONTEND ---
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "upload": "20/hour",
        "research": "60/hour",
        "chat": "60/hour",
        "quiz": "20/hour",
        "evaluation": "30/hour",
    },
}

QUIZ_TOKEN_MAX_AGE = int(os.getenv("QUIZ_TOKEN_MAX_AGE", "1800"))