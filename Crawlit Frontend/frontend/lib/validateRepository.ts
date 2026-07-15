export default async function validateRepository(
  input: string,
): Promise<{ owner: string; repo: string }> {
  input = input.trim();

  if (!input) {
    throw new Error("Repository is required");
  }

  let owner: string;
  let repo: string;

  // owner/repo
  const shortMatch = input.match(/^([^/\s]+)\/([^/\s]+)$/);
  if (shortMatch) {
    owner = shortMatch[1];
    repo = shortMatch[2].replace(/\.git$/i, "");
  }
  // SSH URL
  else {
    const sshMatch = input.match(
      /^git@github\.com:([^/]+)\/([^/]+?)(?:\.git)?$/,
    );

    if (sshMatch) {
      owner = sshMatch[1];
      repo = sshMatch[2];
    } else {
      // GitHub URL
      const normalized = /^[a-z][a-z\d+.-]*:/i.test(input)
        ? input
        : `https://${input}`;

      let url: URL;

      try {
        url = new URL(normalized);
      } catch {
        throw new Error("Invalid repository");
      }

      const hostname = url.hostname.toLowerCase();

      if (hostname !== "github.com" && hostname !== "www.github.com") {
        throw new Error("Only GitHub repositories are supported");
      }

      const parts = url.pathname.replace(/^\/+|\/+$/g, "").split("/");

      if (parts.length !== 2) {
        throw new Error("Invalid GitHub repository URL");
      }

      owner = parts[0];
      repo = parts[1].replace(/\.git$/i, "");
    }
  }

  // Verify repository
  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}`,
    {
      headers: {
        Accept: "application/vnd.github+json",
      },
    },
  );

  if (response.status === 404 || !response.ok) {
    throw new Error("Either Repository does not exist or is private");
  }
  return { owner, repo };
}
