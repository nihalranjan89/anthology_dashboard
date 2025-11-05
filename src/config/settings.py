import os
from pathlib import Path
import environ


BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS', default='').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'anthology',
]

MIDDLEWARE = [
    'anthology.middleware.DisableBrowserCacheMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware'
    
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'anthology' / 'templates'],
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
'''
import ldap
from django_auth_ldap.config import LDAPSearch

# LDAP Basic Config
AUTH_LDAP_SERVER_URI = os.getenv('LDAP_SERVER')
AUTH_LDAP_BIND_DN = os.getenv('LDAP_BIND_DN')
AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD')
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    os.getenv('LDAP_BASE_DN'),
    ldap.SCOPE_SUBTREE,
    "(sAMAccountName=%(user)s)"
)'''

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'anthology' / 'static']

# Session
SESSION_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SECURE = False if DEBUG else True
SESSION_COOKIE_HTTPONLY = True

# Constants (from env)
PERMISSION_PREFIX = env('PERMISSION_PREFIX', default='ANTG')
PERMISSION_SUFFIX_ADMIN = env('PERMISSION_SUFFIX_ADMIN', default='ADMIN')
PERMISSION_SUFFIX_QA = env('PERMISSION_SUFFIX_QA', default='QA-APPROVER')
PERMISSION_SUFFIX_REGION = env('PERMISSION_SUFFIX_REGION', default='REGION')
PERMISSION_SUFFIX_SITE = env('PERMISSION_SUFFIX_SITE', default='SITE')

# Azure and LDAP
AZ_STORAGE_HOSTNAME = env('AZ_STORAGE_HOSTNAME', default='')
AZ_STORAGE_DRAFTS_URI = env('AZ_STORAGE_DRAFTS_URI', default='')
AZ_STORAGE_FINALS_URI = env('AZ_STORAGE_FINALS_URI', default='')
AZ_TOKEN = env('AZ_TOKEN', default='')

LDAP_IDP_HOSTNAME = env('LDAP_IDP_HOSTNAME', default='')
LDAP_BIND_USER = env('LDAP_BIND_USER', default='')
LDAP_BIND_PASS = env('LDAP_BIND_PASS', default='')

# SSO constants
SSO_HOSTNAME = env('SSO_HOSTNAME', default='')
SSO_LOGIN_URI = env('SSO_LOGIN_URI', default='')
SSO_LOGOUT_URI = env('SSO_LOGOUT_URI', default='')
SSO_CALLBACK_URI = env('SSO_CALLBACK_URI', default='login_cb')
ACCESS_APPROVER_EMAIL = env('ACCESS_APPROVER_EMAIL', default='')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Redirect URL after login
LOGIN_REDIRECT_URL = '/reports/'


