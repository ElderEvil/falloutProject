import time

from app.core.celery import celery_app


@celery_app.task(name="create_task1")
def create_task(task_time: int):
    time.sleep(task_time)
    return True
