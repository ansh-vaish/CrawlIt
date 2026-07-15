# CrawlIt Frontend

Next.js UI for CrawlIt. Users enter a GitHub `owner/repo`, watch it get indexed, then browse a generated architecture diagram and chat with a RAG agent that answers questions about the codebase.

## Stack

- **Next.js 16** (App Router, React 19)
- **Tailwind CSS 4** with `@tailwindcss/typography` for Markdown rendering
- **Mermaid** for rendering the generated architecture diagram
- **react-markdown** + `remark-gfm` + `rehype-highlight` for chat message rendering (GFM tables/lists + syntax-highlighted code blocks)
- **better-sqlite3** for local repo-lookup caching (`lib/db.ts`)

## Pages & flow

- `app/page.tsx` — landing page where a user submits a repo to index.
- `app/[repoOwner]/[repoName]/page.tsx` — repo detail page (server component). It checks the backend for the repo's indexed state:
  - **Not indexed, no active job** — shows a message that indexing hasn't started.
  - **Indexing in progress** — renders `RepositoryIndexingStatus`, which polls job progress (`GET /jobs/{job_id}`) until completion.
  - **Indexed** — fetches the Mermaid diagram (`GET /mermaid`) and renders it alongside the `RepositoryAssistant` chat panel.

## Key components

| Component | Purpose |
|---|---|
| `RepositoryAssistant.tsx` | Chat UI — sends questions to `GET /answer`, renders Markdown responses, shows suggested starter questions |
| `RepositoryIndexingStatus.tsx` | Polls job status and progress while a repo is being indexed |
| `MermaidDiagram.tsx` / `MermaidModal.tsx` | Renders the architecture diagram returned by the backend, with an expandable modal view |
| `Navbar.jsx` | Top navigation |

## Backend contract (`lib/api.ts`)

All requests go to `NEXT_PUBLIC_BACKEND_URL`:

| Function | Backend route |
|---|---|
| `startIndexing(owner, repo)` | `POST /index` |
| `getRepository(owner, repo)` | `GET /repositories/{owner}/{repo}` |
| `getJob(jobId)` | `GET /jobs/{job_id}` |
| `askQuestion(owner, repo, query)` | `GET /answer` |
| `getMermaid(owner, repo)` | `GET /mermaid` |


## Requirements

- Node.js ≥ 20
- A running instance of the [CrawlIt backend](../Crawlit-Backend) (see its README for setup)

## Setup

```bash
cd "Crawlit Frontend/frontend"
npm install
```

Create a `.env.local`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Run the dev server:

```bash
npm run dev
```

The app runs on `http://localhost:3000` by default.

Other scripts:

```bash
npm run build   # production build
npm run start   # run the production build
npm run lint    # eslint
```

## Project layout

```
frontend/
├── app/
│   ├── page.tsx                          # Landing page
│   ├── layout.tsx                        # Root layout
│   ├── api/                               # Next.js API routes (local caching helpers)
│   └── [repoOwner]/[repoName]/
│       ├── layout.tsx
│       └── page.tsx                        # Repo detail: indexing status → diagram + chat
├── components/
│   ├── RepositoryAssistant.tsx              # Chat panel
│   ├── RepositoryIndexingStatus.tsx          # Job progress polling
│   ├── MermaidDiagram.tsx / MermaidModal.tsx  # Diagram rendering
│   └── Navbar.jsx
└── lib/
    ├── api.ts                                 # Backend API client
    ├── db.ts                                    # Local SQLite cache (better-sqlite3)
    ├── repoCache.ts
    └── validateRepository.ts                     # Repo URL/owner/name validation
```

## Notes

- The backend currently allows CORS only from `http://localhost:3000`; update `origins` in the backend's `api.py` if you deploy the frontend elsewhere.
- `owner`/`repo` route params are lowercased before use to match how the backend stores repository keys.