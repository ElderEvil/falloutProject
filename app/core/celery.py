from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "async_task",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
    backend=str(settings.SYNC_CELERY_DATABASE_URI),
    include="app.api.celery_task",
)

celery_app.conf.update({"beat_dburi": str(settings.SYNC_CELERY_BEAT_DATABASE_URI)})
celery_app.autodiscover_tasks()
