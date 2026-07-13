-- SQLite schema for the LinkedIn Easy Apply Automaton.
-- Applied idempotently on startup via Database.initialize().

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT NOT NULL,                 -- apply | scan | dry_run
    searches      TEXT,                          -- JSON list of search names
    status        TEXT NOT NULL DEFAULT 'running', -- running | completed | failed
    jobs_scanned  INTEGER NOT NULL DEFAULT 0,
    jobs_applied  INTEGER NOT NULL DEFAULT 0,
    jobs_skipped  INTEGER NOT NULL DEFAULT 0,
    jobs_failed   INTEGER NOT NULL DEFAULT 0,
    notes         TEXT,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT NOT NULL UNIQUE,
    external_id      TEXT,
    title            TEXT,
    company          TEXT,
    location         TEXT,
    workplace_type   TEXT,                        -- remote | hybrid | on-site
    employment_type  TEXT,                        -- full-time | contract | ...
    experience_level TEXT,
    applicants       INTEGER,
    posting_age      TEXT,
    salary           TEXT,
    description      TEXT,
    recruiter        TEXT,
    easy_apply       INTEGER NOT NULL DEFAULT 0,  -- boolean
    already_applied  INTEGER NOT NULL DEFAULT 0,  -- boolean (per LinkedIn UI)
    search_name      TEXT,
    discovered_run   INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    discovered_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_easy_apply ON jobs(easy_apply);

CREATE TABLE IF NOT EXISTS scores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    score      INTEGER NOT NULL,
    threshold  INTEGER NOT NULL,
    passed     INTEGER NOT NULL DEFAULT 0,   -- boolean
    breakdown  TEXT,                         -- JSON of matched keyword -> weight
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scores_job ON scores(job_id);

CREATE TABLE IF NOT EXISTS resumes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    path       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id       INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    resume_id    INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
    status       TEXT NOT NULL DEFAULT 'pending', -- pending|submitted|skipped|failed|dry_run
    reason       TEXT,
    steps        INTEGER NOT NULL DEFAULT 0,
    screenshot   TEXT,
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT,
    UNIQUE(job_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_started ON applications(started_at);

CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    normalized  TEXT NOT NULL UNIQUE,
    category    TEXT,
    skill       TEXT,
    answer_type TEXT,
    seen_count  INTEGER NOT NULL DEFAULT 1,
    first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS answers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
    value       TEXT,
    source      TEXT NOT NULL DEFAULT 'manual', -- yaml|manual|ai|default
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-application record of what was actually asked and answered.
CREATE TABLE IF NOT EXISTS application_answers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    question_id    INTEGER REFERENCES questions(id) ON DELETE SET NULL,
    question_text  TEXT,
    value          TEXT,
    source         TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    match_percent  REAL,
    missing_skills TEXT,           -- JSON list
    recommendation TEXT,
    reasons        TEXT,           -- JSON list
    suggested_resume TEXT,
    should_apply   INTEGER,        -- boolean
    raw            TEXT,           -- raw provider payload
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ai_job ON ai_results(job_id);

CREATE TABLE IF NOT EXISTS errors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    job_id     INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    context    TEXT,
    message    TEXT,
    traceback  TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
