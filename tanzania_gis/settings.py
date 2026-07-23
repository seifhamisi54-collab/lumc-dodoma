import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


# SECURITY
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-8f467b93-3a5b-4ff6-9982-510c35b15659',
)
DEBUG = _env_bool('DJANGO_DEBUG', True)

_allowed = os.environ.get('DJANGO_ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

_csrf = os.environ.get(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001',
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(',') if o.strip()]

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# GDAL — Windows local paths (Docker sets GDAL_LIBRARY_PATH / GEOS_LIBRARY_PATH via env)
if os.name == 'nt':
    os.environ['PATH'] = r'C:\Program Files\GDAL;' + os.environ.get('PATH', '')
    os.environ['PROJ_LIB'] = r'C:\Program Files\GDAL\projlib'
    GDAL_LIBRARY_PATH = os.environ.get('GDAL_LIBRARY_PATH', r'C:\Program Files\GDAL\gdal.dll')
else:
    if os.environ.get('GDAL_LIBRARY_PATH'):
        GDAL_LIBRARY_PATH = os.environ['GDAL_LIBRARY_PATH']
    if os.environ.get('GEOS_LIBRARY_PATH'):
        GEOS_LIBRARY_PATH = os.environ['GEOS_LIBRARY_PATH']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'accounts',
    'locations',
    'landuse',
    'dashboard',
    'detailed_planning',
    'land_conflicts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'dashboard.middleware.AdminPasscodeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

try:
    import whitenoise  # noqa: F401
    _sec_idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
    MIDDLEWARE.insert(_sec_idx + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'tanzania_gis.urls'

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
                'dashboard.context_processors.integration_urls',
            ],
        },
    },
]

WSGI_APPLICATION = 'tanzania_gis.wsgi.application'

# Database — local defaults, or DATABASE_URL / DETAILED_DATABASE_URL (Render)
from urllib.parse import urlparse, unquote


def _postgis_config(name, user, password, host, port, search_path, sslmode=None):
    cfg = {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': name,
        'USER': user,
        'PASSWORD': password,
        'HOST': host,
        'PORT': str(port),
        'OPTIONS': {
            'options': f'-c search_path={search_path}',
        },
    }
    if sslmode:
        cfg['OPTIONS']['sslmode'] = sslmode
    return cfg


def _config_from_database_url(url, search_path):
    parsed = urlparse(url)
    sslmode = None
    if parsed.query:
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        if 'sslmode' in qs:
            sslmode = qs['sslmode'][0]
    # Render / cloud Postgres usually require SSL
    if sslmode is None and parsed.hostname and 'localhost' not in (parsed.hostname or ''):
        sslmode = 'require'
    return _postgis_config(
        name=unquote(parsed.path.lstrip('/')),
        user=unquote(parsed.username or ''),
        password=unquote(parsed.password or ''),
        host=parsed.hostname or '',
        port=parsed.port or 5432,
        search_path=search_path,
        sslmode=sslmode,
    )


_SEARCH_DEFAULT = 'boundaries,public,admin,demographic,infrastructure,landuse,detailed_planning'
_SEARCH_DETAILED = 'detailed_planning,public'

_database_url = os.environ.get('DATABASE_URL', '').strip()
_detailed_url = os.environ.get('DETAILED_DATABASE_URL', '').strip()

if _database_url:
    DATABASES = {
        'default': _config_from_database_url(_database_url, _SEARCH_DEFAULT),
        'detailed_planning': _config_from_database_url(
            _detailed_url or _database_url, _SEARCH_DETAILED
        ),
    }
else:
    _DB_HOST = os.environ.get('DB_HOST', 'localhost')
    _DB_PORT = os.environ.get('DB_PORT', '5433')
    _DB_USER = os.environ.get('DB_USER', 'postgres')
    _DB_PASSWORD = os.environ.get('DB_PASSWORD', '1701')
    _DB_NAME = os.environ.get('DB_NAME', 'tanzania_gis_db')
    _DB_NAME_DETAILED = os.environ.get('DB_NAME_DETAILED', 'DETAILED PLANNNING ')
    _DB_HOST_DETAILED = os.environ.get('DB_HOST_DETAILED', _DB_HOST)
    _DB_PORT_DETAILED = os.environ.get('DB_PORT_DETAILED', _DB_PORT)
    _DB_USER_DETAILED = os.environ.get('DB_USER_DETAILED', _DB_USER)
    _DB_PASSWORD_DETAILED = os.environ.get('DB_PASSWORD_DETAILED', _DB_PASSWORD)

    DATABASES = {
        'default': _postgis_config(
            _DB_NAME, _DB_USER, _DB_PASSWORD, _DB_HOST, _DB_PORT, _SEARCH_DEFAULT
        ),
        'detailed_planning': _postgis_config(
            _DB_NAME_DETAILED,
            _DB_USER_DETAILED,
            _DB_PASSWORD_DETAILED,
            _DB_HOST_DETAILED,
            _DB_PORT_DETAILED,
            _SEARCH_DETAILED,
        ),
    }

# Render injects RENDER_EXTERNAL_HOSTNAME
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
if _render_host and _render_host not in ALLOWED_HOSTS and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)
if _render_host:
    _origin = f'https://{_render_host}'
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

DATABASE_ROUTERS = ['tanzania_gis.db_router.DetailedPlanningRouter']

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'sw'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
try:
    import whitenoise  # noqa: F401
    # Compressed (not Manifest) — Manifest breaks deploy if any static ref is missing
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
except ImportError:
    pass

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AUTH_USER_MODEL = 'accounts.CustomUser'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

GIS_PORTAL_URL = os.environ.get('GIS_PORTAL_URL', 'http://localhost:8000')

DONATION_SETTINGS = {
    'SITE_URL': os.environ.get('DONATION_SITE_URL', GIS_PORTAL_URL),
    'STRIPE_SECRET_KEY': os.environ.get('STRIPE_SECRET_KEY', ''),
    'STRIPE_PUBLISHABLE_KEY': os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    'PESAPAL_CONSUMER_KEY': os.environ.get('PESAPAL_CONSUMER_KEY', ''),
    'PESAPAL_CONSUMER_SECRET': os.environ.get('PESAPAL_CONSUMER_SECRET', ''),
    'PESAPAL_BASE_URL': os.environ.get('PESAPAL_BASE_URL', 'https://pay.pesapal.com/v3'),
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.ERROR: 'error',
    messages.SUCCESS: 'success',
    messages.INFO: 'info',
    messages.WARNING: 'warning',
}

if DEBUG:
    MIDDLEWARE = [m for m in MIDDLEWARE if 'csp' not in m.lower()]
    # Prefer simpler static storage in development (manifest needs collectstatic)
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
