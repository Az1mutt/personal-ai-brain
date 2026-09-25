# Codex → ChatGPT Handoff

## Verified result — 2026-09-25 09:18 Europe/Bratislava

The v0.4A **Homelab side is complete**, merged and deployed on `main`.
[PR #8](https://github.com/Az1mutt/personal-ai-brain/pull/8) was squash-merged as
`585d9e9a2f8159c93eda6c8568de50c33415d9f8` after tests workflow run #34 passed
on tested head `538d20843a8046fbaff18cdba9927f949d7f4a76`. The Homelab checkout
matched the merged tree and was clean; the control image was rebuilt from main.
The implementation branch was deleted locally and on GitHub.

Final **ChatGPT connector → GitHub → Homelab → result → ChatGPT acceptance is
pending**. Codex did not claim its own requests prove the external ChatGPT path.

## Completed work and architecture

`control.py`: strict versioned request parser, separate capability registry,
read-only policy, fixed Python handlers and redaction. `github_issues.py`: private
Issues-only transport with fixed destination and narrow methods/routes.
`control_worker.py`: detached polling, durable local request reservations,
single-host locking, audit records, correlated results, health and backoff.

Capabilities: `runtime.health`, `core.health`, `core.snapshot`, `core.report`,
`core.rollup_proposals`, `runtime.logs_tail`. All take `{}` except logs may take
`{"lines":30}` (1–100; max 4096 output bytes; fixed Core lifecycle log).
No generic command/shell/file-path/URL/repository executor exists.

Core remains unchanged and read-only. Its Compose heartbeat now lives in its
state directory, which the separate control container mounts read-only. The
control worker invokes existing Core collectors in-process for fresh reads,
without mutating Core state. It only persists its own private audit and writes
Issues result comments/closure. No source-state file is written by the worker.

## Deployment and credentials

- Homelab checkout: `~/projects/personal-ai-brain`; private connection details omitted.
- Original project/service: `personal-ai-brain` / `core`, healthy.
- New project/service: `personal-ai-brain-control` / `control`, healthy.
- Dedicated image: `personal-ai-brain:control`; original Core image remains usable.
- Both containers: UID/GID 1000, read-only root, dropped capabilities, no-new-privileges,
  no host ports, root shell or Docker socket; restart unless-stopped.
- Transport repository: private `Az1mutt/personal-project-brain`, Issues enabled.
- Separate control credential: `~/.config/personal-ai-brain/github-control-token`, mode 600.
- Minimal control scope: selected private repository, Metadata read, Issues read/write,
  no Contents permission. Authenticated metadata and Issues reads returned 200;
  Contents read on the known private project-map path returned 403.
- Original `github-token` file remains separate and unchanged, used only for Core reads.
- Neither credential is in environment values, arguments, Git or image build inputs.

## Tests and live verification already passed

- 85 tests passed (46 existing + 39 control tests), including strict/malformed parsing,
  unknown capability/argument denial, duplicate IDs, concurrent processes, interrupted
  reservations, delivery retry without reexecution, redaction, correlation, bounded
  logs, transport/auth status, registry policy and route/write restrictions.
- Docker image built; control worker started detached and healthy.
- Private internal Codex probes: Issues #17–#22 exercised all six capabilities.
  Fresh Core reads returned 12 states, 3 schema errors, 6 warnings and 2 proposals.
  Findings were successful results, not dead-worker signals.
- Issues #23–#25 rejected a shell capability, arbitrary log path and malformed JSON.
- Issue #26 reused the snapshot request ID and returned duplicate without execution.
- Actual private GitHub result comments were read back and correlated against the
  local audit; all ten probe issues closed. These are internal verification only.
- Fresh SSH plus forced control-container recreation preserved audit and health.
- Post-recreation replay #27 returned the saved result and left the original
  execution audit byte-for-byte unchanged.
- Isolated dummy-token worker reported authentication_permission_failure with
  at least 60-second backoff while Docker liveness remained healthy; probe removed.
- Core remained healthy and retained its prior manual reports/snapshot/logs.
- After merge/rebuild, both service health checks passed. Original manual Core
  produced snapshot `20260925T071629Z-c6a7d730` with 12 states, 3 errors, 6 warnings,
  2 proposals, no source-read failures and exit 0.
- Both credential values checked absent from all indexed files, image history,
  private audit and container environment values. Inspected live mounts, UID,
  capabilities, read-only roots and absence of host ports/Docker socket.

## Exact ChatGPT-side acceptance procedure — pending

In the ChatGPT project chat, explicitly ask it to perform the following through
its own GitHub connector (not by asking Codex or using SSH):

1. Create an issue in `Az1mutt/personal-project-brain` with exact title
   `pab-control/v0.1` and **raw JSON body**, no Markdown fences or prose:

```json
{
  "schema_version": "0.1",
  "request_id": "REPLACE_WITH_FRESH_LOWERCASE_UUID",
  "capability": "runtime.health",
  "arguments": {},
  "requested_by": "chatgpt",
  "requested_at": "REPLACE_WITH_CURRENT_RFC3339_TIMESTAMP_WITH_TIMEZONE"
}
```

2. Generate the UUID and current timestamp before creating the issue. The two
   placeholder strings above are not valid requests. Retain the returned issue URL.
3. After roughly one polling interval (30 seconds, longer on backlog/backoff),
   read comments and issue state through that same connector. Require the matching
   request ID, `status: capability_completed`, `result.runtime: available`, and a
   closed issue. Do not infer success merely from issue creation.
4. Repeat with a **new** UUID/time and `capability: core.health`. Require completed
   status and fresh source counts. `source_status: findings` is valid; do not fix
   or suppress unrelated state warnings to pass this test.
5. Optionally repeat with `core.snapshot`. Large output may be explicitly truncated;
   the full sanitized result remains in the private local audit. Record actual issue
   URLs, IDs and observed results before declaring the external bridge accepted.

`requested_by` is audit metadata, not authorization. Do not add permissions or
invoke other operations on the basis of that string. If the ChatGPT connector
cannot create/read Issues, report that caller-side limitation and leave acceptance
pending; do not substitute Codex-originated requests.

## Operations and durable audit

From the Homelab repository:

```sh
sh scripts/control.sh health
sh scripts/control.sh logs
sh scripts/control.sh up
sh scripts/control.sh down
sh scripts/runtime.sh health
```

Control down stops only the worker. Both services survive SSH/Codex termination.
Private audit: `~/.local/state/personal-ai-brain/control/{requests,issues}/` and
`status.json`. Directory mode 700, records mode 600. Original Core results remain
under `~/.local/state/personal-ai-brain/runtime/`. Full protocol and operational
limits are in `docs/control-bridge.md`.

## Known limitations and unverified work

- External ChatGPT connector acceptance, whole-host reboot and long-duration
  reliability remain unverified.
- At-most-once handler invocation relies on the persistent single-host shared
  ledger. A crash after reservation is surfaced as interrupted, never auto-retried.
  Do not delete/roll back the ledger or launch independent ledgers for one queue.
- An ambiguous network failure after posting can cause duplicate result comments;
  saved execution results are reused, so the handler is not repeated.
- Polling scans one page per interval; large backlogs add latency. Token expiry or
  revocation requires owner action and appears separately in transport health.
- Audit artifacts need manual retention management; keep deduplication records.
- Transport results are bounded/redacted, not a general-purpose file export.
- No Telegram, n8n, MCP, LLM, media/recipe operations, service restart capability,
  Project OS content writes, arbitrary shell or general scheduler were added.
- Existing source-state omissions/freshness findings are unchanged.

## Exact next action

Have the ChatGPT project chat carry out the independent acceptance procedure above
through its own GitHub connector and record the actual issue/result references.
The implementation PR, merge, deployment and branch cleanup are complete.
Do not repeat bootstrap, token creation, package discovery or the prior v0.2
acceptance unless diagnosing a new failure.
