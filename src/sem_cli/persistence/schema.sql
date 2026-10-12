-- SEM-CLI SQLite Schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_url TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    repository_id INTEGER NOT NULL,
    requested_ref TEXT,
    commit_sha TEXT,
    status TEXT NOT NULL, -- queued, running, completed, partial, failed
    profile TEXT NOT NULL, -- quick, full
    started_at TEXT NOT NULL,
    completed_at TEXT,
    tool_version TEXT NOT NULL,
    error_code TEXT,
    error_summary TEXT,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_repository
    ON analysis_runs(repository_id, started_at);

CREATE INDEX IF NOT EXISTS idx_runs_commit
    ON analysis_runs(repository_id, commit_sha);

CREATE TABLE IF NOT EXISTS metric_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    status TEXT NOT NULL,
    analyzer TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    explanation TEXT,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_metrics_run_name
    ON metric_values(run_id, name);

CREATE INDEX IF NOT EXISTS idx_metrics_scope
    ON metric_values(run_id, scope_type, scope_key);

CREATE TABLE IF NOT EXISTS commits (
    repository_id INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    author_identity TEXT,
    author_timestamp TEXT,
    committer_timestamp TEXT,
    subject TEXT,
    PRIMARY KEY (repository_id, commit_sha),
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS commit_changes (
    repository_id INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    file_path TEXT NOT NULL,
    change_type TEXT,
    lines_added INTEGER,
    lines_deleted INTEGER,
    PRIMARY KEY (repository_id, commit_sha, file_path),
    FOREIGN KEY (repository_id, commit_sha)
        REFERENCES commits(repository_id, commit_sha) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT,
    message TEXT NOT NULL,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    evidence TEXT,
    tool_name TEXT NOT NULL,
    tool_version TEXT,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_findings_run_severity
    ON findings(run_id, severity);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    version_spec TEXT NOT NULL,
    ecosystem TEXT NOT NULL,
    manifest_file TEXT NOT NULL,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    summary_type TEXT NOT NULL, -- statistical, ai_engineering, ai_business, risk
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    report_format TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
