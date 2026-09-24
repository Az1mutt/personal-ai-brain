# Codex → ChatGPT Handoff

## Timestamp
2026-09-24 20:35 Europe/Bratislava

## Scope
Minimum v0.3 persistent READ-ONLY Homelab runtime. The earlier v0.2 live acceptance
was already complete and was not repeated as a bootstrap/setup exercise.

## Environment
- Host: Igor's Linux Homelab; private connection details omitted.
- Repo: Az1mutt/personal-ai-brain, ~/projects/personal-ai-brain.
- Change branch: feat/homelab-readonly-runtime, through branch/PR workflow.
- Deployment: Docker Compose project personal-ai-brain, service core.
- Runtime: digest-pinned Python 3.14 slim image, pinned PyYAML 6.0.3.
- Existing .venv remains available for tests; no new credential was provisioned.

## Implemented and verified
The detached container survives SSH/session termination. Its restart policy is
unless-stopped and the host Docker service is enabled at boot. Container recreation
was exercised; whole-host reboot and long-duration operation were not.

The existing mode-600 GitHub credential is injected as a read-only Compose file
secret, read by UID/GID 1000. Its value is not in Git, image build inputs, environment
variables, CLI arguments or reports. Runtime root is read-only, capabilities are
dropped, no-new-privileges is enabled, and no ports or Docker socket are exposed.
Core still uses the existing GET-only reader; no write method or permission was added.
The token's successful read access is verified; its user-selected permission scope
was not independently audited through GitHub settings.

Manual core-report, rollup-proposals and core-snapshot all completed against the
private Project OS: 12 states across 8 projects, 3 schema errors, 6 warnings and
2 proposals, with zero source-read failures. These validation findings return
runtime status findings / exit 0. Existing CLI semantics remain unchanged.

Docker liveness uses a local heartbeat and makes no GitHub requests. Rich health
reports runtime availability plus the last completed manual run and timestamps.
An isolated Compose probe with a dummy invalid credential produced
source_read_failure / exit 3 while Docker remained healthy. After removing that
probe, health returned unavailable / exit 1. The production credential was untouched.
Probe containers/network were removed; private diagnostic artifacts remain on host.

## Checks and local artifacts
- 44 tests passed: 29 existing plus 15 runtime tests covering findings, source errors,
  sanitized software failures, output persistence and concurrent-job exclusion.
- Image built successfully; Compose started and waited for healthy service.
- Fresh SSH connection and forced container recreation preserved health, logs and snapshot.
- Host runtime directory mode 700; service.log and latest.json mode 600.
- Snapshot: ~/.local/state/personal-ai-brain/runtime/runs/20260924T182758Z-00fab03b/core-snapshot.json.
- Report run: 20260924T182804Z-db984a6c; proposals run: 20260924T182808Z-f0561f94.
- Logs/results: ~/.local/state/personal-ai-brain/runtime (outside repository).
- service.log rotates at 1 MB with three backups; private per-run outputs have manual retention.

## Manual operations
From ~/projects/personal-ai-brain:

```sh
sh scripts/runtime.sh up
sh scripts/runtime.sh core-report
sh scripts/runtime.sh rollup-proposals
sh scripts/runtime.sh core-snapshot
sh scripts/runtime.sh health
sh scripts/runtime.sh logs
```

Use `sh scripts/runtime.sh down` to stop this Compose project while retaining host
outputs. Health reflects the last manual source read, not continuous connectivity.
See docs/homelab-runtime.md for exit codes, secret handling and lifecycle details.

## Remaining source findings
Existing missing fields remain in the Homelab root state (dependencies,
important_open_loops), Recipe root state (same), and centrally stored Career state
(dependencies). Two older rollups and four freshness warnings were observed.
No owner facts were invented, proposals applied or unrelated freshness dates changed.
Private raw reports remain off the public repository. Media services were unchanged.

## Scope boundary and exact next action
The minimum persistent manual runtime is complete. Scheduling, Telegram, n8n,
MCP, LLM reasoning, general remote-shell API, autonomous Project OS writes and
broader orchestration remain unimplemented by design. Do not equate this slice
with completion of all broader v0.3 ambitions.

Continue operating the deployed runtime and route existing state findings to their
owners. Scope any new automation separately. Do not repeat bootstrap, token setup,
package discovery or the prior v0.2 acceptance unless diagnosing a new failure.

## Project State impact
.project/state.yaml advances to homelab-persistent-readonly-runtime-verified because
the deployment, permission boundary and health behavior were actually exercised.
