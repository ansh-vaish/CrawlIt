from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).resolve().parent / "app.db"


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db() -> None:
    from backend.db.jobs import JobRepository

    repository = JobRepository()
    await repository.initialize_schema()