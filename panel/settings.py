"""
W3Panel v2 — Django Settings
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-w3panel-dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']
CSRF_TRUSTED_ORIGINS = ['https://*', 'http://*']

# Version
W3PANEL_VERSION = '2.0.0'

# Apps
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise',
    # W3Panel packages
    'packages.core',
    'packages.license',
    'packages.plugins',
    # W3Panel apps
    'apps.admin',
    'apps.user',
    'apps.api',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'packages.core.middleware.PortSessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # W3Panel middleware
    'packages.core.middleware.LicenseEnforcementMiddleware',
    'packages.core.middleware.PortIsolationMiddleware',
    'packages.core.middleware.RoleEnforcementMiddleware',
    'packages.core.middleware.APIRateLimitMiddleware',
]

# Database
DB_DIR = BASE_DIR / 'db'
DB_DIR.mkdir(exist_ok=True)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_DIR / 'panel.db',
    }
}

# Auth
AUTH_USER_MODEL = 'core.User'
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
LOGIN_URL = '/login/'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'packages.core.context_processors.panel_context',
                'packages.core.context_processors.system_metrics',
            ],
        },
    },
]

# URLs
ROOT_URLCONF = 'panel.urls'
WSGI_APPLICATION = 'panel.wsgi.application'

# Ports
ADMIN_PORT = 2087
USER_PORT = 2083
API_PORT = 2080

# License
LICENSE_SERVER = 'https://license.lkylab.com/api/validate'
LICENSE_GRACE_PERIOD_DAYS = 7

# API
API_RATE_LIMIT = 50  # requests per minute
API_RATE_LIMIT_BURST = 100

# Logging
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'panel.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'w3panel': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}