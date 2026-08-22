import os

import dramatiq
import periodiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import settings
from app.core.logging import setup_logging

if os.getenv("FALLOUT_WORKER") == "1":
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_format=settings.LOG_JSON_FORMAT,
        log_file=settings.log_file_path,
        retention_days=settings.LOG_FILE_RETENTION_DAYS,
    )

broker = RedisBroker(url=settings.redis_url)
broker.add_middleware(periodiq.PeriodiqMiddleware())
dramatiq.set_broker(broker)
