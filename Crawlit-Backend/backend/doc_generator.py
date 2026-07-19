import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, List, Tuple
import fnmatch

from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from langchain_openai import ChatOpenAI
from backend.db.jobs import JobCancelledError

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("DO_MODEL"),
    api_key=os.getenv("DO_API_KEY"),
    base_url="https://inference.do-ai.run/v1",
)

# --- tunables -----------------------------------------------------------

CONCURRENCY_LIMIT = int(os.getenv("DOCGEN_CONCURRENCY", "12"))          # max concurrent LLM calls, globally
FILE_WORKERS = int(os.getenv("DOCGEN_FILE_WORKERS", str(CONCURRENCY_LIMIT)))  # files processed in parallel
CHUNK_SIZE = int(os.getenv("DOCGEN_CHUNK_SIZE", "7000"))
CHUNK_OVERLAP = int(os.getenv("DOCGEN_CHUNK_OVERLAP", "500"))
MAX_FILE_SIZE_BYTES = int(os.getenv("DOCGEN_MAX_FILE_SIZE", str(500_000)))
SPLIT_THRESHOLD_CHARS = int(os.getenv("DOCGEN_SPLIT_THRESHOLD", "20000"))  # files smaller than this are never split
LLM_TIMEOUT = float(os.getenv("DOCGEN_LLM_TIMEOUT", "120"))
LLM_MAX_RETRIES = int(os.getenv("DOCGEN_LLM_MAX_RETRIES", "3"))

# -------------------------------------------------------------------------

EXT_TO_LANG = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".java": Language.JAVA,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".cs": Language.CSHARP,
    ".php": Language.PHP,
    ".rb": Language.RUBY,
    ".kt": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".swift": Language.SWIFT,
    ".proto": Language.PROTO,
    ".html": Language.HTML,
    ".md": Language.MARKDOWN,
}

IGNORE_FILE_TYPES = {
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".ico", ".svg", ".webp", ".avif", ".heic",
    # audio/video
    ".mp3", ".wav", ".flac", ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".webm", ".ogg",
    # archives/fonts/binaries
    ".zip", ".tar", ".gz", ".rar", ".7z", ".xz", ".bz2",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".git", ".min.js", ".min.css", ".map", ".d.ts", ".lock", ".log", ".tmp", ".bak",
    ".claude", ".bin", ".exe", ".dll", ".so", ".dylib", ".o", ".obj", ".a", ".lib",
    ".pyc", ".pyo", ".class", ".jar", ".war", ".ear",
    ".github", ".gitlab", ".vscode", ".idea", ".DS_Store",
    # snapshot/fixture/data
    ".snap", ".golden", ".csv", ".tsv", ".parquet", ".db", ".sqlite", ".sqlite3",
    # mobile/compiled
    ".apk", ".aab", ".ipa", ".dex", ".pb", ".pbxproj", ".xcworkspacedata",
    # docs/generated
    ".pdf", ".pyc", ".egg-info",
}

SKIP_DIRS = {
    # VCS / editor / IDE
    ".git", ".vscode", ".idea", ".github", ".gitlab", ".vs",
    # JS/TS ecosystem
    "node_modules", "dist", "build", ".next", "coverage", "out",
    ".turbo", ".cache", ".yarn", ".pnpm-store", "bower_components",
    "storybook-static", ".storybook",
    # Python
    "__pycache__", "venv", ".venv", "env", ".tox", ".mypy_cache",
    ".pytest_cache", "*.egg-info", "site-packages",
    # Java/Kotlin/Android
    ".gradle", "gradle", "target", ".m2", "build", "bin",
    "app/build", ".idea", "captures",
    # Go
    "vendor", "bin", "pkg",
    # Rust
    "target",
    # Ruby
    ".bundle", "vendor/bundle",
    # PHP
    "vendor",
    # C/C++
    "cmake-build-debug", "cmake-build-release", "obj",
    # iOS/macOS
    "Pods", "DerivedData", ".build", "xcuserdata",
    # AI/ML noise
    ".ollama", ".claude", "checkpoints", "wandb", "mlruns",
    # generic noise
    "eslint", "prettier", "tests", "spec", "docs", "doc", "examples",
    "fixtures", "__tests__", "__mocks__", "__snapshots__", "test-utils",
    "scripts", "flow-typed", ".circleci", "benchmarks", "e2e",
    "cypress", "playwright-report", "public", "static", "assets",
    "locales", "i18n", "www", "logs", "tmp", "temp", "exmaple", "examples", "sample", "samples", "demo", "demos", "testdata","i18n", "localization", "translations", "translation", "lang", "langs", "language", "languages", "packages" , "package" , "asset" , "resources" , "resource" , "public" , "static" , "dist" , "build" , "out" , "bin" , "lib" , "libs" , "vendor" , "vendors" , "third_party" , "third-party" , "thirdparty" , "external", ".cache", ".tmp", ".temp", ".log", ".logs", ".bak", ".backup", ".backups", ".old", ".archive", ".archives", ".trash", ".recycle", ".recycled", ".deleted", ".removed", ".obsolete", ".deprecated","bin","config"
    # agent/AI pipelines
    ".agents" , ".claude", ".llm", ".openai", ".do", ".anthropic", ".cohere", ".replicate", ".vllm",".cursor" ,".codex"
}

