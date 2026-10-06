import sqlite3

from personal_ai_brain.plex_observation import PlexIdentity, normalize_plex_observation
from personal_ai_brain.watched_ledger import apply_migrations, ingest_observation


def payload(**changes):
    value = {
        "event": "media.scrobble",
        "event_at": "2026-10-06T18:00:00Z",
        "sessionKey": "session-1",
        "Metadata": {
            "type": "movie",
            "ratingKey": "77",
            "guid": "plex://movie/abc",
            "Guid": [{"id": "tmdb://123"}, {"id": "imdb://tt0000123"}],
        },
    }
    value.update(changes)
    return value


def test_plex_adapter_preserves_identity_timestamp_and_session():
    seen = []

    def resolve(evidence):
        seen.append(evidence)
        return PlexIdentity(9, "movie", "tmdb://123")

    result = normalize_plex_observation(payload(), resolve)
    assert result.local_media_id == 9
    assert result.watched_at == "2026-10-06T18:00:00Z"
    assert result.source_event_id == "session-1:77:2026-10-06T18:00:00Z"
    assert result.external_media_id == "tmdb://123"
    assert seen[0].guids == ("plex://movie/abc", "tmdb://123", "imdb://tt0000123")


def test_tautulli_episode_observation_normalizes():
    result = normalize_plex_observation(
        {
            "watched_at": 1791309600,
            "notification_uuid": "notification-1",
            "media_type": "episode",
            "rating_key": "99",
            "guids": ["tmdb://episode/4"],
        },
        lambda evidence: PlexIdentity(41, "episode", evidence.guids[0]),
        observed_via="tautulli",
    )
    assert result.media_kind == "episode"
    assert result.local_media_id == 41
    assert result.source_event_id == "notification-1"
    assert result.provenance["observed_via"] == "tautulli"


def test_unresolved_plex_identity_is_durably_quarantined():
    observation = normalize_plex_observation(payload(), lambda _: None)
    assert observation.quarantine_reason == "stable_media_identity_unresolved"
    connection = sqlite3.connect(":memory:")
    apply_migrations(connection)
    result = ingest_observation(connection, observation)
    assert result.status == "quarantined"
    assert result.outbound_allowed is False
    assert connection.execute("SELECT count(*) FROM sync_deliveries").fetchone()[0] == 0
