"""
Django settings for Lite Hosting Panel.

Loads SECRET_KEY and FERNET_KEY from /usr/local/lkypanel/.env (chmod 600).
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
INSTALL_DIR = Path('/usr/local/lkypanel')

# Fallback for local development or non-standard install
if not INSTALL_DIR.exists():
    INSTALL_DIR = BASE_DIR.parent

# Ensure essential directories exist
(INSTALL_DIR / 'db').mkdir(parents=True, exist_ok=True)
(INSTALL_DIR / 'ssl').mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Environment — load from .env file (simple key=value, no shell expansion)
# ---------------------------------------------------------------------------
_env_path = INSTALL_DIR / '.env'
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())

SECRET_KEY = os.environ['SECRET_KEY']
FERNET_KEY = os.environ['FERNET_KEY']

DEBUG = False
ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_vite',
    'lkypanel.apps.LkypanelConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'lkypanel.middleware.PortIsolationMiddleware',
    'lkypanel.middleware.RoleEnforcementMiddleware',
    'lkypanel.middleware.APIRateLimitMiddleware',
]

ROOT_URLCONF = 'lkypanel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'lkypanel' / 'templates'],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'lkypanel.context_processors.plugin_states',
                'lkypanel.context_processors.notification_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'lkypanel.wsgi.application'

# ---------------------------------------------------------------------------
# Database — SQLite at /usr/local/lkypanel/db/panel.db
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': INSTALL_DIR / 'db' / 'panel.db',
    }
}

# ---------------------------------------------------------------------------
# Password hashing — Argon2 first (requires argon2-cffi)
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# ---------------------------------------------------------------------------
# Password validation (complexity rules — full validator added in task 3)
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'lkypanel.validators.PasswordComplexityValidator'},
]

# ---------------------------------------------------------------------------
# Session security
# ---------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 1800  # 30 minutes

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = False  # Set to True if behind HTTPS proxy correctly

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files — served by OpenLiteSpeed directly
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = INSTALL_DIR / 'staticfiles'

# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'lkypanel.User'

# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'lkypanel.User'

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Logging — /var/log/lkypanel/
# ---------------------------------------------------------------------------
import os as _os
_LOG_DIR = '/var/log/lkypanel'
try:
    _os.makedirs(_LOG_DIR, exist_ok=True)
except PermissionError:
    _LOG_DIR = INSTALL_DIR / 'logs'
    _os.makedirs(_LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{_LOG_DIR}/panel.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
    },
}

# ---------------------------------------------------------------------------
# Vite Integration (django-vite)
# ---------------------------------------------------------------------------
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "manifest_path": BASE_DIR / "lkypanel" / "static" / "dist" / ".vite" / "manifest.json",
        "dev_server_host": "0.0.0.0",
        "dev_server_port": 5173,
    }
}

STATICFILES_DIRS = [
    BASE_DIR / "lkypanel" / "static",
    BASE_DIR / "lkypanel" / "static" / "dist",
]
