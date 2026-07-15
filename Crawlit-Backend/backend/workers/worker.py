from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from backend.db.jobs import JobCancelledError, JobRepository
from backend.db.models import JobStatus

logger = logging.getLogger(__name__)

Processor = Callable[..., Awaitable[object]]


class JobWorker:
    def __init__(self, repository: JobRepository, processor: Processor) -> None:
        self._repository = repository
        self._processor = processor

    async def run(self) -> None:
        while True:
            job = await self._repository.claim_next_job()
            if job is None:
                await asyncio.sleep(0.5)
                continue

            async def update_phase(stage: str, progress: int) -> None:
                await self._repository.set_job_phase(job.id, stage, progress)

            async def ensure_not_cancelled() -> None:
                current = await self._repository.get_job(job.id)
                if current is not None and current.status == JobStatus.CANCELLED:
                    raise JobCancelledError(job.id)

            try:
                await self._processor(
                    job.owner,
                    job.repo,
                    progress_callback=update_phase,
                    cancel_check=ensure_not_cancelled,
                )
                await ensure_not_cancelled()
                await self._repository.complete_job(job.id)
            except JobCancelledError:
                try:
                    await self._repository.cancel_job(job.id)
                except Exception:
                    logger.exception("Failed to mark job %s as cancelled", job.id)
            except Exception as exc:
                logger.exception("Job %s failed", job.id)
                try:
                    await self._repository.record_job_failure(job.id, str(exc))
                except Exception:
                    logger.exception("Failed to mark job %s as failed", job.id)