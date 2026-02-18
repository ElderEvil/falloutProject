from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables before importing settings
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from app.core.config import settings  # noqa: E402

celery_app = Celery(
    "async_task",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
    backend=str(settings.SYNC_CELERY_DATABASE_URI),
    include=["app.api.celery_task"],
)

celery_app.conf.update({"beat_dburi": str(settings.SYNC_CELERY_BEAT_DATABASE_URI)})

# Configure Celery Beat schedule for game loop
celery_app.conf.beat_schedule = {
    "game-tick-every-60-seconds": {
        "task": "game_tick",
        "schedule": 60.0,
        "options": {"expires": 55},
    },
    "check-permanent-deaths-daily": {
        "task": "check_permanent_deaths",
        "schedule": 86400.0,
        "options": {"expires": 82800},
    },
    "refresh-daily-objectives": {
        "task": "refresh_daily_objectives",
        "schedule": 86400.0,
        "options": {"expires": 82800},
    },
    "refresh-weekly-objectives": {
        "task": "refresh_weekly_objectives",
        "schedule": crontab(minute=0, hour=0, day_of_week="monday"),
    },
}

celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks()
