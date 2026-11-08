from celery import Celery

from app.config import settings
from app.services.pipeline import process_document

celery_app = Celery("docintel", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_track_started=True, task_time_limit=3600, task_soft_time_limit=3500)


@celery_app.task(
    name="process_document", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=3
)
def process_document_task(document_id: str) -> None:
    process_document(document_id)
