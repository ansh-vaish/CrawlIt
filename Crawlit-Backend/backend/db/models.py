from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Job:
    id: str
    owner: str
    repo: str
    status: JobStatus
    current_stage: str = "Queued"
    progress: int = 0
    retry_count: int = 0
    cancelled: bool = False
    error: str | None = None
    next_attempt_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass(slots=True)
class Repository:
    owner: str
    repo: str
    indexed: bool
    job_id: str | None = None
    status: JobStatus = JobStatus.QUEUED
    last_indexed: datetime | None = None