"""Deterministic watched-event ledger and delivery state machine.

This module has no network clients. Callers provide normalized observations and
perform external I/O outside the ledger boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from importlib.resources import files
import json
import sqlite3
from typing import Any, Mapping


MEDIA_KINDS = {"movie", "episode"}
PRECISIONS = {"exact", "date_only", "legacy_placeholder"}
SOURCES = {"plex", "trakt", "manual", "agent", "migration"}
CONFIDENCES = {"high", "medium", "low"}
DELIVERY_STATES = {"pending", "in_flight", "verified", "retry_wait", "ambiguous", "failed"}


class LedgerError(ValueError):
    """A deterministic ledger invariant was violated."""


class DuplicateIdempotencyKey(LedgerError):
    """A target/idempotency-key pair already exists."""


@dataclass(frozen=True)
class Observation:
    media_kind: str
    local_media_id: int | None
    watched_at: str
    watched_date_precision: str
    source: str
    provenance: Mapping[str, Any]
    source_event_id: str | None = None
    confidence: str = "high"
    account_scope: str = "default"
    external_media_id: str | None = None
    quarantine_reason: str | None = None


@dataclass(frozen=True)
class IngestResult:
    status: str
    watch_event_id: int | None
    outbound_allowed: bool


@dataclass(frozen=True)
class Delivery:
    id: int
    state: str
    attempt_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise LedgerError("provenance must be JSON serializable") from exc


def _timestamp(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise LedgerError("watched_at must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerError("watched_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise LedgerError("watched_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply the additive ledger schema without reading or rewriting old rows."""
    migration = files("personal_ai_brain.sql").joinpath("001_watched_event_ledger.sql").read_text(encoding="utf-8")
    connection.executescript(migration)


def event_fingerprint(observation: Observation) -> str:
    """Fingerprint exact same-source observations; never proximity-merge sources."""
    payload = {
        "event_type": "watch",
        "local_media_id": observation.local_media_id,
        "media_kind": observation.media_kind,
        "source": observation.source,
        "watched_at": _timestamp(observation.watched_at),
    }
    if observation.local_media_id is None:
        payload["quarantine_reason"] = observation.quarantine_reason
        payload["source_event_id"] = observation.source_event_id
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def set_migration_boundary(
    connection: sqlite3.Connection,
    *,
    source: str,
    account_scope: str,
    maximum_source_event_id: int,
    at: str | None = None,
) -> None:
    """Record an accepted historical high-water mark without copying events."""
    if source not in SOURCES or maximum_source_event_id < 0 or not account_scope:
        raise LedgerError("invalid migration boundary")
    watermark = _canonical_json({"kind": "event_id_lte", "value": maximum_source_event_id})
    connection.execute(
        """INSERT INTO source_cursors(source, account_scope, cursor_or_watermark, last_success_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(source, account_scope) DO UPDATE SET
             cursor_or_watermark=excluded.cursor_or_watermark,
             last_success_at=excluded.last_success_at""",
        (source, account_scope, watermark, at or utc_now()),
    )