SKIP_FILES = {
    # env/vcs
    ".env", ".env.example", ".env.local", ".gitignore", ".gitattributes", ".gitmodules",
    # JS/TS
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "package.json",
    "tsconfig.json", "tsconfig.base.json", "tsconfig.build.json",
    "next.config.js", "next.config.ts", "next.config.mjs",
    "tailwind.config.js", "tailwind.config.ts",
    "postcss.config.js", "babel.config.js", ".babelrc", ".babelrc.js",
    "webpack.config.js", "vite.config.js", "vite.config.ts",
    "rollup.config.js", "rollup.config.mjs",
    "jest.config.js", "jest.config.ts", "vitest.config.ts",
    ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintignore",
    ".prettierrc", ".prettierrc.json", ".prettierignore",
    ".flowconfig", ".watchmanconfig", ".npmignore", ".npmrc", ".yarnrc", ".yarnrc.yml",
    "lerna.json", "nx.json", "turbo.json",
    # Python
    "poetry.lock", "Pipfile.lock", "requirements.txt", "requirements-dev.txt",
    "Pipfile", "setup.cfg", "setup.py", "pyproject.toml", "tox.ini",
    "MANIFEST.in", "conftest.py",
    # Java/Kotlin/Android
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat",
    "AndroidManifest.xml", "proguard-rules.pro",
    # Go
    "go.sum", "go.mod",
    # Rust
    "Cargo.lock", "Cargo.toml",
    # Ruby
    "Gemfile.lock", "Gemfile", ".rspec",
    # PHP
    "composer.lock", "composer.json",
    # C/C++
    "CMakeLists.txt", "Makefile", "configure", "configure.ac",
    # containers/CI
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile", ".dockerignore",
    ".travis.yml", ".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile",
    "cloudbuild.yaml", ".pre-commit-config.yaml",
    # legal/meta/community
    "LICENSE", "LICENSE.md", "LICENSE.txt", "CHANGELOG.md", "CHANGES.md",
    "CODEOWNERS", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "SUPPORT.md", "GOVERNANCE.md", "NOTICE", "AUTHORS", "PATENTS", ".mailmap",
    # editor/tooling
    ".editorconfig", ".nvmrc", ".node-version", ".ruby-version", ".python-version",
    ".browserslistrc",
}

SKIP_DIR_PATTERNS = {
    "*.egg-info",
    "*-cache",
    "*_cache",
    ".terraform*",
    "*.dSYM",
    "__pycache__*",          # covers __pycache__-3.11 style variants some tools create
    ".venv*",
    "*.egg",
    "*.dist-info",
    "cmake-build-*",
    "*.xcarchive",
    "*.framework",
    ".gradle-*",
    "*-build",
    "build-*",
    ".nx",
    "*.snap-tests",
}

SKIP_FILE_PATTERNS = {
    "*.min.js",
    "*.min.css",
    "*-lock.json",
    "*.generated.*",
    "*.g.dart",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*.pb.go",
    "*.d.ts",
    "*.chunk.js",
    "*.bundle.js",
}

