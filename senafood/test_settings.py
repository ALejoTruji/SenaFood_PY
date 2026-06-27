from .settings import *

# BD SQLite en memoria para pruebas
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': ':memory:',
        }
    }
}

# Omitir migraciones con SQL específico de MySQL
MIGRATION_MODULES = {
    'pqrs': None,
    'producto': None,
    'inventario': None,
    'proveedor': None,
    'ordencompra': None,
    'notificaciones': None,
    'ventas': None,
}

# Correos en memoria
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Sin caché
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# SOLUCIÓN: sobreescribir STORAGES completo (Django 4.2+)
# Reemplaza el CompressedManifestStaticFilesStorage de WhiteNoise
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Quitar WhiteNoise del middleware
MIDDLEWARE = [m for m in MIDDLEWARE if 'whitenoise' not in m.lower()]

DEBUG = True