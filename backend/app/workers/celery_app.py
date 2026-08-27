from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "masea",
    broker=settings.celery_broker_url_resolved,
    backend=settings.celery_result_backend_resolved,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_always_eager=(settings.environment == "test"),
    task_eager_propagates=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