def _matches_any_pattern(name: str, patterns: set[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)

def should_skip_dir(dirname: str) -> bool:
    return dirname in SKIP_DIRS or _matches_any_pattern(dirname, SKIP_DIR_PATTERNS)

# --------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(slots=True)
class RepositoryContext:
    owner: str
    name: str
    repo_dir: Path
    summary_file: Path
    overview_file: Path | None = None


# --- prompts --------------------------------------------------------------
# Shared structure block, reused by both the single-pass and reduce prompts
# so it isn't duplicated (and re-sent to the API) twice per call site.

DOC_STRUCTURE = """# Overview
Purpose of the file and its role in the project.

    imports:
    exports:
    classes:
    functions:

## Responsibilities
Primary responsibilities of this file.

## Main Components
Important classes, functions, hooks, interfaces, or modules and what each does.

## Execution Flow
How the file works start to finish and how data flows through it.

## Dependencies
Important internal modules and external libraries and why they're used.

## Key Logic
Most important algorithms, business logic, or implementation details.

## Configuration
Env vars, config values, constants, or feature flags, if present.

## Error Handling
Validation, exception handling, logging, retries, or fallbacks, if any.

## Security Notes
Auth, input validation, sanitization, or security-sensitive operations. State "None" if none.

## Limitations
Assumptions, TODOs, edge cases, or potential improvements visible from the code.

## Summary
3-5 sentence summary of the file's purpose and how it interacts with the rest of the app."""

filesummaryPrompt = (
    "You are an expert software engineer and technical writer. Analyze the source "
    "code and produce concise Markdown documentation.\n\n"
    "Rules: only describe what's evident from the code; write \"Not found\" if "
    "something can't be determined; explain intent, don't restate the implementation; "
    "no metadata; output only valid Markdown.\n\n"
    "Structure:\n" + DOC_STRUCTURE + "\n\n"
    "Source code:\n```{language}\n{code}\n```"
)

# Map step: cheap per-chunk summary for large files.
chunkSummaryPrompt = (
    "You're analyzing one part of a larger source file split into sequential chunks. "
    "Summarize this chunk concisely: what it does, any classes/functions/exports "
    "defined, key logic, and notable dependencies. Don't speculate about code outside "
    "this chunk. Under 200 words, plain Markdown, no headers.\n\n"
    "```{language}\n{code}\n```"
)

# Reduce step: synthesize the chunk summaries into one unified doc.
combineSummaryPrompt = (
    "You are an expert software engineer and technical writer. Below are summaries "
    "of sequential parts of one large source file, in order. Synthesize them into a "
    "single unified doc for the whole file — merge overlapping details, remove "
    "duplication between parts, describe the file as a whole.\n\n"
    "Rules: only describe what's evident from the summaries; write \"Not found\" if "
    "something can't be determined; no metadata; output only valid Markdown.\n\n"
    "Structure:\n" + DOC_STRUCTURE + "\n\n"
    "Chunk summaries:\n{chunk_summaries}"
)

# Repository-level rollup, built from each file's short summary at the end of the run.
repoSummaryPrompt = (
    "You are an expert software architect. Below is a list of files in a repository "
    "with a short summary of each. Write a high-level repository overview in Markdown "
    "covering: overall purpose, likely tech stack, architecture/module breakdown, and "
    "any notable patterns or conventions you can infer. Only state what's supported by "
    "the summaries below; do not invent details. A few paragraphs plus a short bullet "
    "list of key modules is enough.\n\n"
    "Repository: {repo_owner}/{repo_name}\n\n"
    "Files:\n{file_summaries}"
)


def get_language(file_path: str) -> Language | None:
    return EXT_TO_LANG.get(Path(file_path).suffix.lower())


def get_splitter(file_path: str):
    language = get_language(file_path)

    if language:
        return RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )


def split_file(context: RepositoryContext, file_path: Path) -> list[Document]:
    code = file_path.read_text(encoding="utf-8")
    source = file_path.relative_to(context.repo_dir).as_posix()
    metadata = {
        "source": source,
        "language": Path(file_path).suffix.lower().lstrip(".").capitalize(),
        "file_name": Path(file_path).name,
    }

    # Small files: don't split at all, one LLM call handles the whole thing.
    if len(code) <= SPLIT_THRESHOLD_CHARS:
        return [Document(page_content=code, metadata=metadata)]

    splitter = get_splitter(str(file_path))
    return splitter.split_documents([Document(page_content=code, metadata=metadata)])


def should_skip_file(file_path: Path) -> bool:
    suffix = file_path.suffix.lower()
    name = file_path.name

    if suffix in IGNORE_FILE_TYPES:
        return True
    if name in SKIP_FILES:
        return True
    if _matches_any_pattern(name, SKIP_FILE_PATTERNS):
        return True
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return True
    except OSError:
        return True

    return False


def extract_summary_section(content: str) -> str:
    """Pull just the '## Summary' section out of a generated doc, for the
    repo-level rollup (much cheaper than feeding the whole doc back in)."""
    marker = "## Summary"
    idx = content.find(marker)
    if idx == -1:
        return content.strip()[:400]
    return content[idx + len(marker):].strip()


