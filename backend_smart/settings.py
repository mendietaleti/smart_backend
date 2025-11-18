"""
Django settings for backend_smart project.

Optimizado para despliegue en Render
Backend: Django + Gunicorn + Whitenoise
Base de Datos: PostgreSQL (Render)
"""

import os
from pathlib import Path
from decouple import config
import dj_database_url

# -------------------------------
# RUTAS BASE
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------------
# CONFIGURACIONES BÁSICAS
# -------------------------------
SECRET_KEY = config('SECRET_KEY', default='unsafe-key')
DEBUG = config('DEBUG', default=False, cast=bool)

# Llaves externas
API_KEY_IMGBB = config('API_KEY_IMGBB', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Token opcional para generar datos de prueba sin sesión (Render)
DATA_GENERATION_TOKEN = config('DATA_GENERATION_TOKEN', default='')

# Render asigna su dominio en producción
ALLOWED_HOSTS = ['*']


# -------------------------------
# APLICACIONES INSTALADAS
# -------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'autenticacion_usuarios',
    'dashboard_inteligente',
    'productos',
    'reportes_dinamicos',
    'ventas_carrito',
]


# -------------------------------
# MIDDLEWARE
# -------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',

    # Whitenoise para servir estáticos en producción
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# -------------------------------
# CORS / CSRF
# -------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://smart-frontend-blond.vercel.app",
]

# Permitir todos los subdominios de Vercel (para previews y producción)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# Si DEBUG está activo, permitir todos los orígenes (solo para desarrollo)
# En producción, usar solo los orígenes específicos arriba
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = False  # Mantener False incluso en DEBUG para seguridad
else:
    CORS_ALLOW_ALL_ORIGINS = False  # Siempre False en producción

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://smart-frontend-blond.vercel.app",
    "https://*.vercel.app",
]

CORS_ALLOW_CREDENTIALS = True

# Headers adicionales permitidos
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-data-token',
]

# Métodos permitidos
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Configuración adicional para asegurar que CORS funcione
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 horas

# Configuración de cookies para CORS cross-origin
# En producción (HTTPS), usar SameSite=None; en desarrollo, usar Lax
SESSION_COOKIE_SECURE = not DEBUG  # True en producción (HTTPS requerido)
CSRF_COOKIE_SECURE = not DEBUG  # True en producción (HTTPS requerido)
SESSION_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"  # None para CORS cross-origin en producción
CSRF_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"  # None para CORS cross-origin en producción
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # False para que JavaScript pueda leerlo si es necesario


# -------------------------------
# URL PRINCIPAL Y WSGI
# -------------------------------
ROOT_URLCONF = 'backend_smart.urls'

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

WSGI_APPLICATION = 'backend_smart.wsgi.application'


# -------------------------------
# BASE DE DATOS (Render)
# -------------------------------
DATABASES = {
    'default': dj_database_url.config(default=os.environ.get("DATABASE_URL"))
}


# -------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# -------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# -------------------------------
# INTERNACIONALIZACIÓN
# -------------------------------
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True


# -------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# -------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# -------------------------------
# DJANGO REST FRAMEWORK
# -------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}


# -------------------------------
# AUTO-FIELD POR DEFECTO
# -------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
