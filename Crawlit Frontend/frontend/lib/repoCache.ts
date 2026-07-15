type RepoData = {
  indexed: boolean;
};

const repoCache = new Map<string, RepoData>();



export default repoCache;
