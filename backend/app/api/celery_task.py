import time

from app.core.celery import celery_app


@celery_app.task(name="create_task")
def create_task(task_time: int):
    time.sleep(task_time)
    return True
