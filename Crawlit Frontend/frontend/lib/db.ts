import Database from "better-sqlite3";
import path from "path";

const db = new Database(path.join(process.cwd(), "data", "crawlit.db"));

// Better concurrency
db.pragma("journal_mode = WAL");

// Create tables if they don't exist
db.exec(`
CREATE TABLE IF NOT EXISTS repos (
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT,
    PRIMARY KEY(owner, repo)
);
`);

export default db;
