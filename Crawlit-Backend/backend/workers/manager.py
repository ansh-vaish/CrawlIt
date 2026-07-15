from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from backend.db.jobs import JobRepository
from backend.workers.worker import JobWorker

Processor = Callable[..., Awaitable[object]]


class WorkerManager:
    def __init__(
        self,
        repository: JobRepository,
        processor: Processor,
        worker_count: int = 2,
    ) -> None:
        self._repository = repository
        self._processor = processor
        self._worker_count = worker_count
        self._workers = [JobWorker(self._repository, self._processor) for _ in range(self._worker_count)]
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self._tasks:
            return

        self._tasks = [asyncio.create_task(worker.run()) for worker in self._workers]

    async def shutdown(self) -> None:
        if not self._tasks:
            return

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
