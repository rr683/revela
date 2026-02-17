"""
Celery application configuration.

Usage:
    # Start worker
    celery -A workers.celery_app worker --loglevel=info --concurrency=1

    # Start with GPU task routing
    celery -A workers.celery_app worker --loglevel=info -Q gpu --concurrency=1
"""

import os
import sys
from pathlib import Path

from celery import Celery

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import get_config

config = get_config()
celery_config = config.celery

app = Celery(
    "revela",
    broker=os.environ.get("CELERY_BROKER_URL", celery_config.broker_url),
    backend=os.environ.get("CELERY_RESULT_BACKEND", celery_config.result_backend),
)

app.conf.update(
    task_serializer=celery_config.task_serializer,
    result_serializer=celery_config.result_serializer,
    accept_content=celery_config.accept_content,
    timezone=celery_config.timezone,
    worker_prefetch_multiplier=celery_config.worker_prefetch_multiplier,
    worker_max_tasks_per_child=celery_config.worker_max_tasks_per_child,
    # Only one GPU task at a time per worker
    worker_concurrency=1,
    # Route reconstruction tasks to GPU queue
    task_routes={
        "workers.tasks.run_reconstruction": {"queue": "gpu"},
    },
    # Keep results for 24 hours
    result_expires=86400,
)

# Auto-discover tasks
app.autodiscover_tasks(["workers"])
