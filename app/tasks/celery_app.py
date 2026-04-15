"""
Celery application instance.

Workers are started with:
    celery -A app.tasks.celery_app.celery worker --loglevel=info

The broker and result backend both point to Redis, configured via REDIS_URL.
"""

from celery import Celery

from app.core.config import settings

celery: Celery = Celery(
    "aura_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.vision_tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks up to 3 times with exponential back-off.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
