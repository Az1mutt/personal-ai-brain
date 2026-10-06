"""Pure read-only normalization for Plex and Tautulli watch observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .watched_ledger import LedgerError, Observation


@dataclass(frozen=True)
class PlexIdentity:
    local_media_id: int
    media_kind: str
    external_media_id: str | None = None


@dataclass(frozen=True)
class PlexIdentityEvidence:
    media_kind: str
    rating_key: str | None
    guids: tuple[str, ...]


IdentityResolver = Callable[[PlexIdentityEvidence], PlexIdentity | None]


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LedgerError("Plex observation timestamp is malformed") from exc
        if parsed.tzinfo is None:
            raise LedgerError("Plex observation timestamp lacks timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    raise LedgerError("Plex observation has no event timestamp")


def normalize_plex_observation(
    payload: Mapping[str, Any],
    resolve_identity: IdentityResolver,
    *,
    observed_via: str = "webhook",
) -> Observation:
    """Normalize one payload without making network calls or external writes."""
    metadata = payload.get("Metadata") or payload.get("metadata") or payload
    if not isinstance(metadata, Mapping):
        raise LedgerError("Plex metadata must be an object")
    media_kind = str(_first(metadata, "type", "media_type") or "")
    if media_kind not in {"movie", "episode"}:
        raise LedgerError("Plex observation is not a movie or episode")

    rating_key_value = _first(metadata, "ratingKey", "rating_key")
    rating_key = str(rating_key_value) if rating_key_value is not None else None
    guids: list[str] = []
    direct_guid = _first(metadata, "guid", "plex_guid")
    if direct_guid:
        guids.append(str(direct_guid))
    raw_guids = metadata.get("Guid") or metadata.get("guids") or []
    if isinstance(raw_guids, list):
        for item in raw_guids:
            if isinstance(item, Mapping) and item.get("id"):
                guids.append(str(item["id"]))
            elif isinstance(item, str):
                guids.append(item)

    watched_at = _timestamp(
        _first(payload, "event_at", "timestamp", "watched_at")
        or _first(metadata, "lastViewedAt", "last_viewed_at", "watched_at")
    )
    explicit_event = _first(payload, "notification_uuid", "event_id", "history_id")
    session = _first(payload, "sessionKey", "session_key", "session_id")
    source_event_id = str(explicit_event) if explicit_event is not None else None
    if source_event_id is None and session is not None:
        source_event_id = f"{session}:{rating_key or 'unknown'}:{watched_at}"

    evidence = PlexIdentityEvidence(media_kind, rating_key, tuple(dict.fromkeys(guids)))
    identity = resolve_identity(evidence)
    provenance = {
        "adapter": "plex_tautulli_v0.1",
        "observed_via": observed_via,
        "plex_rating_key": rating_key,
        "plex_guids": list(evidence.guids),
    }
    if identity is None or identity.media_kind != media_kind or identity.local_media_id <= 0:
        return Observation(
            media_kind=media_kind,
            local_media_id=None,
            watched_at=watched_at,
            watched_date_precision="exact",
            source="plex",
            provenance=provenance,
            source_event_id=source_event_id,
            confidence="low",
            external_media_id=evidence.guids[0] if evidence.guids else rating_key,
            quarantine_reason="stable_media_identity_unresolved",
        )
    return Observation(
        media_kind=media_kind,
        local_media_id=identity.local_media_id,
        watched_at=watched_at,
        watched_date_precision="exact",
        source="plex",
        provenance=provenance,
        source_event_id=source_event_id,
        confidence="high",
        external_media_id=identity.external_media_id or (evidence.guids[0] if evidence.guids else rating_key),
    )
