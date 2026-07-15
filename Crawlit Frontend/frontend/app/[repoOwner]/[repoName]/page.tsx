import { redirect } from "next/navigation";

import Navbar from "@/components/Navbar";
import MermaidModal from "@/components/MermaidModal";
import RepositoryAssistant from "@/components/RepositoryAssistant";
import RepositoryIndexingStatus from "@/components/RepositoryIndexingStatus";

import { getMermaid, getRepository } from "@/lib/api";

type PageProps = {
  params: Promise<{
    repoOwner: string;
    repoName: string;
  }>;
  searchParams: Promise<{
    job_id?: string;
  }>;
};

type MermaidResponse = {
  success: boolean;
  mermaid_diagram?: string;
  error?: string;
};

export default async function Page({ params, searchParams }: PageProps) {
  let { repoOwner, repoName } = await params;
  const { job_id } = await searchParams;
  repoOwner = repoOwner.toLowerCase();
  repoName = repoName.toLowerCase();
  if (!repoOwner || !repoName) {
    redirect("/");
  }

  const repository = await getRepository(repoOwner, repoName).catch(() => null);
  if (!repository) {
    redirect("/");
  }

  if (!repository.indexed) {
    const activeJobId = repository.job_id ?? job_id;

    if (!activeJobId) {
      return (
        <>
          <Navbar />

          <main className="min-h-[calc(100vh-90px)] bg-stone-50">
            <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
              <div
                className="flex items-center justify-center rounded-3xl border border-stone-200 bg-white p-8 shadow-sm"
                style={{ minHeight: "32rem" }}
              >
                <div className="max-w-md text-center">
                  <p className="text-xs font-medium uppercase tracking-[0.25em] text-stone-500">
                    Indexing
                  </p>
                  <h2 className="mt-3 text-2xl font-semibold text-stone-900">
                    {repoOwner}/{repoName}
                  </h2>
                  <p className="mt-3 text-sm text-stone-600">
                    The backend has no active job for this repository yet.
                  </p>
                </div>
              </div>
            </div>
          </main>
        </>
      );
    }

    return (
      <>
        <Navbar />

        <main className="min-h-[calc(100vh-90px)] bg-stone-50">
          <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
            <RepositoryIndexingStatus
              jobId={activeJobId}
              repoOwner={repoOwner}
              repoName={repoName}
            />
          </div>
        </main>
      </>
    );
  }

  const graphData = (await getMermaid(
    repoOwner,
    repoName,
  )) as unknown as MermaidResponse;
  const graph =
    graphData?.mermaid_diagram ??
    "No mermaid diagram was returned by the backend.";
  const suggestions = [
    "Explain project architecture",
    "Summarize repository",
    "Authentication flow",
    "Routing",
  ];

  return (
    <>
      <Navbar />

      <main className="min-h-[calc(100vh-90px)] bg-stone-50">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.25em] text-stone-500">
              Repository
            </p>

            <h1 className="text-3xl font-bold text-stone-900">
              {repoOwner}/{repoName}
            </h1>

            <p className="text-sm text-stone-600">
              Interactive Mermaid diagram generated from the repository
              structure.
            </p>
          </div>

          <section className="overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-stone-200 px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-stone-900">
                  Repository Diagram
                </h2>

                <p className="text-sm text-stone-500">
                  Generated using Mermaid
                </p>
              </div>

              <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-700">
                Mermaid
              </span>
            </div>

            <div className="flex min-h-136 items-center justify-center p-4 sm:p-6">
              <div className="flex w-full items-center justify-center">
                <MermaidModal chart={graph} />
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-sm">
            <div className="border-b border-stone-200 px-6 py-4">
              <h2 className="text-lg font-semibold text-stone-900">
                CrawlIt AI
              </h2>

              <p className="mt-1 text-sm text-stone-500">
                Ask questions about this repository
              </p>
            </div>

            <div className="min-h-128">
              <RepositoryAssistant
                suggestions={suggestions}
                repoOwner={repoOwner}
                repoName={repoName}
              />
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
