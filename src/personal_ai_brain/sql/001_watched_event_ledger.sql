PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS watch_events (
    id INTEGER PRIMARY KEY,
    local_media_id INTEGER,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('movie', 'episode')),
    event_type TEXT NOT NULL DEFAULT 'watch' CHECK (event_type = 'watch'),
    watched_at TEXT NOT NULL,
    watched_date_precision TEXT NOT NULL
        CHECK (watched_date_precision IN ('exact', 'date_only', 'legacy_placeholder')),
    source TEXT NOT NULL CHECK (source IN ('plex', 'trakt', 'manual', 'agent', 'migration')),
    provenance TEXT NOT NULL,
    source_event_id TEXT,
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    imported_at TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL UNIQUE,
    superseded_by INTEGER REFERENCES watch_events(id),
    quarantine_reason TEXT,
    created_at TEXT NOT NULL,
    CHECK (
        (local_media_id IS NOT NULL AND quarantine_reason IS NULL) OR
        (local_media_id IS NULL AND quarantine_reason IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS watch_events_source_event
    ON watch_events(source, source_event_id)
    WHERE source_event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS external_event_links (
    id INTEGER PRIMARY KEY,
    watch_event_id INTEGER NOT NULL REFERENCES watch_events(id),
    system TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    external_media_id TEXT,
    linked_at TEXT NOT NULL,
    UNIQUE(system, external_event_id)
);

CREATE TABLE IF NOT EXISTS sync_deliveries (
    id INTEGER PRIMARY KEY,
    watch_event_id INTEGER NOT NULL REFERENCES watch_events(id),
    target TEXT NOT NULL,
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('pending', 'in_flight', 'verified', 'retry_wait', 'ambiguous', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TEXT,
    last_http_status INTEGER,
    last_error_class TEXT,
    target_event_id TEXT,
    started_at TEXT,
    verified_at TEXT,
    UNIQUE(target, idempotency_key)
);

CREATE TABLE IF NOT EXISTS source_cursors (
    source TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    cursor_or_watermark TEXT NOT NULL,
    last_success_at TEXT,
    last_error_at TEXT,
    PRIMARY KEY(source, account_scope)
);
