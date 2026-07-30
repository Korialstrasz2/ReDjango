import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redjango.settings")

application = get_asgi_application()

from backend.core.backup_scheduler import start_backup_scheduler

start_backup_scheduler()
