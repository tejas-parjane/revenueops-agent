from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "revenueops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
)