def _suppressed_by_boundary(connection: sqlite3.Connection, observation: Observation) -> bool:
    if observation.source_event_id is None:
        return False
    row = connection.execute(
        "SELECT cursor_or_watermark FROM source_cursors WHERE source=? AND account_scope=?",
        (observation.source, observation.account_scope),
    ).fetchone()
    if row is None:
        return False
    try:
        boundary = json.loads(row[0])
        return boundary.get("kind") == "event_id_lte" and int(observation.source_event_id) <= int(boundary["value"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def ingest_observation(
    connection: sqlite3.Connection,
    observation: Observation,
    *,
    imported_at: str | None = None,
) -> IngestResult:
    """Ingest one observation atomically and return its deterministic outcome."""
    if observation.media_kind not in MEDIA_KINDS:
        raise LedgerError("unsupported media kind")
    if observation.watched_date_precision not in PRECISIONS:
        raise LedgerError("unsupported watched date precision")
    if observation.source not in SOURCES:
        raise LedgerError("unsupported source")
    if observation.confidence not in CONFIDENCES:
        raise LedgerError("unsupported confidence")
    if observation.local_media_id is not None and observation.local_media_id <= 0:
        raise LedgerError("local media identity must be positive")
    if observation.local_media_id is None and not observation.quarantine_reason:
        raise LedgerError("missing identity must be quarantined")
    if observation.local_media_id is not None and observation.quarantine_reason:
        raise LedgerError("identified events cannot be quarantined")

    watched_at = _timestamp(observation.watched_at)
    now = imported_at or utc_now()
    provenance = _canonical_json(observation.provenance)
    fingerprint = event_fingerprint(observation)

    with connection:
        if _suppressed_by_boundary(connection, observation):
            return IngestResult("historical_boundary_suppressed", None, False)

        if observation.source_event_id is not None:
            duplicate = connection.execute(
                "SELECT id, quarantine_reason FROM watch_events WHERE source=? AND source_event_id=?",
                (observation.source, observation.source_event_id),
            ).fetchone()
            if duplicate:
                return IngestResult("duplicate_source_event", int(duplicate[0]), duplicate[1] is None)
            linked = connection.execute(
                "SELECT watch_event_id FROM external_event_links WHERE system=? AND external_event_id=?",
                (observation.source, observation.source_event_id),
            ).fetchone()
            if linked:
                return IngestResult("external_echo_suppressed", int(linked[0]), False)

        duplicate = connection.execute(
            "SELECT id, quarantine_reason FROM watch_events WHERE event_fingerprint=?", (fingerprint,)
        ).fetchone()
        if duplicate:
            event_id = int(duplicate[0])
            if observation.source_event_id is not None:
                link_external_event(
                    connection,
                    watch_event_id=event_id,
                    system=observation.source,
                    external_event_id=observation.source_event_id,
                    external_media_id=observation.external_media_id,
                    linked_at=now,
                )
            return IngestResult("duplicate_fingerprint", event_id, duplicate[1] is None)

        cursor = connection.execute(
            """INSERT INTO watch_events(
                 local_media_id, media_kind, event_type, watched_at, watched_date_precision,
                 source, provenance, source_event_id, confidence, imported_at,
                 event_fingerprint, quarantine_reason, created_at)
               VALUES (?, ?, 'watch', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                observation.local_media_id,
                observation.media_kind,
                watched_at,
                observation.watched_date_precision,
                observation.source,
                provenance,
                observation.source_event_id,
                observation.confidence,
                now,
                fingerprint,
                observation.quarantine_reason,
                now,
            ),
        )
        event_id = int(cursor.lastrowid)
        if observation.source_event_id is not None and observation.local_media_id is not None:
            link_external_event(
                connection,
                watch_event_id=event_id,
                system=observation.source,
                external_event_id=observation.source_event_id,
                external_media_id=observation.external_media_id,
                linked_at=now,
            )
        quarantined = observation.local_media_id is None
        return IngestResult("quarantined" if quarantined else "created", event_id, not quarantined)


def link_external_event(
    connection: sqlite3.Connection,
    *,
    watch_event_id: int,
    system: str,
    external_event_id: str,
    external_media_id: str | None = None,
    linked_at: str | None = None,
) -> None:
    if not system or not external_event_id:
        raise LedgerError("external event link requires system and event ID")
    existing = connection.execute(
        "SELECT watch_event_id FROM external_event_links WHERE system=? AND external_event_id=?",
        (system, external_event_id),
    ).fetchone()
    if existing:
        if int(existing[0]) == watch_event_id:
            return
        raise LedgerError("external event is already linked to another watch event")
    connection.execute(
        """INSERT INTO external_event_links(
             watch_event_id, system, external_event_id, external_media_id, linked_at)
           VALUES (?, ?, ?, ?, ?)""",
        (watch_event_id, system, external_event_id, external_media_id, linked_at or utc_now()),
    )


def supersede_event(connection: sqlite3.Connection, *, old_event_id: int, replacement_event_id: int) -> None:
    """Apply an explicit correction; original history remains auditable."""
    if old_event_id == replacement_event_id:
        raise LedgerError("event cannot supersede itself")
    with connection:
        old = connection.execute("SELECT superseded_by FROM watch_events WHERE id=?", (old_event_id,)).fetchone()
        replacement = connection.execute("SELECT id FROM watch_events WHERE id=?", (replacement_event_id,)).fetchone()
        if old is None or replacement is None or old[0] is not None:
            raise LedgerError("invalid or already superseded event")
        connection.execute("UPDATE watch_events SET superseded_by=? WHERE id=?", (replacement_event_id, old_event_id))


def deterministic_idempotency_key(watch_event_id: int, target: str, operation: str) -> str:
    return sha256(f"watch-event:{watch_event_id}:{target}:{operation}".encode("utf-8")).hexdigest()


def create_delivery(
    connection: sqlite3.Connection,
    *,
    watch_event_id: int,
    target: str,
    operation: str,
    request: Mapping[str, Any],
    idempotency_key: str | None = None,
) -> Delivery:
    event = connection.execute(
        "SELECT quarantine_reason, superseded_by FROM watch_events WHERE id=?", (watch_event_id,)
    ).fetchone()
    if event is None or event[0] is not None or event[1] is not None:
        raise LedgerError("delivery requires an active, identified watch event")
    key = idempotency_key or deterministic_idempotency_key(watch_event_id, target, operation)
    request_hash = sha256(_canonical_json(request).encode("utf-8")).hexdigest()
    try:
        cursor = connection.execute(
            """INSERT INTO sync_deliveries(
                 watch_event_id, target, operation, idempotency_key, request_hash, state)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (watch_event_id, target, operation, key, request_hash),
        )
    except sqlite3.IntegrityError as exc:
        raise DuplicateIdempotencyKey("duplicate target idempotency key") from exc
    return Delivery(int(cursor.lastrowid), "pending", 0)


_TRANSITIONS = {
    "pending": {"in_flight", "failed"},
    "retry_wait": {"in_flight", "failed"},
    "in_flight": {"verified", "retry_wait", "ambiguous", "failed"},
    "ambiguous": {"verified", "pending", "failed"},
    "verified": set(),
    "failed": set(),
}


def transition_delivery(
    connection: sqlite3.Connection,
    delivery_id: int,
    new_state: str,
    *,
    at: str | None = None,
    next_attempt_at: str | None = None,
    http_status: int | None = None,
    error_class: str | None = None,
    target_event_id: str | None = None,
) -> Delivery:
    if new_state not in DELIVERY_STATES:
        raise LedgerError("unsupported delivery state")
    row = connection.execute(
        "SELECT state, attempt_count FROM sync_deliveries WHERE id=?", (delivery_id,)
    ).fetchone()
    if row is None or new_state not in _TRANSITIONS[row[0]]:
        raise LedgerError("invalid delivery state transition")
    now = at or utc_now()
    attempts = int(row[1]) + (1 if new_state == "in_flight" else 0)
    started_at = now if new_state == "in_flight" else None
    verified_at = now if new_state == "verified" else None
    if new_state == "verified" and not target_event_id:
        raise LedgerError("verified delivery requires target event ID")
    connection.execute(
        """UPDATE sync_deliveries SET state=?, attempt_count=?, next_attempt_at=?,
             last_http_status=?, last_error_class=?, target_event_id=COALESCE(?, target_event_id),
             started_at=COALESCE(?, started_at), verified_at=COALESCE(?, verified_at)
           WHERE id=?""",
        (
            new_state,
            attempts,
            next_attempt_at,
            http_status,
            error_class,
            target_event_id,
            started_at,
            verified_at,
            delivery_id,
        ),
    )
    return Delivery(delivery_id, new_state, attempts)


def record_delivery_failure(
    connection: sqlite3.Connection,
    delivery_id: int,
    *,
    error_class: str,
    http_status: int | None = None,
    retry_at: str | None = None,
    at: str | None = None,
) -> Delivery:
    """Map rate limits and uncertain POST outcomes to safe states."""
    if http_status == 429:
        if retry_at is None:
            raise LedgerError("rate-limit response requires retry deadline")
        return transition_delivery(
            connection,
            delivery_id,
            "retry_wait",
            at=at,
            next_attempt_at=_timestamp(retry_at),
            http_status=http_status,
            error_class=error_class,
        )
    if error_class in {"timeout_after_send", "connection_lost_after_send", "ambiguous_response"}:
        return transition_delivery(
            connection,
            delivery_id,
            "ambiguous",
            at=at,
            http_status=http_status,
            error_class=error_class,
        )
    return transition_delivery(
        connection, delivery_id, "failed", at=at, http_status=http_status, error_class=error_class
    )


def recover_restart_work(
    connection: sqlite3.Connection,
    *,
    now: str,
    stale_started_before: str,
) -> list[int]:
    """Quarantine stale in-flight work and return only safe runnable IDs."""
    now_value = _timestamp(now)
    stale_value = _timestamp(stale_started_before)
    with connection:
        connection.execute(
            """UPDATE sync_deliveries
               SET state='ambiguous', last_error_class='restart_during_in_flight'
               WHERE state='in_flight' AND started_at IS NOT NULL AND started_at <= ?""",
            (stale_value,),
        )
        rows = connection.execute(
            """SELECT id FROM sync_deliveries
               WHERE state='pending'
                  OR (state='retry_wait' AND next_attempt_at IS NOT NULL AND next_attempt_at <= ?)
               ORDER BY id""",
            (now_value,),
        ).fetchall()
    return [int(row[0]) for row in rows]
