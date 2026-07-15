import asyncio
import os
from typing import List
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from langchain_ollama import OllamaEmbeddings

from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from langchain_community.document_loaders import TextLoader
from backend.db.jobs import JobCancelledError

load_dotenv()
embeddings = OllamaEmbeddings(
    model="nomic-embed-text:v1.5"
)

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(os.environ["PINECONE_INDEX"])

vectorstore = PineconeVectorStore(
    index_name=os.environ.get("PINECONE_INDEX"),
    embedding=embeddings
)

def delete_namespace(namespace: str):
    try:
        index.delete(delete_all=True, namespace=namespace)
        print(f"Deleted namespace: {namespace}")
    except Exception as e:
        print(f"Failed to delete namespace: {e}")


async def index_documents(
    documents: List[Document],
    namespace: str,
    batch_size: int = 50,
    progress_callback=None,
    cancel_check=None,
):
    print(f"Indexing {len(documents)} documents in batches of {batch_size}...")

    batches = [
        documents[i:i + batch_size] 
        for i in range(0, len(documents), batch_size)
    ]

    print(f"Total batches to index: {len(batches)}")

    successful = 0

    for i, batch in enumerate(batches):
        try:
            if cancel_check is not None:
                await cancel_check()

            await asyncio.to_thread(
                vectorstore.add_documents,
                batch,
                namespace=namespace,
            )
            successful += 1
            print(f"Batch {i+1} indexed successfully.")
            if progress_callback is not None and batches:
                await progress_callback("Embedding", 80 + int(15 * successful / len(batches)))
        except JobCancelledError:
            raise
        except Exception as e:
            print(f"Error indexing batch {i+1}: {e}")

    print(f"{successful} out of {len(batches)} batches indexed successfully.")


async def ingestion_pipeline(owner: str, repo: str, progress_callback=None, cancel_check=None):
    namespace = f"{owner}-{repo}"
    
    # Delete existing vectors
    if cancel_check is not None:
        await cancel_check()

    await asyncio.to_thread(delete_namespace, namespace)
    print("Starting ingestion...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=4000,
        chunk_overlap=200,
    )
    file_path = os.path.join(os.getcwd(), f"backend\\generated_docs\\{owner}_{repo}.md")
    loader = TextLoader(file_path, encoding="utf-8")
    docs = loader.load()
    splitted_docs = text_splitter.split_documents(docs)


    for i, doc in enumerate(splitted_docs):
        doc.metadata.update({
            "repo": f"{owner}/{repo}",
            "owner": owner,
            "repo_name": repo,
            "chunk_index": i,
        })

    await index_documents(
        splitted_docs,
        f"{owner}-{repo}",
        batch_size=100,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    print("Ingestion completed.")


if __name__ == "__main__":
    asyncio.run(ingestion_pipeline("ansh-vaish", "Web-IDE"))