"""
APScheduler — in-process SSL renewal cron.
Initialized once in AppConfig.ready() to avoid duplicate jobs across workers.
"""
import logging

logger = logging.getLogger(__name__)
_scheduler_started = False


def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone='UTC')
        scheduler.add_job(
            _renew_expiring_certs,
            trigger=CronTrigger(hour=3, minute=0),
            id='ssl_renewal',
            replace_existing=True,
        )
        scheduler.start()
        _scheduler_started = True
        logger.info('APScheduler started — SSL renewal job registered at 03:00 UTC')
    except Exception as e:
        logger.error('Failed to start APScheduler: %s', e)


def _renew_expiring_certs():
    from datetime import datetime, timedelta, timezone
    from lkypanel.models import SSLCertificate
    from lkypanel.services.ssl import renew_certificate

    threshold = datetime.now(timezone.utc) + timedelta(days=30)
    certs = SSLCertificate.objects.filter(expires_at__lte=threshold, auto_renew=True)
    logger.info('SSL renewal job: checking %d certificate(s)', certs.count())

    for cert in certs:
        try:
            renew_certificate(cert)
        except Exception as e:
            logger.error('Renewal failed for %s: %s', cert.website.domain, e)
