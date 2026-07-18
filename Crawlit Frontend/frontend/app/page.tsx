"use client";

import { type FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { GitHub } from "@deemlol/next-icons";
import validateRepository from "@/lib/validateRepository";
import Navbar from "@/components/Navbar";
import { getRepository, startIndexing } from "@/lib/api";
import { toast } from "sonner";

const loadingStages = [
  "Validating repository URL",
  "Repository is Queued for processing",
  "Ingestion pipeline is running",
  "Processing Completed",
];

export default function HomePage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [isCloning, setIsCloning] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusType, setStatusType] = useState<"idle" | "success" | "error">(
    "idle",
  );
  const [loadingStageIndex, setLoadingStageIndex] = useState(0);
  const loadingIntervalRef = useRef<number | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (loadingIntervalRef.current) {
      window.clearInterval(loadingIntervalRef.current);
      loadingIntervalRef.current = null;
    }

    if (!repoUrl.trim()) {
      setStatusType("error");
      setStatusMessage("Enter a repository link to clone.");
      return;
    }

    setIsCloning(true);
    setStatusType("idle");
    setStatusMessage("");
    setLoadingStageIndex(0);
    try {
      let { owner, repo } = await validateRepository(repoUrl);
      owner = owner.toLowerCase();
      repo = repo.toLowerCase();
      const repositoryKey = `${owner}/${repo}`;

      const repository = await getRepository(owner, repo).catch(async () => {
        const job = await startIndexing(owner, repo);
        return {
          indexed: false,
          job_id: job.job_id,
        };
      });

      if (repository.indexed) {
        setStatusType("success");
        setStatusMessage(`Repository ${repositoryKey} is already indexed.`);
        await fetch("/api/repository", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            owner,
            repo,
          }),
        });
        router.push(`/${owner}/${repo}`);
        return;
      }

      const jobId = repository.job_id;

      if (!jobId) {
        throw new Error(
          "Repository is not indexed yet and no job is available to resume.",
        );
      }

      setStatusMessage(
        `Indexing ${repositoryKey}. Resuming the existing backend job.`,
      );

      setLoadingStageIndex(1);

      toast.info(`Resuming ${repositoryKey}...`);

      setStatusType("success");
      setStatusMessage(`Indexing ${repositoryKey} is already in progress.`);
      router.push(`/${owner}/${repo}?job_id=${jobId}`);
    } catch (error) {
      setStatusType("error");
      setStatusMessage(
        error instanceof Error ? error.message : "Failed to clone repository.",
      );
    } finally {
      if (loadingIntervalRef.current) {
        window.clearInterval(loadingIntervalRef.current);
        loadingIntervalRef.current = null;
      }
      setIsCloning(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#F6F0E8] text-[#2B2118]">
      {/* Navbar */}
      <Navbar />
      {/* Hero */}
      <section className="mx-auto flex max-w-7xl flex-col items-center px-6 py-auto text-center">
        <h1 className="max-w-4xl text-7xl font-black leading-none tracking-tighter">
          Chat with any
          <br />
          GitHub repository
        </h1>
        <p className="mt-5 max-w-2xl text-xl leading-8 text-[#6D5B4D]">
          Generate documentation, understand architecture, visualize the
          repository and ask questions about any public GitHub project.
        </p>

        {/* Card */}
        <form onSubmit={handleSubmit} className="mt-8 w-full max-w-5xl">
          <div className="relative">
            {/* shadow */}
            <div className="absolute left-3 top-3 h-full w-full rounded-lg border-2 border-[#2B2118] bg-[#5B4636]" />

            {/* main card */}
            <div className="relative rounded-lg border-2 border-[#2B2118] bg-[#EFE3D2] p-8">
              {/* Search */}
              <div className="flex gap-4">
                <div className="flex flex-1 items-center border-2 border-[#2B2118] bg-white px-5">
                  <GitHub size={22} className="mr-4 text-[#6D5B4D]" />

                  <input
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="owner/repository or GitHub URL"
                    className="h-16 w-full bg-transparent text-lg outline-none placeholder:text-[#8B8177]"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isCloning}
                  className="flex h-16 items-center justify-center border-2 border-[#2B2118] bg-[#8B5E3C] px-10 text-lg font-bold text-white transition hover:bg-[#6F4A30] disabled:opacity-60"
                >
                  {isCloning ? (
                    <span className="flex items-center gap-3">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      {loadingStages[loadingStageIndex]}
                    </span>
                  ) : (
                    "Analyze"
                  )}
                </button>
              </div>

              <p className="mt-4 text-left text-sm text-[#6D5B4D]">
                First-time indexing may take up to 20 minutes. After the first
                run, responses are much faster.
              </p>

              {/* Examples */}

              <div className="mt-8 text-left">
                <p className="mb-4 text-lg font-semibold">
                  Try these repositories
                </p>

                <div className="flex flex-wrap gap-3">
                  {[
                    "vercel/next.js",
                    "fastapi/fastapi",
                    "langchain-ai/langgraph",
                    "expressjs/express",
                    "axios/axios",
                  ].map((repo) => (
                    <button
                      key={repo}
                      type="button"
                      onClick={() => setRepoUrl(repo)}
                      className="border-2 border-[#2B2118] bg-[#D9C2A5] px-5 py-2 font-medium transition hover:bg-[#CFAE87]"
                    >
                      {repo}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status */}

              <div className="mt-8 border-2 border-[#2B2118] bg-white px-5 py-4 text-left">
                <p
                  className={`font-medium ${
                    statusType === "error"
                      ? "text-red-700"
                      : statusType === "success"
                        ? "text-green-700"
                        : "text-[#6D5B4D]"
                  }`}
                >
                  {statusMessage ||
                    "Paste any GitHub repository to generate architecture, documentation and an interactive knowledge base."}
                </p>
                {isCloning ? (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-3 text-sm text-[#6D5B4D]">
                      <span className="h-2.5 w-2.5 rounded-full bg-[#8B5E3C] animate-pulse" />
                      <span>{loadingStages[loadingStageIndex]}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#EFE3D2]">
                      <div className="h-full w-2/5 animate-pulse rounded-full bg-[#8B5E3C]" />
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </form>
      </section>
    </main>
  );
}
