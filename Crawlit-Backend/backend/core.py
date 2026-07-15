import asyncio
import os
from pathlib import Path

from backend.clone import clone_repo
from backend.doc_generator import RepositoryContext
from backend.doc_generator import run_doc_generator
from backend.ingestion import ingestion_pipeline
from backend.retrieve import run_llm


def _generated_docs_dir(context: RepositoryContext) -> Path:
    if context.overview_file is not None:
        return context.overview_file.parent
    return context.summary_file.parent


async def process_repo(
    repoOwner: str,
    repoName: str,
    progress_callback=None,
    cancel_check=None,
):
    async def emit(stage: str, progress: int) -> None:
        if progress_callback is not None:
            await progress_callback(stage, progress)

    async def ensure_not_cancelled() -> None:
        if cancel_check is not None:
            await cancel_check()

    repo_url = f"https://github.com/{repoOwner}/{repoName}"

    await ensure_not_cancelled()
    await emit("Cloning", 5)
    await asyncio.to_thread(clone_repo, repo_url)

    await ensure_not_cancelled()
    await emit("Documentation", 30)
    await run_doc_generator(
        repoOwner,
        repoName,
        progress_callback=emit,
        cancel_check=ensure_not_cancelled,
    )

    await ensure_not_cancelled()
    await emit("Embedding", 80)
    await ingestion_pipeline(
        repoOwner,
        repoName,
        progress_callback=emit,
        cancel_check=ensure_not_cancelled,
    )

    await ensure_not_cancelled()
    await emit("Completed", 100)
    return {
        "success": True,
    }


async def answer_query(context: RepositoryContext, query: str):
    try:
        result = run_llm(query, context.owner, context.name)
        return {
            "success": True,
            "answer": result["answer"],
        }
    except Exception as e:
        print(f"Error answering query for repository {context.owner}/{context.name}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def get_mermaid_diagram(context: RepositoryContext):
    try:
        mermaid_diagram_path = _generated_docs_dir(context) / f"{context.owner}_{context.name}_mermaid_diagram.md"
        with open(mermaid_diagram_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "success": True,
            "mermaid_diagram": content,
        }
    except Exception as e:
        print(f"Error getting mermaid diagram for repository {context.owner}/{context.name}: {e}")
        return {
            "success": False,
            "error": str(e),
        }