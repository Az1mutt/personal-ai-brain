# Remote Work Submission v0.1

The existing private Issues transport now exposes `work.submit`, `work.status`
and `work.cancel`. The six original read-only capabilities retain their contracts.
The existing Issues credential is unchanged. No new token, listener, port,
repository, model backend, task publisher or deployment capability is introduced.

## Caller contract

Create an issue in private `Az1mutt/personal-project-brain`, title exactly
`pab-control/v0.1`, body a raw control v0.1 JSON object. The existing six envelope
fields and freshness/8 KiB limits apply. `requested_by` is audit metadata, never
authorization: everyone authorized to create issues in this private repository
can invoke these bounded operations.

| Capability | Exact arguments |
|---|---|
| `work.submit` | `{"contract": <Work Contract v0.1>}` |
| `work.status` | `{"task_id": "<canonical UUID>"}` |
| `work.cancel` | `{"task_id": "<canonical UUID>"}` |

The only allowed task remains `fixture.patch-test.v1`, repository
`Az1mutt/personal-ai-brain`, base SHA
`71f0d82516d059ba2d65e028742cd73b2b9ee6bc`. See
[Work Runner](work-runner-v01.md) for its exact fixed contract. Unknown fields,
commands, paths, alternate refs/repositories and scripts are rejected. Both
control and runner validate independently; runner applies admission freshness.

Control results retain the existing correlated envelope. `result.outcome` is
`completed`, `rejected` (with a fixed policy error), or `handoff_pending`.
The latter acknowledges **durable local handoff only**, not runner admission or
execution. The control worker waits at most two seconds for a handoff response,
never for task completion. Use a fresh `work.status` request to observe later task
truth. An `unknown_task` response can mean the submit handoff is still pending;
query later rather than inventing a new task UUID. There is no unsolicited
completion notification.

Successful replies project only task UUID, payload hash, status, attempts,
cancellation flag, timestamps, terminal flag and terminal result metadata.
They expose no raw logs, patch contents, host paths, task request text or secrets.
Artifacts remain in the runner's private audit. A cancel response can show a
running task with `cancel_requested: true`; a later status confirms termination.

## Durable handoff and isolation

`/var/lib/personal-ai-brain/work-transport` is root-owned. Its two directories are
the **only** new mounts into control:

| Directory | Owner:group | Mode | Control | Builder |
|---|---|---|---|---|
| `inbox` | `1000:982` | `2750` | read/write | read-only |
| `outbox` | `999:1000` | `2750` | read-only | read/write |

Files are `0640`; setgid inheritance supplies the reader group. No new identity
or group membership is needed. The builder service gains only outbox write access
and a read-only inbox. It still cannot traverse control's private home/audit or
read its tokens. Control has neither builder state/workspace mounts nor the
builder publication credential. Sandboxes have neither transport mount; the
fixture checks this explicitly alongside the existing isolation checks.

Each message is at most 8192 bytes, with at most 2048 retained entries per
directory (including temporary files). UUID basenames are validated. Every path
component is opened without symlink following, directories are pinned by file
descriptor, reads accept only bounded regular single-link files, and publication
uses exclusive temporary files, fsync, no-replace linking and directory fsync.
A crash leaving a temporary link or malformed record fails closed; it is never
interpreted as permission to execute. Operators retain/reconcile evidence; there
is no automatic retention deletion. Disk exhaustion can leave a pending handoff.

The control request UUID identifies one transport invocation; its existing
reservation ledger still prevents reinvocation after worker interruption. The
handoff response binds that UUID to a canonical request hash. The runner task
UUID/payload hash remains execution authority. A crash after task admission but
before response persistence can repeat admission lookup, never execution; same
UUID/different payload remains rejected. Cancellation is safely repeatable;
status is a snapshot, not a subscription.

A single bounded receiver child in the builder systemd cgroup handles messages
while the single execution worker runs. This keeps cancellation responsive and
avoids threads around the sandbox resource-limit pre-exec hook. Existing fsync,
flock, interruption and cgroup cleanup semantics remain. No second executor or
queue framework is introduced.

## Deployment and acceptance boundary

The reviewed administrative `deploy/install_remote_work.py` installs the narrow
surface and builder modules only, refusing to interrupt active work. Then rebuild
only the existing control Compose project from the merged revision with its
existing state and secrets. Core and Media services are not redeployed. The
installer is not exposed through the control API and grants no sudo to builder.

Unit/integration tests cover duplicate/conflicting IDs, restart during handoff,
lost response after admission, cancellation races, independent validation,
malformed/symlink/hardlink/FIFO/oversized inputs and sanitized output. Existing
control tests cover all six original read capabilities. Live internal acceptance
must verify private Issues submit/status/cancel, artifacts and actual identity
boundaries after deployment. This is **not ChatGPT connector acceptance**.
External project-chat acceptance remains pending until Igor submits fresh
requests and verifies correlated worker comments and closure. Whole-host reboot
remains pending and outside this milestone.
