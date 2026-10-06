import json
import sqlite3

import pytest

from personal_ai_brain.tautulli_reconciliation import (
    CursorNotInitialized,
    ReconciliationError,
    SourceEvent,
    reconcile_tautulli,
    resolve_tmdb_identity,
)
from personal_ai_brain.watched_ledger import apply_migrations


class FakeSource:
    def __init__(self, events=()):
        self.events = list(events)
        self.read_positions = []

    def read_after(self, position, *, limit):
        self.read_positions.append(position)
        return [event for event in self.events if event.position > position][:limit]


def event(position, *, kind="episode", tmdb=None, watched_at=None):
    tmdb = tmdb if tmdb is not None else 7000 + position
    return SourceEvent(
        position,
        {
            "history_id": str(position),
            "watched_at": watched_at or f"2026-10-06T12:{position:02d}:00Z",
            "media_type": kind,
            "rating_key": str(400 + position),
            "guid": f"plex://{kind}/{position}",
            "guids": [f"tmdb://{tmdb}", f"imdb://tt{tmdb:07d}"],
        },
    )


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    apply_migrations(connection)
    return connection


def cursor(db):
    row = db.execute(
        "SELECT cursor_or_watermark FROM source_cursors WHERE source='plex' AND account_scope='igor'"
    ).fetchone()
    return None if row is None else json.loads(row[0])["value"]


def test_empty_first_run_records_explicit_start(db):
    result = reconcile_tautulli(
        db, FakeSource(), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert result.processed_count == 0
    assert cursor(db) == 0


def test_first_run_without_boundary_fails_closed(db):
    with pytest.raises(CursorNotInitialized):
        reconcile_tautulli(db, FakeSource(), resolve_tmdb_identity, account_scope="igor")
    assert cursor(db) is None


def test_one_new_episode(db):
    result = reconcile_tautulli(
        db, FakeSource([event(1)]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert (result.created_count, cursor(db)) == (1, 1)
    assert db.execute("SELECT media_kind FROM watch_events").fetchone()[0] == "episode"


def test_multiple_ordered_events(db):
    result = reconcile_tautulli(
        db, FakeSource([event(2), event(1), event(3)]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert (result.processed_count, result.created_count, cursor(db)) == (3, 3, 3)


def test_movie_and_episode_batch(db):
    result = reconcile_tautulli(
        db, FakeSource([event(1, kind="movie"), event(2)]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert result.created_count == 2
    assert db.execute("SELECT media_kind FROM watch_events ORDER BY id").fetchall() == [
        ("movie",), ("episode",)
    ]


def test_duplicate_already_in_ledger_is_noop(db):
    source = FakeSource([event(1)])
    reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    db.execute("DELETE FROM source_cursors")
    result = reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert result.duplicate_count == 1
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1


def test_cursor_overlap_is_harmless(db):
    source = FakeSource([event(1)])
    reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0, overlap=1,
    )
    source.events.append(event(2))
    result = reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", overlap=1,
    )
    assert (result.duplicate_count, result.created_count, cursor(db)) == (1, 1, 2)
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 2


def test_cursor_overlap_never_backfills_unseen_history(db):
    accepted = event(38, tmdb=7045607)
    reconcile_tautulli(
        db, FakeSource([accepted]), resolve_tmdb_identity,
        account_scope="bootstrap", initial_watermark=37, overlap=0,
    )
    result = reconcile_tautulli(
        db, FakeSource([event(37), accepted]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=38, overlap=2,
    )
    assert result.duplicate_count == 1
    assert db.execute("SELECT source_event_id FROM watch_events").fetchall() == [("38",)]
    row = db.execute(
        "SELECT cursor_or_watermark FROM source_cursors WHERE source='plex' AND account_scope='igor'"
    ).fetchone()
    assert json.loads(row[0])["value"] == 38


def test_unknown_identity_is_quarantined_and_later_event_continues(db):
    unknown = SourceEvent(
        1,
        {
            "history_id": "1", "watched_at": "2026-10-06T12:01:00Z",
            "media_type": "episode", "rating_key": "401",
            "guid": "plex://episode/unknown", "guids": [],
        },
    )
    result = reconcile_tautulli(
        db, FakeSource([unknown, event(2)]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert (result.quarantined_count, result.created_count, cursor(db)) == (1, 1, 2)
    assert db.execute("SELECT count(*) FROM sync_deliveries").fetchone()[0] == 0


def test_partial_batch_failure_stops_before_later_event(db):
    malformed = SourceEvent(2, {"history_id": "2", "media_type": "episode"})
    result = reconcile_tautulli(
        db, FakeSource([event(1), malformed, event(3)]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    assert result.failed_position == 2
    assert (result.processed_count, cursor(db)) == (1, 1)
    assert db.execute("SELECT source_event_id FROM watch_events").fetchall() == [("1",)]


def test_source_read_failure_preserves_cursor(db):
    class BrokenSource:
        def read_after(self, position, *, limit):
            raise OSError("source unavailable")

    with pytest.raises(ReconciliationError):
        reconcile_tautulli(
            db, BrokenSource(), resolve_tmdb_identity,
            account_scope="igor", initial_watermark=38,
        )
    assert cursor(db) == 38
    assert db.execute(
        "SELECT last_error_at FROM source_cursors WHERE source='plex' AND account_scope='igor'"
    ).fetchone()[0] is not None


def test_restart_after_insert_before_cursor_deduplicates(db):
    source = FakeSource([event(1)])

    def crash_after_ingest(_event, _result):
        raise RuntimeError("simulated restart")

    first = reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0, after_ingest=crash_after_ingest,
    )
    assert first.failed_position == 1
    assert cursor(db) == 0
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1

    second = reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor",
    )
    assert (second.duplicate_count, cursor(db)) == (1, 1)
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1


def test_restart_after_cursor_advance_is_idempotent(db):
    source = FakeSource([event(1)])
    reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", initial_watermark=0,
    )
    result = reconcile_tautulli(
        db, source, resolve_tmdb_identity,
        account_scope="igor", overlap=0,
    )
    assert result.processed_count == 0
    assert cursor(db) == 1
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1


def test_accepted_s09e06_replay_creates_no_duplicate(db):
    accepted = event(
        38,
        tmdb=7045607,
        watched_at="2026-10-06T13:20:09Z",
    )
    first = reconcile_tautulli(
        db, FakeSource([accepted]), resolve_tmdb_identity,
        account_scope="igor", initial_watermark=37, overlap=1,
    )
    second = reconcile_tautulli(
        db, FakeSource([accepted]), resolve_tmdb_identity,
        account_scope="igor", overlap=1,
    )
    assert first.created_count == 1
    assert second.duplicate_count == 1
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM sync_deliveries").fetchone()[0] == 0
