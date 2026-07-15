"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getJob } from "@/lib/api";

type RepositoryIndexingStatusProps = {
  repoOwner: string;
  repoName: string;
  jobId: string;
};

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

export default function RepositoryIndexingStatus({
  repoOwner,
  repoName,
  jobId,
}: RepositoryIndexingStatusProps) {
  const router = useRouter();
  const [message, setMessage] = useState("Preparing the repository...");
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: number | null = null;

    async function pollJob() {
      try {
        const job = await getJob(jobId);

        if (cancelled) {
          return;
        }

        setProgress(job.progress ?? 0);
        setMessage(
          `${job.current_stage || "Indexing"} for ${repoOwner}/${repoName}`,
        );

        if (job.status === "completed") {
          router.refresh();
          return;
        }

        if (terminalStatuses.has(job.status)) {
          setMessage(job.error || "Indexing stopped before completion.");
          return;
        }

        timeoutId = window.setTimeout(pollJob, 2000);
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Failed to load repository progress.",
          );
        }
      }
    }

    void pollJob();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [jobId, repoName, repoOwner, router]);

  return (
    <div
      className="flex items-center justify-center rounded-3xl border border-stone-200 bg-white p-8 shadow-sm min-h-128"
    >
      <div className="max-w-md text-center">
        <p className="text-xs font-medium uppercase tracking-[0.25em] text-stone-500">
          Indexing
        </p>
        <h2 className="mt-3 text-2xl font-semibold text-stone-900">
          {repoOwner}/{repoName}
        </h2>
        <p className="mt-3 text-sm text-stone-600">{message}</p>
        <div className="mt-6 h-2 overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full rounded-full bg-stone-900 transition-all"
            style={{ width: `${Math.max(5, Math.min(progress, 100))}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-stone-500">{progress}% complete</p>
      </div>
    </div>
  );
}
