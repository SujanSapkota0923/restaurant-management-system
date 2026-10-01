"""WSGI entry point. Defaults to production settings so that a deploy without
an explicit settings module fails closed (validation) rather than open."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
