import db from "./db";

export function isIndexed(owner: string, repo: string) {
  return !!db
    .prepare("SELECT 1 FROM repos WHERE owner = ? AND repo = ?")
    .get(owner, repo);
}

export function saveRepo(owner: string, repo: string) {
  db.prepare(
    `
    INSERT OR REPLACE INTO repos
    (owner, repo, indexed, indexed_at)
    VALUES (?, ?, 1, datetime('now'))
  `,
  ).run(owner, repo);
}
