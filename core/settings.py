from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'asdf-ghijkl-mn-1234-5678'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.staticfiles',
    'rest_framework',

    # third party apps
    'drf_yasg',

    # apps
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
}]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = 'static/'

FUEL_STATIONS_CSV = BASE_DIR / 'fuel-prices-for-be-assessment.csv'
OSRM_BASE_URL = 'http://router.project-osrm.org'
NOMINATIM_BASE_URL = 'https://nominatim.openstreetmap.org'

VEHICLE_MAX_RANGE_MILES = 500
VEHICLE_MPG = 10
TANK_CAPACITY_GALLONS = 50

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

GEOCODE_OVERRIDE = {
    "big cabin": (36.5095, -95.2083),
    "tomah": (43.9786, -90.5040),
}
