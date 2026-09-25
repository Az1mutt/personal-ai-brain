# Manual read-only Homelab runtime

This v0.3 slice keeps a lightweight container alive independently of SSH/Codex.
It runs jobs only when requested. There is no scheduler, HTTP listener, remote
shell API, LLM, notification integration or GitHub writer.

## Start and operate

From the repository on the Linux host, as the owner of the existing token:

```sh
sh scripts/runtime.sh up
sh scripts/runtime.sh core-report
sh scripts/runtime.sh rollup-proposals
sh scripts/runtime.sh core-snapshot
sh scripts/runtime.sh health
sh scripts/runtime.sh logs
```

`up` builds and starts Compose detached with `restart: unless-stopped`.
Closing SSH or Codex does not stop it. Docker must be enabled at host boot for
reboot persistence. `sh scripts/runtime.sh down` stops/removes only this Compose
project; logs and reports remain. No changes to the media stack are required.

Each manual command prints a concise JSON result including its artifact directory.
The requested report plus a diagnostic snapshot and result JSON are saved under
`~/.local/state/personal-ai-brain/runtime/runs/<run-id>/`. The snapshot records
all source/schema findings. `service.log` records lifecycle events and rotates at
1 MB with three backups. Per-run artifacts are retained until manually removed;
there is no automatic deletion or retention scheduler in this slice.

Each run uses one cached source view for the existing collectors. GitHub access
remains GET-only through the existing reader; proposals never apply themselves.
One run at a time is allowed. Concurrent requests return exit 5 without changing
the last completed result. Existing CLI commands retain their original semantics;
the runtime wrapper treats successfully detected validation findings as a working
runtime rather than returning the original CLI's validation-error exit 2.

## Credential and filesystem boundary

The existing `~/.config/personal-ai-brain/github-token` is a Compose file secret
mounted read-only at `/run/secrets/github_token`. Its value is never passed as a
Docker build argument, environment variable or command-line argument. Only the
file path appears in configuration. Keep the host file mode 600 and its parent
700. The token must have only Contents read permission for the private Project OS;
an API read test alone cannot prove that write permission was not selected.

The helper passes the invoking UID/GID (1000 on the verified Homelab), so the
container can read the owner's mode-600 secret without making it world-readable.
Compose file secrets are host bind mounts, not encrypted Swarm secrets.

The container has a read-only root, a small temporary filesystem, dropped Linux
capabilities, no-new-privileges, no host ports and no Docker socket. Only `/state`
is a persistent writable mount. It holds private data and must not be committed
or copied into the image. The Docker build context is allowlisted by `.dockerignore`.
The runtime uses a digest-pinned Python image and pinned runtime PyYAML.

Optional host overrides (paths, never secret values): `PAB_STATE_DIR`,
`PAB_GITHUB_TOKEN_FILE`, `PAB_UID`, `PAB_GID`. Use the same overrides for all commands.
No `.env` is necessary. Replacing the secret file atomically may require recreating
the container to refresh its file bind mount (`up --force-recreate` through Compose).

## Health contract

Docker's healthcheck is strictly local liveness: imports plus a heartbeat from
the persistent process. It makes no GitHub requests and performs no scheduled job.
The richer `health` command reports liveness and the **last completed manual run**:

| Runtime / last run | Exit | Meaning |
|---|---:|---|
| unavailable | 1 | Container absent/stopped, or heartbeat missing/stale |
| available / runtime_failure | 1 | Local job failed; inspect sanitized result and code |
| available / source_read_failure | 3 | Missing credential, GitHub/network/read or source parse failure |
| available / findings | 0 | Runtime works; inspect Project State validation/freshness findings |
| available / ok | 0 | Last manual read completed without findings |
| available / not_checked | 4 | No manual source read recorded yet |

Timestamps in `last_run` show when source access was checked. Health does not imply
current GitHub connectivity, silently refresh old source results or hide their age.
A healthy Docker container may therefore have a source read failure, which is
shown explicitly by the richer status. Source validation errors never kill the
keeper or mark Docker liveness unhealthy. Startup failure, missing heartbeat or a
dead process does. Results survive recreation. Compose now places the Core heartbeat in its host
state directory so the separate control worker can read it through a read-only
mount. Graceful shutdown removes it; a crash leaves a file that expires after
30 seconds. No Docker socket or remote shell is needed for this read.

## Optional v0.4A control worker

The Core service above still has no writer or scheduler. A separate worker adds
bounded private Issues requests; see [control bridge](control-bridge.md).
Start it with `sh scripts/control.sh up`; `control.sh down` stops only that worker.
The original Core credential and manual operations remain unchanged.

## Verification

Run `pytest -q` for existing and runtime boundary tests. For deployment, use `up`,
run the three manual commands, inspect health/artifacts, reconnect over a fresh
SSH session, and recreate the service to verify lifecycle/log persistence.
Source-failure probes should use an isolated test Compose project and dummy secret,
never modify the production token. Existing Project State warnings are not a
reason to weaken validation or rewrite unrelated source states.
