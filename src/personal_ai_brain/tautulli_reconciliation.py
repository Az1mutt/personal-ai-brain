"""Restart-safe, read-only Tautulli observation reconciliation.

The source and Plex clients only read. The runner writes canonical observations
and its cursor to media.db; it never creates or executes outbound deliveries.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping, Protocol, Sequence
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .plex_observation import (
    IdentityResolver,
    PlexIdentity,
    PlexIdentityEvidence,
    normalize_plex_observation,
)
from .watched_ledger import IngestResult, LedgerError, ingest_observation, utc_now


CURSOR_KIND = "tautulli_history_id"
CURSOR_SOURCE = "plex"


class ReconciliationError(RuntimeError):
    """The batch cannot safely continue."""


class CursorNotInitialized(ReconciliationError):
    """A new source requires an explicit accepted starting watermark."""


@dataclass(frozen=True)
class SourceEvent:
    position: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ReconciliationResult:
    read_count: int
    processed_count: int
    created_count: int
    duplicate_count: int
    quarantined_count: int
    cursor: int
    failed_position: int | None = None
    error_class: str | None = None


class ObservationSource(Protocol):
    def read_after(self, position: int, *, limit: int) -> Sequence[SourceEvent]: ...


AfterIngestHook = Callable[[SourceEvent, IngestResult], None]


def _cursor_value(connection: sqlite3.Connection, account_scope: str) -> int | None:
    row = connection.execute(
        "SELECT cursor_or_watermark FROM source_cursors WHERE source=? AND account_scope=?",
        (CURSOR_SOURCE, account_scope),
    ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(row[0])
        if value.get("kind") != CURSOR_KIND or int(value["value"]) < 0:
            raise ValueError
        return int(value["value"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ReconciliationError("invalid Tautulli source cursor") from exc


def _store_cursor(
    connection: sqlite3.Connection,
    account_scope: str,
    position: int,
) -> None:
    encoded = json.dumps(
        {"kind": CURSOR_KIND, "value": position},
        sort_keys=True,
        separators=(",", ":"),
    )
    with connection:
        connection.execute(
            """INSERT INTO source_cursors(
                 source, account_scope, cursor_or_watermark, last_success_at, last_error_at)
               VALUES (?, ?, ?, ?, NULL)
               ON CONFLICT(source, account_scope) DO UPDATE SET
                 cursor_or_watermark=excluded.cursor_or_watermark,
                 last_success_at=excluded.last_success_at,
                 last_error_at=NULL""",
            (CURSOR_SOURCE, account_scope, encoded, utc_now()),
        )


def _record_cursor_error(
    connection: sqlite3.Connection,
    account_scope: str,
) -> None:
    with connection:
        connection.execute(
            """UPDATE source_cursors SET last_error_at=?
               WHERE source=? AND account_scope=?""",
            (utc_now(), CURSOR_SOURCE, account_scope),
        )


def reconcile_tautulli(
    connection: sqlite3.Connection,
    source: ObservationSource,
    resolve_identity: IdentityResolver,
    *,
    account_scope: str,
    initial_watermark: int | None = None,
    overlap: int = 2,
    limit: int = 100,
    after_ingest: AfterIngestHook | None = None,
) -> ReconciliationResult:
    """Reconcile one bounded ordered batch and durably advance per event.

    Ingest commits before cursor advancement. A crash in that gap is safe: the
    next run observes the same source ID, deduplicates it, and then advances.
    """
    if not account_scope or overlap < 0 or limit <= 0:
        raise ReconciliationError("invalid reconciliation configuration")
    cursor = _cursor_value(connection, account_scope)
    if cursor is None:
        if initial_watermark is None or initial_watermark < 0:
            raise CursorNotInitialized("explicit initial watermark required")
        _store_cursor(connection, account_scope, initial_watermark)
        cursor = initial_watermark

    start = max(0, cursor - overlap)
    try:
        events = sorted(source.read_after(start, limit=limit), key=lambda item: item.position)
    except Exception as exc:
        _record_cursor_error(connection, account_scope)
        raise ReconciliationError("Tautulli source read failed") from exc
    if any(event.position <= start for event in events):
        raise ReconciliationError("source returned an event outside the requested window")
    if any(left.position == right.position for left, right in zip(events, events[1:])):
        raise ReconciliationError("source returned duplicate cursor positions")

    created = duplicates = quarantined = processed = 0
    for event in events:
        if event.position <= cursor:
            source_event_id = event.payload.get("history_id") or event.payload.get("event_id")
            existing = None
            if source_event_id is not None:
                existing = connection.execute(
                    """SELECT id FROM watch_events
                       WHERE source='plex' AND source_event_id=?""",
                    (str(source_event_id),),
                ).fetchone()
            # A cursor asserts that every older source position was already
            # handled or intentionally bounded out. Overlap may confirm known
            # events, but it must never backfill an unseen historical row.
            if existing is not None:
                processed += 1
                duplicates += 1
            continue
        try:
            observation = normalize_plex_observation(
                event.payload,
                resolve_identity,
                observed_via="tautulli_reconciliation",
            )
            result = ingest_observation(connection, observation)
            if after_ingest is not None:
                after_ingest(event, result)
            _store_cursor(connection, account_scope, max(cursor, event.position))
            cursor = max(cursor, event.position)
        except Exception as exc:
            _record_cursor_error(connection, account_scope)
            return ReconciliationResult(
                len(events), processed, created, duplicates, quarantined, cursor,
                failed_position=event.position,
                error_class=type(exc).__name__,
            )
        processed += 1
        if result.status == "created":
            created += 1
        elif result.status == "quarantined":
            quarantined += 1
        elif result.status.startswith("duplicate_") or result.status == "external_echo_suppressed":
            duplicates += 1

    return ReconciliationResult(
        len(events), processed, created, duplicates, quarantined, cursor
    )


class PlexReadOnlyMetadataClient:
    """Fetch only Plex metadata GUIDs; no write methods are exposed."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 10.0):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not token:
            raise ValueError("valid Plex URL and token are required")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    def guids_for(self, rating_key: str) -> tuple[str, ...]:
        if not rating_key.isdigit():
            raise ReconciliationError("invalid Plex rating key")
        request = urllib.request.Request(
            f"{self.base_url}/library/metadata/{rating_key}?includeGuids=1&includeRelated=0",
            headers={"X-Plex-Token": self._token, "Accept": "application/xml"},
            method="GET",
        )
        root = ET.fromstring(urllib.request.urlopen(request, timeout=self.timeout).read())
        media = root.find("Video")
        if media is None or media.get("ratingKey") != rating_key:
            raise ReconciliationError("Plex metadata identity mismatch")
        values = [media.get("guid")]
        values.extend(node.get("id") for node in media.findall("Guid"))
        return tuple(dict.fromkeys(value for value in values if value))


