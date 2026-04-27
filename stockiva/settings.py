"""
Django settings for stockiva project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 🔐 GÜVENLİK AYARLARI
# ==============================================================================

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Production'da callback URL'i için (İyzico vs.)
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000')

# ==============================================================================
# 📦 UYGULAMALAR
# ==============================================================================

INSTALLED_APPS = [
    'accounts.apps.AccountsConfig',
    'rest_framework',
    'core',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'two_factor',
    'two_factor.plugins.phonenumber',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # EKLENDİ: Statik dosyalar için
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'axes.middleware.AxesMiddleware',  # DÜZELTİLDİ: En sona alındı
]

ROOT_URLCONF = 'stockiva.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stockiva.wsgi.application'

# ==============================================================================
# 🗄️ VERİTABANI
# ==============================================================================

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=not DEBUG  # Prod'da SSL zorunlu, dev'de değil
    )
}

# ==============================================================================
# 🔑 ŞİFRE DOĞRULAMA
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================================================
# 🌍 DİL VE ZAMAN AYARLARI
# ==============================================================================

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'  # UTC yerine Türkiye saati
USE_I18N = True
USE_TZ = True

# ==============================================================================
# 📁 STATİK DOSYALAR
# ==============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# EKLENDİ: Whitenoise ile statik dosyaları canlıda sunma
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# EKLENDİ: Sunucu arkası (Nginx/Load Balancer) CSRF güvenliği
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host]

# ==============================================================================
# 🔗 GİRİŞ / ÇIKIŞ YÖNLENDIRMELER
# ==============================================================================

LOGIN_URL = 'two_factor:login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
SITE_ID = 1

# ==============================================================================
# 📧 E-POSTA AYARLARI
# ==============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'Stockiva Destek <{EMAIL_HOST_USER}>'

ACCOUNT_ACTIVATION_DAYS = 1

# ==============================================================================
# 🤖 ÜÇÜNCÜ TARAF API ANAHTARLARI
# ==============================================================================

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # İleride kullanılacak

IYZICO_API_KEY = os.getenv('IYZICO_API_KEY')
IYZICO_SECRET_KEY = os.getenv('IYZICO_SECRET_KEY')
IYZICO_BASE_URL = os.getenv('IYZICO_BASE_URL', 'https://sandbox-api.iyzipay.com')

# ==============================================================================
# 🛡️ GÜVENLİK EKSTRALARİ (django-axes brute-force koruması)
# ==============================================================================

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # 1 saat

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ==============================================================================
# ⚡ ÖNBELLEK (Rate limit ve axes için)
# ==============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ==============================================================================
# 📝 LOGLAMA
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'core': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
