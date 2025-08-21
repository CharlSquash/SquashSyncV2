# coach_project/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv
import datetime

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))


# --- SECURITY SETTINGS ---
# The SECRET_KEY is read from an environment variable
SECRET_KEY = os.environ.get('SECRET_KEY')

# Smart DEBUG setting: Defaults to False (production) unless DEV_MODE=True in .env
DEBUG = os.environ.get('DEV_MODE') == 'True'

# Smart ALLOWED_HOSTS and URL settings
if DEBUG:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.3.6'] # Add any other local IPs you use
    APP_SITE_URL = 'http://127.0.0.1:8000'
    CSRF_TRUSTED_ORIGINS = [] # Not usually needed for local dev
else:
    ALLOWED_HOSTS = ['www.squashsync.com', 'CharlSquash.pythonanywhere.com']
    APP_SITE_URL = 'https://www.squashsync.com'
    CSRF_TRUSTED_ORIGINS = ['https://www.squashsync.com', 'https://CharlSquash.pythonanywhere.com']


# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'players',
    'scheduling',
    'live_session',
    'assessments',
    'finance',
    'core',
    'rest_framework',
    'rest_framework_simplejwt', # Make sure this is here for JWT
    'corsheaders', # <<< ADD THIS LINE
    'crispy_forms',
    "crispy_bootstrap5",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware', # <<< ADD THIS LINE (must be high up)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'coach_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'coach_project.wsgi.application'


# --- DATABASE ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --- PASSWORD VALIDATION ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- INTERNATIONALIZATION & TIMEZONE ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True


# --- STATIC & MEDIA FILES ---
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'

MEDIA_URL = '/media/'
MEDIA_ROOT= BASE_DIR / 'mediafiles'


# --- THIRD-PARTY APPS ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# --- DJANGO REST FRAMEWORK & JWT ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}

# --- AUTHENTICATION ---
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- SMART EMAIL CONFIGURATION ---
if DEBUG:
    # Local development: Print emails to the console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # Production: Use Gmail's SMTP server
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASS')


# --- CUSTOM APP SETTINGS ---
BONUS_SESSION_START_TIME = datetime.time(6, 0, 0) # 6:00 AM
BONUS_SESSION_AMOUNT = 22.00


# --- CORS SETTINGS (ADD THIS ENTIRE SECTION) ---
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',      # Your React local development server
    'http://127.0.0.1:3000',     # Also include this for good measure
    # When you deploy, you will add your Vercel URL here:
    # 'https://solosync-pwa.vercel.app',
    # 'https://app.squashsync.com',
]
