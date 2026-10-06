# Watched Event Ledger v0.1

## Ownership

`media.db` is the canonical durable record of watch events. Plex and Tautulli are
observation sources and playback interfaces. Trakt is an external portable replica.
An absent remote event is not a deletion instruction, and no layer infers an
unwatch operation.

## Ledger contract

The additive migration creates four normalized tables:

- `watch_events` stores one immutable `watch` fact per real viewing. Its media
  kind and local media ID identify the canonical movie or episode. Timestamp
  precision and JSON provenance retain whether a date is exact, date-only, or a
  legacy placeholder. A correction creates another event and explicitly links
  the original through `superseded_by`.
- `external_event_links` maps a ledger event to a source or target event ID. The
  unique `(system, external_event_id)` contract suppresses replica echoes.
- `sync_deliveries` records one target operation under a deterministic idempotency
  key and request hash.
- `source_cursors` records source/account watermarks. A numeric
  `event_id_lte` migration boundary suppresses replay of accepted historical
  events without copying those events into the ledger.

Source event IDs deduplicate redelivery from the same system. The event
fingerprint deduplicates the same exact observation when no common source event
ID is available. It includes source, identity and the exact timestamp; timestamp
proximity never merges two sources. A genuine later viewing therefore creates a
second event. Unresolved identity is stored as a quarantined observation and is
ineligible for delivery.

The Plex/Tautulli adapter is a pure normalizer. It retains rating keys, GUIDs,
event/session identity and event time, then delegates canonical identity lookup
to a deterministic caller. A missing or conflicting identity fails closed into
quarantine. The adapter performs no network call and no remote write.

## Delivery state machine

```text
pending ──> in_flight ──> verified
   │            ├───────> retry_wait ──> in_flight
   │            ├───────> ambiguous
   │            └───────> failed
   └────────────────────> failed

ambiguous ──explicit reconciliation──> verified | pending | failed
```

`verified` and `failed` are terminal. Verification requires the target event ID.
HTTP 429 enters `retry_wait` with an explicit retry deadline. A timeout after send
enters `ambiguous`, never an automatic retry. On restart, stale `in_flight` work
becomes `ambiguous`; only `pending` and due `retry_wait` rows are runnable.

## Historical boundary

The completed 558/558 Trakt migration remains unchanged. v0.1 supplies the
cursor contract and deterministic suppression logic for its private accepted
high-water mark. The migration itself does not seed personal event IDs, copy the
558 historical events, or alter existing movie, rating, watched, CSFD or external
identity rows.

## Tautulli reconciliation

`personal-ai-brain watched-reconcile` runs one bounded batch and exits so the
existing Homelab scheduler can invoke it periodically. It reads completed movie
and episode sessions incrementally from Tautulli SQLite and uses a read-only Plex
metadata GET to obtain stable GUIDs. Only an explicit numeric TMDb GUID is
accepted by the built-in resolver; unresolved identity is quarantined.

The cursor is stored in `source_cursors` under source `plex` and the configured
account scope as `{"kind":"tautulli_history_id","value":N}`. A new account scope
requires an explicitly accepted initial watermark, preventing accidental Plex
history backfill. Normal reads start at a small bounded overlap. Known overlap
events count as duplicates; unseen rows at or below the cursor are intentionally
not imported.

Each event is ingested durably before its cursor position advances. If the
process stops between those commits, the next run re-reads the event, source-ID
deduplication returns the existing canonical event, and the cursor advances.
Quarantined identity is a durable handled result. A malformed payload, source
failure, or other unsafe error records cursor failure time, stops the batch, and
does not advance past that position.

Example scheduler command (paths and account values remain private runtime
configuration):

```sh
personal-ai-brain watched-reconcile \
  --media-db /path/to/media.db \
  --tautulli-db /path/to/tautulli.db \
  --tautulli-user ACCOUNT \
  --account-scope ACCOUNT_SCOPE \
  --plex-url http://plex:32400 \
  --plex-token-file /run/secrets/plex_token \
  --initial-watermark ACCEPTED_HISTORY_ID
```

After the first successful invocation, omit `--initial-watermark`; the durable
cursor is reused. The command contains no Plex or Trakt write operation and does
not create `sync_deliveries`.

## Explicitly deferred

- deployment or periodic scheduling of the reconciliation command;
- webhook listener or persistent polling framework;
- Trakt API client or any Trakt write;
- any Plex write client or operation;
- ratings, deletes, unwatch propagation and historical Plex backfill;
- automatic identity inference, LLM matching or LLM retry decisions.