async def call_llm(prompt: str, semaphore: asyncio.Semaphore) -> str:
    """Invoke the LLM with a timeout and exponential-backoff retries. The
    semaphore is only held around the actual API call, not the backoff sleep,
    so a retrying request doesn't block others from using that slot."""
    last_error: Exception | None = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            async with semaphore:
                res = await asyncio.wait_for(llm.ainvoke(prompt), timeout=LLM_TIMEOUT)
            return res.content
        except Exception as e:
            last_error = e
            if attempt < LLM_MAX_RETRIES:
                wait = 2 ** (attempt - 1)  # 1s, 2s, 4s, ...
                print(f"LLM call failed (attempt {attempt}/{LLM_MAX_RETRIES}): {e}. Retrying in {wait}s")
                await asyncio.sleep(wait)

    raise last_error


async def get_file_summary_async(
    context: RepositoryContext,
    docs: List[Document],
    semaphore: asyncio.Semaphore,
) -> str:
    header = f'''
Metadata:
- repoOwner: {context.owner}
- repoName: {context.name}
- filePath: {docs[0].metadata["source"]}
- fileName: {docs[0].metadata["file_name"]}
- language: {docs[0].metadata["language"]}

'''

    if len(docs) == 1:
        content = await call_llm(
            filesummaryPrompt.format(language=docs[0].metadata["language"], code=docs[0].page_content),
            semaphore,
        )
    else:
        # Map: summarize every chunk concurrently (bounded by the shared semaphore).
        chunk_summaries = await asyncio.gather(*(
            call_llm(
                chunkSummaryPrompt.format(language=doc.metadata["language"], code=doc.page_content),
                semaphore,
            )
            for doc in docs
        ))

        combined = "\n\n".join(
            f"--- Part {i} of {len(docs)} ---\n{summary}"
            for i, summary in enumerate(chunk_summaries, start=1)
        )

        # Reduce: synthesize one unified doc from the chunk summaries.
        content = await call_llm(
            combineSummaryPrompt.format(chunk_summaries=combined), semaphore
        )

    return header + content + "\n\n"


def makeSummaryFile(context: RepositoryContext) -> Path:
    summary_dir = SCRIPT_DIR / "generated_docs"
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary_file = summary_dir / f"{context.owner}_{context.name}.md"

    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# Repository Documentation \n\n")

    return summary_file


def makeRepoOverviewFile(context: RepositoryContext) -> Path:
    summary_dir = SCRIPT_DIR / "generated_docs"
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary_overview_file = summary_dir / f"{context.owner}_{context.name}_overview.md"

    with open(summary_overview_file, "w", encoding="utf-8") as f:
        f.write("# Repository Overview \n\n")

    return summary_overview_file


async def worker(
    context: RepositoryContext,
    name: int,
    queue: "asyncio.Queue[Path | None]",
    write_lock: asyncio.Lock,
    semaphore: asyncio.Semaphore,
    file_summaries: List[Tuple[str, str]],
    cancel_check: Callable[[], Awaitable[None]] | None = None,
):
    while True:
        file_path = await queue.get()
        if file_path is None:
            queue.task_done()
            break
        try:
            if cancel_check is not None:
                await cancel_check()
            split_docs = split_file(context, file_path)
            full_summary = await get_file_summary_async(context, split_docs, semaphore)

            # Write incrementally as each file finishes, instead of holding
            # everything in memory until the whole repo is done.
            async with write_lock:
                with context.summary_file.open("a", encoding="utf-8") as f:
                    f.write(full_summary)

            # Stash the short summary for the repo-level rollup at the end.
            source = split_docs[0].metadata["source"]
            file_summaries.append((source, extract_summary_section(full_summary)))

            print(f"[worker {name}] Processed: {file_path}")
        except JobCancelledError:
            raise
        except Exception as e:
            print(f"[worker {name}] Skipping {file_path}: {e}")
        finally:
            queue.task_done()


