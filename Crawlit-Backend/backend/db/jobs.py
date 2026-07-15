from __future__ import annotations

from contextlib import asynccontextmanager
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import aiosqlite

from backend.db.database import DB_PATH
from backend.db.models import Job, JobStatus
from backend.db.models import Job, JobStatus, Repository


class JobCancelledError(Exception):
    pass


class JobRepository:
    def __init__(
        self,
        db_path: Path | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        self._db_path = db_path or DB_PATH
        self._max_retries = max_retries if max_retries is not None else int(os.getenv("JOB_MAX_RETRIES", "3"))
        self._retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else float(os.getenv("JOB_RETRY_BACKOFF_SECONDS", "2"))
        )

    async def initialize_schema(self) -> None:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
            )
            row = await cursor.fetchone()

            if row is None:
                await self._create_jobs_table(db)
            else:
                schema_sql = row[0] or ""
                if not self._schema_is_current(schema_sql):
                    await self._migrate_jobs_table(db)

            cursor = await db.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'repositories'"
            )
            row = await cursor.fetchone()
            if row is None:
                await self._create_repositories_table(db)

            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_active_repo
                ON jobs(owner, repo)
                WHERE status IN ('queued', 'running')
                """
            )
            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_repositories_owner_repo
                ON repositories(owner, repo)
                """
            )
            await db.commit()

    async def create_job(
        self,
        owner: str,
        repo: str,
        job_id: str | None = None,
        status: JobStatus = JobStatus.QUEUED,
    ) -> Job:
        job_id = job_id or uuid4().hex

        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT id, owner, repo, status, current_stage, progress, retry_count, cancelled, error, next_attempt_at, created_at, updated_at
                FROM jobs
                WHERE owner = ?
                  AND repo = ?
                  AND status IN (?, ?)
                  AND cancelled = 0
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (
                    owner,
                    repo,
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ),
            )
            existing = await cursor.fetchone()

            if existing is not None:
                await self._upsert_repository_record(
                    db,
                    owner,
                    repo,
                    existing["id"],
                    JobStatus(existing["status"]),
                    indexed=False,
                    last_indexed=None,
                )
                await db.commit()
                return self._row_to_job(existing)

            await db.execute(
                """
                INSERT INTO jobs (
                    id, owner, repo, status, current_stage, progress, retry_count, cancelled, error, next_attempt_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, NULL, NULL)
                """,
                (job_id, owner, repo, status.value, "Queued", 0),
            )
            await self._upsert_repository_record(
                db,
                owner,
                repo,
                job_id,
                status,
                indexed=False,
                last_indexed=None,
            )
            await db.commit()

        job = await self.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Failed to load job {job_id} after creation")
        return job

    async def reset_running_jobs(self) -> int:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = ?, progress = 0, error = NULL, next_attempt_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE status = ?
                """,
                (JobStatus.QUEUED.value, "Queued", JobStatus.RUNNING.value),
            )
            await db.execute(
                """
                UPDATE repositories
                SET status = ?, indexed = 0, updated_at = CURRENT_TIMESTAMP
                WHERE status = ?
                """,
                (JobStatus.QUEUED.value, JobStatus.RUNNING.value),
            )
            await db.commit()
            return cursor.rowcount

    async def claim_next_job(self) -> Job | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT id, owner, repo, status, current_stage, progress, retry_count, cancelled, error, next_attempt_at, created_at, updated_at
                FROM jobs
                WHERE status = ?
                  AND cancelled = 0
                  AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP)
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (JobStatus.QUEUED.value,),
            )
            row = await cursor.fetchone()

            if row is None:
                await db.commit()
                return None

            await db.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = ?, progress = 0, error = NULL, cancelled = 0, next_attempt_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.RUNNING.value, "Cloning", row["id"]),
            )
            await db.commit()

        return await self.get_job(row["id"])

    async def get_job(self, job_id: str) -> Job | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT id, owner, repo, status, current_stage, progress, retry_count, cancelled, error, next_attempt_at, created_at, updated_at
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    async def set_job_phase(self, job_id: str, stage: str, progress: int) -> Job | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT status, cancelled
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                await db.commit()
                return None

            if row["status"] in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value) or row["cancelled"]:
                await db.commit()
                return await self.get_job(job_id)

            await db.execute(
                """
                UPDATE jobs
                SET current_stage = ?, progress = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (stage, progress, job_id),
            )
            await db.commit()
        return await self.get_job(job_id)

    async def complete_job(self, job_id: str) -> Job | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT status, cancelled
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                await db.commit()
                return None

            if row["status"] == JobStatus.CANCELLED.value or row["cancelled"]:
                await db.commit()
                return await self.get_job(job_id)

            await db.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = ?, progress = 100, error = NULL, cancelled = 0, next_attempt_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.COMPLETED.value, "Completed", job_id),
            )
            await db.execute(
                """
                INSERT INTO repositories (owner, repo, indexed, job_id, status, last_indexed, created_at, updated_at)
                VALUES (
                    (SELECT owner FROM jobs WHERE id = ?),
                    (SELECT repo FROM jobs WHERE id = ?),
                    1,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(owner, repo) DO UPDATE SET
                    indexed = excluded.indexed,
                    job_id = excluded.job_id,
                    status = excluded.status,
                    last_indexed = excluded.last_indexed,
                    updated_at = excluded.updated_at
                """,
                (job_id, job_id, job_id, JobStatus.COMPLETED.value),
            )
            await db.commit()
        return await self.get_job(job_id)

    async def record_job_failure(self, job_id: str, error: str) -> Job | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT retry_count, status, cancelled, current_stage, progress
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                await db.commit()
                return None

            if row["status"] == JobStatus.CANCELLED.value or row["cancelled"]:
                await db.commit()
                return await self.get_job(job_id)

            retry_count = int(row["retry_count"])
            next_retry_count = retry_count + 1

            if next_retry_count <= self._max_retries:
                delay_seconds = self._retry_backoff_seconds * (2 ** (next_retry_count - 1))
                next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
                await db.execute(
                    """
                    UPDATE jobs
                    SET status = ?, current_stage = ?, progress = 0, retry_count = ?, error = ?, cancelled = 0, next_attempt_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        JobStatus.QUEUED.value,
                        "Queued",
                        next_retry_count,
                        error,
                        next_attempt_at.isoformat(sep=" ", timespec="seconds"),
                        job_id,
                    ),
                )
                await db.execute(
                    """
                    INSERT INTO repositories (owner, repo, indexed, job_id, status, updated_at)
                    VALUES (
                        (SELECT owner FROM jobs WHERE id = ?),
                        (SELECT repo FROM jobs WHERE id = ?),
                        0,
                        ?,
                        ?,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(owner, repo) DO UPDATE SET
                        indexed = excluded.indexed,
                        job_id = excluded.job_id,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (job_id, job_id, job_id, JobStatus.QUEUED.value),
                )
            else:
                await db.execute(
                    """
                    UPDATE jobs
                    SET status = ?, current_stage = ?, retry_count = ?, error = ?, next_attempt_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        JobStatus.FAILED.value,
                        "Failed",
                        next_retry_count,
                        error,
                        job_id,
                    ),
                )
                await db.execute(
                    """
                    INSERT INTO repositories (owner, repo, indexed, job_id, status, updated_at)
                    VALUES (
                        (SELECT owner FROM jobs WHERE id = ?),
                        (SELECT repo FROM jobs WHERE id = ?),
                        0,
                        ?,
                        ?,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(owner, repo) DO UPDATE SET
                        indexed = excluded.indexed,
                        job_id = excluded.job_id,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (job_id, job_id, job_id, JobStatus.FAILED.value),
                )

            await db.commit()

        return await self.get_job(job_id)

    async def cancel_job(self, job_id: str) -> Job | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT id, status, cancelled
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                await db.commit()
                return None

            if row["status"] in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
                await db.commit()
                return await self.get_job(job_id)

            await db.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = ?, error = ?, cancelled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.CANCELLED.value, "Cancelled", "Cancelled", job_id),
            )
            await db.execute(
                """
                INSERT INTO repositories (owner, repo, indexed, job_id, status, updated_at)
                VALUES (
                    (SELECT owner FROM jobs WHERE id = ?),
                    (SELECT repo FROM jobs WHERE id = ?),
                    0,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(owner, repo) DO UPDATE SET
                    indexed = excluded.indexed,
                    job_id = excluded.job_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (job_id, job_id, job_id, JobStatus.CANCELLED.value),
            )
            await db.commit()

        return await self.get_job(job_id)

    async def update_status(self, job_id: str, status: JobStatus) -> Job | None:
        await self._execute_update(
            """
            UPDATE jobs
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status.value, job_id),
        )
        return await self.get_job(job_id)

    async def update_progress(self, job_id: str, progress: int) -> Job | None:
        await self._execute_update(
            """
            UPDATE jobs
            SET progress = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (progress, job_id),
        )
        return await self.get_job(job_id)

    async def fail_job(self, job_id: str, error: str) -> Job | None:
        await self._execute_update(
            """
            UPDATE jobs
            SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (JobStatus.FAILED.value, error, job_id),
        )
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO repositories (owner, repo, indexed, job_id, status, updated_at)
                VALUES (
                    (SELECT owner FROM jobs WHERE id = ?),
                    (SELECT repo FROM jobs WHERE id = ?),
                    0,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(owner, repo) DO UPDATE SET
                    indexed = excluded.indexed,
                    job_id = excluded.job_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (job_id, job_id, job_id, JobStatus.FAILED.value),
            )
            await db.commit()
        return await self.get_job(job_id)

    async def get_repository(self, owner: str, repo: str) -> Repository | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT owner, repo, indexed, job_id, status, last_indexed
                FROM repositories
                WHERE owner = ?
                  AND repo = ?
                """,
                (owner, repo),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_repository(row)

    async def _execute_update(self, sql: str, params: tuple[object, ...]) -> None:
        async with self._connect() as db:
            await db.execute(sql, params)
            await db.commit()

    def _row_to_job(self, row: aiosqlite.Row) -> Job:
        return Job(
            id=row["id"],
            owner=row["owner"],
            repo=row["repo"],
            status=JobStatus(row["status"]),
            current_stage=row["current_stage"],
            progress=row["progress"],
            retry_count=row["retry_count"],
            cancelled=bool(row["cancelled"]),
            error=row["error"],
            next_attempt_at=self._parse_timestamp(row["next_attempt_at"]),
            created_at=self._parse_timestamp(row["created_at"]),
            updated_at=self._parse_timestamp(row["updated_at"]),
        )

    def _row_to_repository(self, row: aiosqlite.Row) -> Repository:
        return Repository(
            owner=row["owner"],
            repo=row["repo"],
            indexed=bool(row["indexed"]),
            job_id=row["job_id"],
            status=JobStatus(row["status"]),
            last_indexed=self._parse_timestamp(row["last_indexed"]),
        )

    def _schema_is_current(self, schema_sql: str) -> bool:
        return "cancelled" in schema_sql and "current_stage" in schema_sql and "retry_count" in schema_sql

    async def _create_jobs_table(self, db: aiosqlite.Connection) -> None:
        await db.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                current_stage TEXT NOT NULL DEFAULT 'Queued',
                progress INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                cancelled INTEGER NOT NULL DEFAULT 0,
                error TEXT NULL,
                next_attempt_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    async def _create_repositories_table(self, db: aiosqlite.Connection) -> None:
        await db.execute(
            """
            CREATE TABLE repositories (
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                indexed INTEGER NOT NULL DEFAULT 0,
                job_id TEXT NULL,
                status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                last_indexed TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (owner, repo)
            )
            """
        )

    async def _upsert_repository_record(
        self,
        db: aiosqlite.Connection,
        owner: str,
        repo: str,
        job_id: str | None,
        status: JobStatus,
        indexed: bool,
        last_indexed: datetime | None,
    ) -> None:
        await db.execute(
            """
            INSERT INTO repositories (owner, repo, indexed, job_id, status, last_indexed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(owner, repo) DO UPDATE SET
                indexed = excluded.indexed,
                job_id = excluded.job_id,
                status = excluded.status,
                last_indexed = COALESCE(excluded.last_indexed, repositories.last_indexed),
                updated_at = excluded.updated_at
            """,
            (
                owner,
                repo,
                1 if indexed else 0,
                job_id,
                status.value,
                last_indexed.isoformat(sep=" ", timespec="seconds") if last_indexed else None,
            ),
        )

    async def _migrate_jobs_table(self, db: aiosqlite.Connection) -> None:
        await db.execute("ALTER TABLE jobs RENAME TO jobs_old")
        await self._create_jobs_table(db)
        await db.execute(
            """
            INSERT INTO jobs (
                id, owner, repo, status, current_stage, progress, retry_count, cancelled, error, next_attempt_at, created_at, updated_at
            )
            SELECT
                id,
                owner,
                repo,
                CASE
                    WHEN status IN ('queued', 'running', 'completed', 'failed', 'cancelled') THEN status
                    ELSE 'failed'
                END,
                CASE
                    WHEN status = 'completed' THEN 'Completed'
                    WHEN status = 'failed' THEN 'Failed'
                    WHEN status = 'cancelled' THEN 'Cancelled'
                    WHEN status = 'running' THEN 'Cloning'
                    ELSE 'Queued'
                END,
                COALESCE(progress, 0),
                0,
                CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END,
                error,
                NULL,
                created_at,
                updated_at
            FROM jobs_old
            """
        )
        await db.execute("DROP TABLE jobs_old")

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    @asynccontextmanager
    async def _connect(self):
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