class TautulliSQLiteSource:
    """Incrementally read completed movie/episode sessions from Tautulli SQLite."""

    def __init__(
        self,
        database: Path,
        *,
        user: str,
        guid_provider: Callable[[str], tuple[str, ...]],
        completion_ratio: float = 0.90,
    ):
        if not user or not 0 < completion_ratio <= 1:
            raise ValueError("invalid Tautulli source configuration")
        self.database = database
        self.user = user
        self.guid_provider = guid_provider
        self.completion_ratio = completion_ratio

    def read_after(self, position: int, *, limit: int) -> Sequence[SourceEvent]:
        connection = sqlite3.connect(f"file:{self.database}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                """SELECT h.id, h.rating_key, h.media_type, h.stopped,
                          h.view_offset, m.duration, m.last_viewed_at, m.guid
                   FROM session_history h
                   JOIN session_history_metadata m ON m.id=h.id
                   WHERE h.id > ? AND h.user=?
                     AND h.media_type IN ('movie', 'episode')
                     AND m.duration > 0
                     AND CAST(h.view_offset AS REAL) / m.duration >= ?
                   ORDER BY h.id
                   LIMIT ?""",
                (position, self.user, self.completion_ratio, limit),
            ).fetchall()
        finally:
            connection.close()
        events = []
        for history_id, rating_key, media_type, stopped, _, _, last_viewed_at, guid in rows:
            rating_key_text = str(rating_key)
            guids = self.guid_provider(rating_key_text)
            events.append(
                SourceEvent(
                    int(history_id),
                    {
                        "history_id": str(history_id),
                        "watched_at": int(last_viewed_at or stopped),
                        "media_type": media_type,
                        "rating_key": rating_key_text,
                        "guid": guid,
                        "guids": list(guids),
                    },
                )
            )
        return events


def resolve_tmdb_identity(evidence: PlexIdentityEvidence) -> PlexIdentity | None:
    """Resolve only an explicit numeric TMDb GUID; title matching is forbidden."""
    matches = []
    for guid in evidence.guids:
        if guid.startswith("tmdb://") and guid[7:].isdigit():
            matches.append(guid)
    if len(set(matches)) != 1:
        return None
    guid = matches[0]
    return PlexIdentity(int(guid[7:]), evidence.media_kind, guid)
