from contextlib import asynccontextmanager
from os import environ
from uuid import uuid4
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.core import answer_query, get_mermaid_diagram, process_repo
from backend.doc_generator import RepositoryContext
from backend.db.database import init_db
from backend.db.jobs import JobRepository
from backend.db.models import Job, JobStatus
from backend.db.models import Job, JobStatus, Repository
from backend.workers import WorkerManager


origins = [
    environ.get("FRONTEND_URL", "http://localhost:3000")
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    repository = JobRepository()
    await repository.reset_running_jobs()
    worker_manager = WorkerManager(repository, process_repo)

    await worker_manager.start()

    app.state.job_repository = repository
    app.state.worker_manager = worker_manager

    try:
        yield
    finally:
        await worker_manager.shutdown()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RepoRequest(BaseModel):
    repoOwner: str
    repoName: str

class QueryRequest(BaseModel):
    repoOwner: str
    repoName: str
    query: str

class MermaidRequest(BaseModel):
    repoOwner: str
    repoName: str


def build_repository_context(repo_owner: str, repo_name: str) -> RepositoryContext:
    backend_dir = Path(__file__).resolve().parent
    return RepositoryContext(
        owner=repo_owner,
        name=repo_name,
        repo_dir=backend_dir / "repos" / repo_owner / repo_name,
        summary_file=backend_dir / "generated_docs" / f"{repo_owner}_{repo_name}.md",
    )


def serialize_job(job: Job) -> dict[str, object]:
    return {
        "job_id": job.id,
        "owner": job.owner,
        "repo": job.repo,
        "status": job.status.value,
        "current_stage": job.current_stage,
        "progress": job.progress,
        "retry_count": job.retry_count,
        "cancelled": job.cancelled,
        "error": job.error,
        "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def serialize_repository(repository: Repository) -> dict[str, object]:
    return {
        "owner": repository.owner,
        "repo": repository.repo,
        "indexed": repository.indexed,
        "job_id": repository.job_id,
        "status": repository.status.value,
        "last_indexed": repository.last_indexed.isoformat() if repository.last_indexed else None,
    }


@app.post("/index")
async def index_repository(req: RepoRequest):
    repository: JobRepository = app.state.job_repository

    job = await repository.create_job(
        req.repoOwner,
        req.repoName,
        status=JobStatus.QUEUED,
    )

    return serialize_job(job)


@app.get("/repositories/{owner}/{repo}")
async def get_repository(owner: str, repo: str):
    repository: JobRepository = app.state.job_repository
    repo_record = await repository.get_repository(owner, repo)
    if repo_record is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return serialize_repository(repo_record)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    repository: JobRepository = app.state.job_repository
    job = await repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job)


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    repository: JobRepository = app.state.job_repository
    job = await repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job = await repository.cancel_job(job_id)
    return serialize_job(job)

@app.get("/answer")
async def answer(req : QueryRequest = Depends()):
    context = build_repository_context(req.repoOwner, req.repoName)
    result = await answer_query(context, req.query)
    return result

@app.get("/mermaid")
async def mermaid(req : MermaidRequest = Depends()):
    context = build_repository_context(req.repoOwner, req.repoName)
    result = await get_mermaid_diagram(context)
    return result
