# CrawlIt

CrawlIt turns any public GitHub repository into something you can read *and* talk to. Point it at `owner/repo` and it will:

1. Clone the repository
2. Generate structured Markdown documentation for every source file, using an LLM with map-reduce summarization for large files
3. Roll those file summaries up into a repository-level overview and a Mermaid architecture diagram
4. Embed the documentation into a vector store
5. Let you ask questions about the codebase through a retrieval-augmented chat agent that's required to ground every answer in retrieved documentation

## Architecture

- **`Crawlit-Backend/`** — FastAPI service. Owns cloning, doc generation, embedding, job orchestration, and the RAG chat agent. See its [README](./Crawlit-Backend/README.md) for setup and API details.
- **`Crawlit Frontend/frontend/`** — Next.js app. Submits repos for indexing, polls progress, and renders the diagram + chat UI. See its [README](./Crawlit%20Frontend/frontend/README.md) for setup details.

## Why a job queue instead of a synchronous request

Indexing a repository (cloning, documenting every file with an LLM, embedding) can take anywhere from seconds to several minutes depending on repo size. Rather than block an HTTP request for that whole duration, `POST /index` enqueues a job and returns immediately; a small pool of async workers processes jobs from a SQLite-backed queue, and the frontend polls for progress. This also means indexing survives a backend restart — any job left `running` when the process dies is automatically reset to `queued` on the next startup.

## Getting started

You'll need both services running. Start the backend first, since the frontend depends on it.

```bash
# 1. Backend
cd Crawlit-Backend
uv sync
# create .env — see Crawlit-Backend/README.md
uv run uvicorn backend.api:app --reload

# 2. Frontend (in a separate terminal)
cd "Crawlit Frontend/frontend"
npm install
# create .env.local — see frontend README
npm run dev
```

Then open `http://localhost:3000`, submit a public GitHub repository, and wait for indexing to complete.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, Mermaid |
| Backend | FastAPI, SQLite (`aiosqlite`), asyncio worker pool |
| LLM / RAG | LangChain (agent + retrieval), Ollama (`nomic-embed-text` embeddings), Pinecone (vector store), OpenAI-compatible chat model |
| Persistence | SQLite (jobs & repository state) |

## Repository layout

```
CrawlIt/
├── Crawlit-Backend/          # FastAPI service — pipeline, jobs, RAG agent
│   └── backend/
│       ├── api.py
│       ├── core.py
│       ├── clone.py
│       ├── doc_generator.py
│       ├── ingestion.py
│       ├── retrieve.py
│       ├── db/
│       └── workers/
└── Crawlit Frontend/
    └── frontend/               # Next.js app — indexing UI, diagram, chat
        ├── app/
        ├── components/
        └── lib/
```

## Current limitations

- Only public GitHub repositories are supported.
- Re-indexing a repository fully replaces its previous documentation and vectors rather than incrementally updating changed files.
However duplicate cloning is restricted from frontend.
- The chat agent call on the backend currently runs synchronously on the event loop, which can serialize concurrent `/answer` requests under load.