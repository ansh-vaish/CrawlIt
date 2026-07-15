# CrawlIt Backend

FastAPI service that turns a public GitHub repository into searchable, chat-ready documentation. Given an `owner/repo`, it clones the repo, generates per-file and repository-level Markdown docs with an LLM, embeds them into Pinecone, and exposes a retrieval-augmented chat agent plus a generated Mermaid architecture diagram.

## Pipeline

```
POST /index  →  clone repo  →  generate docs (map-reduce)  →  embed & upsert to Pinecone  →  ready
```

1. **Clone** (`clone.py`) — validates the repo exists and is public via the GitHub API, then shallow-clones it (`--depth 1`) into `backend/repos/<owner>/<repo>`.
2. **Documentation generation** (`doc_generator.py`) — walks the repo, skipping build artifacts, locks, and binaries. Each source file is summarized by an LLM into a structured Markdown doc (overview, responsibilities, execution flow, dependencies, security notes, etc.). Large files are chunked, summarized per-chunk, and reduced into one unified doc (map-reduce). Work is parallelized across an async worker pool bounded by a semaphore over LLM concurrency, with retry/backoff on failed calls. A repository-level overview and a Mermaid architecture diagram are generated once all files are documented.
3. **Ingestion** (`ingestion.py`) — the generated docs are chunked and embedded (`nomic-embed-text` via Ollama) into a Pinecone namespace scoped to `owner-repo`, replacing any previous vectors for that repo.
4. **Retrieval agent** (`retrieve.py`) — a LangChain tool-calling agent that must retrieve documentation before answering any repository question. It decomposes questions into focused sub-queries, retrieves via MMR search, deduplicates chunks by content hash across calls in the same request, and labels every claim as either confirmed by retrieved docs or a general suggestion.

Indexing runs as a background job, not inline in the request — see **Jobs** below.

## Jobs & workers

Indexing a repo can take minutes, so `/index` only enqueues work; a small pool of async workers (`workers/manager.py`, `workers/worker.py`) polls SQLite for queued jobs and runs the pipeline.

- `db/jobs.py` is the job store: SQLite via `aiosqlite`, with `BEGIN IMMEDIATE` transactions for atomic job claiming, a partial unique index preventing duplicate active jobs for the same repo, and in-place schema migration if the table shape is out of date.
- Jobs left `running` when the process is killed are reset to `queued` on startup (`reset_running_jobs`), so a crash doesn't strand a repo in limbo.
- Jobs can be cancelled while queued or failed; cancellation is checked between pipeline stages and propagated via `JobCancelledError`.
- Progress is reported per stage (`Cloning → Documentation → Embedding → Completed`) and polled by the frontend.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/index` | Enqueue an indexing job for `{repoOwner, repoName}` |
| `GET` | `/repositories/{owner}/{repo}` | Current indexed state of a repository |
| `GET` | `/jobs/{job_id}` | Status/progress of a job |
| `DELETE` | `/jobs/{job_id}` | Cancel a queued or failed job |
| `GET` | `/answer?repoOwner=&repoName=&query=` | Ask the RAG agent a question about an indexed repo |
| `GET` | `/mermaid?repoOwner=&repoName=` | Fetch the generated architecture diagram |

## Requirements

- Python ≥ 3.13
- [uv](https://github.com/astral-sh/uv) (dependencies are pinned in `uv.lock`)
- A running [Ollama](https://ollama.com) instance with `nomic-embed-text:v1.5` pulled, for embeddings
- A Pinecone index
- An OpenAI-compatible LLM endpoint (currently configured for DigitalOcean's inference API)

## Setup

```bash
cd Crawlit-Backend
uv sync
```

Create a `.env` file in `Crawlit-Backend/`:

```bash
# LLM (OpenAI-compatible endpoint)
DO_API_KEY=your-api-key
DO_MODEL=your-model-name

# Pinecone
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=your-index-name

# Optional: doc generation tuning (all have defaults)
DOCGEN_CONCURRENCY=12          # max concurrent LLM calls
DOCGEN_FILE_WORKERS=12         # files processed in parallel
DOCGEN_CHUNK_SIZE=7000
DOCGEN_CHUNK_OVERLAP=500
DOCGEN_MAX_FILE_SIZE=500000    # bytes; larger files are skipped
DOCGEN_SPLIT_THRESHOLD=20000   # chars; files smaller than this aren't chunked
DOCGEN_LLM_TIMEOUT=120
DOCGEN_LLM_MAX_RETRIES=3

# Optional: job retry tuning
JOB_MAX_RETRIES=3
JOB_RETRY_BACKOFF_SECONDS=2
```

You'll also need Ollama running locally with the embedding model available:

```bash
ollama pull nomic-embed-text:v1.5
```

Run the server:

```bash
uv run uvicorn backend.api:app --reload
```

The API listens on `http://localhost:8000` by default and allows CORS from `http://localhost:3000` (the frontend's dev origin — update `origins` in `api.py` for other environments).

## Project layout

```
backend/
├── api.py              # FastAPI app, routes, request lifecycle
├── core.py              # Orchestrates the clone → docgen → ingest pipeline
├── clone.py              # Repo validation + shallow git clone
├── doc_generator.py      # LLM-based doc generation (map-reduce, mermaid)
├── ingestion.py           # Chunking + Pinecone upsert
├── retrieve.py             # RAG agent + retrieval tool + system prompt
├── db/
│   ├── database.py         # SQLite connection/init
│   ├── jobs.py               # Job & repository persistence layer
│   └── models.py              # Job / Repository / JobStatus dataclasses
└── workers/
    ├── manager.py            # Spins up/tears down the worker pool
    └── worker.py               # Polls for jobs, runs the pipeline, handles failure/cancellation
```

## Known limitations

- Only public repositories are supported (private repos are explicitly rejected in `clone.py`).
- Each `/index` call fully replaces the Pinecone namespace for that repo — there's no incremental re-indexing of changed files only
However duplicate cloning is restricted from frontend.
- The RAG agent call in `core.py` is currently synchronous and runs on the event loop rather than in a thread pool; under concurrent load this will serialize `/answer` requests.