async def generate_mermaid_diagram(
    context: RepositoryContext,
    overview_file: Path,
    cancel_check: Callable[[], Awaitable[None]] | None = None,
) -> Path:
    """Generate a Mermaid architecture diagram from the repository overview."""

    if cancel_check is not None:
        await cancel_check()

    overview = overview_file.read_text(encoding="utf-8")

    prompt = f"""
You are a senior software architect specializing in system architecture diagrams.

Analyze the repository overview and infer the high-level architecture of the project.

Generate a Mermaid diagram that communicates how the system is organized, not how the files are arranged.

Requirements:
- Output ONLY valid Mermaid syntax.
- Use `flowchart TD`.
- Produce an architecture diagram, not a directory tree.
- Group related files into logical components (e.g. Frontend, Backend API, Workers, Database, Queue, Authentication, AI Pipeline, Cache, External Services).
- Show the primary flow of data and requests between components using directed edges.
- Include only major architectural components (10-25 nodes).
- Omit implementation details, helper modules, utility files, constants, configuration files, tests, and internal functions.
- Infer architectural layers when possible (Presentation → API → Business Logic → Data Layer → External Services).
- If queues, workers, databases, caches, vector stores, LLMs, or external APIs exist, represent them as separate components.
- Prefer meaningful component names over folder names.
- Avoid duplicate or redundant nodes.
- Keep the layout clean and easy to read.
- Ensure the Mermaid syntax is valid.
- Do NOT include explanations, comments, markdown, or code fences.

Repository Overview:
--------------------
{overview}
"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])

    mermaid = response.content.strip()

    # Remove accidental markdown fences if present
    if mermaid.startswith("```"):
        mermaid = mermaid.removeprefix("```mermaid").removeprefix("```")
        mermaid = mermaid.removesuffix("```").strip()

    output_path = overview_file.parent / f"{context.owner}_{context.name}_mermaid_diagram.md"
    output_path.write_text(mermaid, encoding="utf-8")

    return output_path


async def generate_repo_overview(
    context: RepositoryContext,
    semaphore: asyncio.Semaphore,
    file_summaries: List[Tuple[str, str]],
    progress_callback: Callable[[str, int], Awaitable[None]] | None = None,
    cancel_check: Callable[[], Awaitable[None]] | None = None,
):
    if not file_summaries:
        return

    if cancel_check is not None:
        await cancel_check()

    file_summaries.sort(key=lambda t: t[0])  # deterministic order
    listing = "\n\n".join(f"### {path}\n{summary}" for path, summary in file_summaries)

    repo_summary = await call_llm(
        repoSummaryPrompt.format(repo_owner=context.owner, repo_name=context.name, file_summaries=listing),
        semaphore,
    )

    context.overview_file = makeRepoOverviewFile(context)
    with context.overview_file.open("w", encoding="utf-8") as f:
        f.write(repo_summary.strip() + "\n")

    if progress_callback is not None:
        await progress_callback("Mermaid", 60)

    await generate_mermaid_diagram(context, context.overview_file, cancel_check=cancel_check)
    existing = context.summary_file.read_text(encoding="utf-8")
    with context.summary_file.open("w", encoding="utf-8") as f:
        f.write("# Repository Summary\n\n")
        f.write(repo_summary.strip() + "\n\n---\n\n")
        f.write(existing)

    print("Repository-level summary generated and prepended.")


async def walk_directory_async(
    context: RepositoryContext,
    progress_callback: Callable[[str, int], Awaitable[None]] | None = None,
    cancel_check: Callable[[], Awaitable[None]] | None = None,
):
    context.summary_file = makeSummaryFile(context)

    queue: "asyncio.Queue[Path | None]" = asyncio.Queue()
    file_count = 0

    for root, dirs, files in os.walk(context.repo_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]

        for file in files:
            file_path = Path(root) / file
            if should_skip_file(file_path):
                continue
            queue.put_nowait(file_path)
            file_count += 1

    print(f"Found {file_count} files to process (file_workers={FILE_WORKERS}, llm_concurrency={CONCURRENCY_LIMIT})")

    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)  # global cap on concurrent LLM calls
    file_summaries: List[Tuple[str, str]] = []

    workers = [
        asyncio.create_task(worker(context, i, queue, write_lock, semaphore, file_summaries, cancel_check))
        for i in range(FILE_WORKERS)
    ]

    await queue.join()  # wait until every file has been processed

    # signal workers to stop
    for _ in workers:
        queue.put_nowait(None)
    await asyncio.gather(*workers)

    await generate_repo_overview(
        context,
        semaphore,
        file_summaries,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


async def run_doc_generator(
    owner: str,
    name: str,
    progress_callback: Callable[[str, int], Awaitable[None]] | None = None,
    cancel_check: Callable[[], Awaitable[None]] | None = None,
):
    context = RepositoryContext(
        owner=owner,
        name=name,
        repo_dir=SCRIPT_DIR / "repos" / owner / name,
        summary_file=SCRIPT_DIR / "generated_docs" / f"{owner}_{name}.md",
    )
    await walk_directory_async(
        context,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


if __name__ == "__main__":
    asyncio.run(run_doc_generator("ansh-vaish", "KeyNinja"))
