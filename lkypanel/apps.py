from django.apps import AppConfig


class LkypanelConfig(AppConfig):
    name = 'lkypanel'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Start APScheduler for SSL renewal (once per process)
        import os
        if os.environ.get('RUN_MAIN') != 'true':  # avoid double-start in dev
            from lkypanel.scheduler import start_scheduler
            start_scheduler()
