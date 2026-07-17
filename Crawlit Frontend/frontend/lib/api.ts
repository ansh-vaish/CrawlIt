function getBaseUrl() {
  return typeof window === "undefined"
    ? process.env.BACKEND_URL!
    : process.env.NEXT_PUBLIC_BACKEND_URL!;
}

export type RepositoryState = {
  owner: string;
  repo: string;
  indexed: boolean;
  job_id: string | null;
  status: string;
  last_indexed: string | null;
};

export type JobState = {
  job_id: string;
  owner: string;
  repo: string;
  status: string;
  current_stage: string;
  progress: number;
  error: string | null;
};

function buildUrl(path: string, params: Record<string, string>) {
  const url = new URL(path, getBaseUrl());

  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }

  return url.toString();
}

export async function getRepository(repoOwner: string, repoName: string) {
  const res = await fetch(`${getBaseUrl()}/repositories/${repoOwner}/${repoName}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to fetch repository state");
  }

  return (await res.json()) as RepositoryState;
}

export async function getJob(jobId: string) {
  const res = await fetch(`${getBaseUrl()}/jobs/${jobId}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to fetch job state");
  }

  return (await res.json()) as JobState;
}

export async function startIndexing(repoOwner: string, repoName: string) {
  const res = await fetch(`${getBaseUrl()}/index`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repoOwner,
      repoName,
    }),
  });

  if (!res.ok) {
    throw new Error("Failed to start repository indexing");
  }

  return (await res.json()) as JobState;
}

export async function askQuestion(
  repoOwner: string,
  repoName: string,
  query: string,
) {
  const res = await fetch(buildUrl("/answer", { repoOwner, repoName, query }));

  if (!res.ok) {
    throw new Error("Failed to fetch repository answer");
  }

  return res.json();
}

export async function getMermaid(repoOwner: string, repoName: string) {
  const res = await fetch(buildUrl("/mermaid", { repoOwner, repoName }));

  if (!res.ok) {
    throw new Error("Failed to fetch mermaid diagram");
  }

  return res.json();
}
