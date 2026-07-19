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

        if (cancelled) return;

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
    <div className="mx-auto flex min-h-168 max-w-2xl items-center justify-center">
      <div className="w-full rounded-3xl border-[3px] border-[#2B2118] bg-[#F6F0E8] p-8 shadow-[10px_10px_0px_#8B5E3C]">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#8B5E3C]">
          Indexing Repository
        </p>

        <h2 className="mt-3 text-4xl font-black text-[#2B2118]">
          {repoOwner}/{repoName}
        </h2>

        <div className="mt-8 text-center">
          <p className="text-xl leading-8 text-[#5B4636]">
            {message}
            <span> </span>
            <span className="inline-flex">
              <span className="animate-bounce [animation-delay:0ms]">.</span>
              <span className="animate-bounce [animation-delay:200ms]">.</span>
              <span className="animate-bounce [animation-delay:400ms]">.</span>
            </span>
          </p>
        </div>

        <div className="mt-10">
          <div className="mb-2 flex items-center justify-between text-sm font-medium text-[#5B4636]">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>

          <div className="h-3 overflow-hidden rounded-full border-2 border-[#2B2118] bg-[#EADFCF]">
            <div
              className="relative h-full bg-[#8B5E3C] transition-all duration-700"
              style={{
                width: `${Math.max(5, Math.min(progress, 100))}%`,
              }}
            >
              <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-linear-to-r from-transparent via-white/30 to-transparent" />
            </div>
          </div>
        </div>

        <div className="mt-8 rounded-2xl border-2 border-[#2B2118] bg-[#FBF7F1] p-6">
          <p className="text-base font-bold text-[#2B2118]">
            First-time indexing takes a while.
          </p>

          <p className="mt-4 text-sm leading-7 text-[#5B4636]">
            Grab a coffee ☕ or take a short walk. Initial indexing may take up
            to <span className="font-semibold text-[#2B2118]">20 minutes</span>,
            depending on the repository size.
          </p>

          <p className="mt-4 text-sm leading-7 text-[#5B4636]">
            In the meantime, you can explore one of our pre-indexed
            repositories.
          </p>

          <p className="mt-4 text-sm leading-7 text-[#5B4636]">
            Feel free to close this tab and come back later. Your indexing job
            will continue in the background.
          </p>
        </div>
      </div>
    </div>
  );
}
