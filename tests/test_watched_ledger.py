from datetime import datetime, timezone
import json
import sqlite3

import pytest

from personal_ai_brain.watched_ledger import (
    DuplicateIdempotencyKey,
    LedgerError,
    Observation,
    apply_migrations,
    create_delivery,
    ingest_observation,
    link_external_event,
    record_delivery_failure,
    recover_restart_work,
    set_migration_boundary,
    transition_delivery,
)


WATCHED_AT = "2026-10-06T18:00:00Z"


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys=ON")
    apply_migrations(connection)
    yield connection
    connection.close()


def observation(**changes):
    values = dict(
        media_kind="movie",
        local_media_id=1,
        watched_at=WATCHED_AT,
        watched_date_precision="exact",
        source="plex",
        provenance={"adapter": "test"},
        source_event_id="plex-event-1",
        confidence="high",
        external_media_id="tmdb://1",
    )
    values.update(changes)
    return Observation(**values)


def test_additive_migration_preserves_existing_personal_state():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE movies(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
        CREATE TABLE user_movies(movie_id INTEGER PRIMARY KEY, watched INTEGER, my_rating INTEGER);
        CREATE TABLE external_ids(movie_id INTEGER, source TEXT, external_id TEXT);
        INSERT INTO movies VALUES (1, 'Existing movie');
        INSERT INTO user_movies VALUES (1, 1, 9);
        INSERT INTO external_ids VALUES (1, 'csfd', '123');
        """
    )
    before = {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in ("movies", "user_movies", "external_ids")
    }
    apply_migrations(connection)
    after = {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in ("movies", "user_movies", "external_ids")
    }
    assert after == before
    assert connection.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM source_cursors").fetchone()[0] == 0


def test_first_movie_watch_creates_event(db):
    result = ingest_observation(db, observation())
    assert result.status == "created"
    assert result.outbound_allowed is True
    row = db.execute("SELECT media_kind, event_type, source FROM watch_events").fetchone()
    assert row == ("movie", "watch", "plex")


def test_genuine_rewatch_is_a_second_event(db):
    first = ingest_observation(db, observation())
    second = ingest_observation(
        db,
        observation(watched_at="2026-10-07T18:00:00Z", source_event_id="plex-event-2"),
    )
    assert first.watch_event_id != second.watch_event_id
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 2


def test_duplicate_plex_webhook_is_deduplicated_by_source_event(db):
    first = ingest_observation(db, observation())
    duplicate = ingest_observation(db, observation(provenance={"adapter": "redelivery"}))
    assert duplicate.status == "duplicate_source_event"
    assert duplicate.watch_event_id == first.watch_event_id
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1


def test_webhook_and_reconciliation_share_exact_fingerprint(db):
    first = ingest_observation(db, observation(source_event_id=None, provenance={"via": "webhook"}))
    duplicate = ingest_observation(
        db, observation(source_event_id="reconciliation-1", provenance={"via": "reconciliation"})
    )
    assert duplicate.status == "duplicate_fingerprint"
    assert duplicate.watch_event_id == first.watch_event_id
    assert db.execute("SELECT count(*) FROM external_event_links").fetchone()[0] == 1


def test_same_timestamp_from_different_sources_is_not_auto_merged(db):
    ingest_observation(db, observation(source_event_id="plex-1"))
    ingest_observation(
        db,
        observation(source="manual", source_event_id="manual-1", provenance={"entered_by": "owner"}),
    )
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 2


def test_episode_identity_is_preserved(db):
    result = ingest_observation(
        db, observation(media_kind="episode", local_media_id=41, source_event_id="episode-event")
    )
    assert result.status == "created"
    assert db.execute("SELECT media_kind, local_media_id FROM watch_events").fetchone() == ("episode", 41)


def test_unknown_identity_is_quarantined_and_cannot_create_delivery(db):
    result = ingest_observation(
        db,
        observation(
            local_media_id=None,
            source_event_id="unknown-1",
            confidence="low",
            quarantine_reason="stable_media_identity_unresolved",
        ),
    )
    assert result.status == "quarantined" and result.outbound_allowed is False
    with pytest.raises(LedgerError):
        create_delivery(db, watch_event_id=result.watch_event_id, target="trakt", operation="add", request={})


def test_historical_migration_boundary_suppresses_replay_without_copying_events(db):
    set_migration_boundary(db, source="trakt", account_scope="primary", maximum_source_event_id=558)
    result = ingest_observation(
        db,
        observation(
            source="trakt",
            source_event_id="500",
            account_scope="primary",
            provenance={"via": "reconciliation"},
        ),
    )
    assert result.status == "historical_boundary_suppressed"
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 0


def test_trakt_echo_is_suppressed_by_external_event_link(db):
    original = ingest_observation(
        db, observation(source="manual", source_event_id=None, provenance={"entered_by": "owner"})
    )
    link_external_event(
        db,
        watch_event_id=original.watch_event_id,
        system="trakt",
        external_event_id="trakt-history-9",
        external_media_id="1",
    )
    echo = ingest_observation(
        db,
        observation(source="trakt", source_event_id="trakt-history-9", provenance={"via": "poll"}),
    )
    assert echo.status == "external_echo_suppressed"
    assert echo.watch_event_id == original.watch_event_id
    assert db.execute("SELECT count(*) FROM watch_events").fetchone()[0] == 1


def _delivery(db, key=None):
    event = ingest_observation(db, observation(source_event_id="delivery-source"))
    return create_delivery(
        db,
        watch_event_id=event.watch_event_id,
        target="trakt",
        operation="history.add",
        request={"tmdb": 1, "watched_at": WATCHED_AT},
        idempotency_key=key,
    )


def test_delivery_pending_in_flight_verified_and_verified_is_immutable(db):
    delivery = _delivery(db)
    in_flight = transition_delivery(db, delivery.id, "in_flight", at="2026-10-06T18:01:00Z")
    verified = transition_delivery(
        db, delivery.id, "verified", target_event_id="private-target-event", at="2026-10-06T18:02:00Z"
    )
    assert in_flight.attempt_count == 1
    assert verified.state == "verified"
    with pytest.raises(LedgerError):
        transition_delivery(db, delivery.id, "pending")


def test_http_429_enters_retry_wait(db):
    delivery = _delivery(db)
    transition_delivery(db, delivery.id, "in_flight")
    result = record_delivery_failure(
        db,
        delivery.id,
        error_class="rate_limited",
        http_status=429,
        retry_at="2026-10-06T19:00:00Z",
    )
    assert result.state == "retry_wait"
    assert db.execute("SELECT next_attempt_at FROM sync_deliveries WHERE id=?", (delivery.id,)).fetchone()[0] == "2026-10-06T19:00:00Z"


def test_timeout_after_post_is_ambiguous(db):
    delivery = _delivery(db)
    transition_delivery(db, delivery.id, "in_flight")
    result = record_delivery_failure(db, delivery.id, error_class="timeout_after_send")
    assert result.state == "ambiguous"


def test_restart_recovery_never_retries_stale_in_flight_work(db):
    pending = _delivery(db)
    second_event = ingest_observation(
        db, observation(source_event_id="second-source", watched_at="2026-10-07T18:00:00Z")
    )
    in_flight = create_delivery(
        db, watch_event_id=second_event.watch_event_id, target="trakt", operation="history.add", request={"x": 2}
    )
    transition_delivery(db, in_flight.id, "in_flight", at="2026-10-06T17:00:00Z")
    runnable = recover_restart_work(
        db, now="2026-10-06T20:00:00Z", stale_started_before="2026-10-06T18:00:00Z"
    )
    assert runnable == [pending.id]
    assert db.execute("SELECT state FROM sync_deliveries WHERE id=?", (in_flight.id,)).fetchone()[0] == "ambiguous"


def test_duplicate_idempotency_key_is_rejected(db):
    _delivery(db, key="same-key")
    second_event = ingest_observation(
        db, observation(source_event_id="different-event", watched_at="2026-10-07T18:00:00Z")
    )
    with pytest.raises(DuplicateIdempotencyKey):
        create_delivery(
            db,
            watch_event_id=second_event.watch_event_id,
            target="trakt",
            operation="history.add",
            request={"x": 2},
            idempotency_key="same-key",
        )


def test_malformed_observation_fails_closed(db):
    with pytest.raises(LedgerError):
        ingest_observation(db, observation(watched_at="not-a-date"))
