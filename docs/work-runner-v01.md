# Work Runner v0.1 — durable local execution

This milestone implements the local execution boundary from
[the Builder Execution Plane](builder-execution-plane.md). It has one deterministic
fixture, one worker and an administrative local CLI. It has no model backend,
remote submission adapter, GitHub publisher, deployment handler or Media behavior.

## Work Contract

The entire request is at most 8192 UTF-8 bytes. Exactly these fields are required;
unknown fields, duplicate JSON keys and nonfinite numbers are rejected.

```json
{
  "schema_version": "0.1",
  "task_id": "REPLACE_WITH_CANONICAL_LOWERCASE_UUID",
  "task_type": "fixture.patch-test.v1",
  "repository": "Az1mutt/personal-ai-brain",
  "base_ref": "71f0d82516d059ba2d65e028742cd73b2b9ee6bc",
  "goal": "Create the deterministic Work Runner fixture artifact.",
  "acceptance_criteria": ["fixture content matches", "isolation checks pass"],
  "requested_at": "REPLACE_WITH_CURRENT_RFC3339_TIMESTAMP",
  "deadline_seconds": 20
}
```

The placeholders are invalid until replaced. Deadline is an integer 1–60 seconds
covering preparation and execution. New requests must be at most seven days old
and no more than five minutes in the future. Repository, type, goal and criteria
are fixed in v0.1. The root-owned profile allows exactly one immutable base SHA;
it is an offline repository snapshot, not a moving remote branch. No command,
environment, URL, filesystem path, script, credential or dependency instruction
can be supplied in a task. Text fields cannot redefine what success means.

The fixture waits five seconds, creates `builder-fixture.txt` with the exact text
`Personal AI Brain Work Runner v0.1` plus newline, and runs fixed isolation checks.
It deliberately starts a harmless detached sleeper to verify namespace cleanup.
It executes trusted installed fixture code; it does not execute repository code.

## State and recovery

`submitted -> reserved -> running -> succeeded | failed | cancelled | interrupted`;
admission/resource rejection can yield `blocked`. A queued task can be cancelled
without being reserved. Cancellation is a durable flag and wins over a concurrent
success transition. Every transition records a timestamp and bounded code.

Canonical payload SHA-256 plus UUID is the idempotency key. An identical duplicate
returns the existing record, including after completion; a changed payload under
the same ID is rejected. There is no implicit second attempt. A new UUID represents
a new explicitly requested operation. Do not remove task records to clean logs.

Each record is written to a private temporary file, fsynced, atomically renamed
and its directory fsynced. A shared state flock serializes admission/cancellation;
a separate lifetime worker flock permits only one executor. Corrupt records fail
closed. On service restart, `reserved`/`running` becomes `interrupted`, with no
replay. Untouched `submitted` tasks remain queued. systemd clears the service
cgroup before restarting the supervisor.

Admission preallocates 128 KiB emergency space per task before acknowledgement.
Insufficient free space blocks execution. An execution-time storage error releases
that reserve to record failure. If the device remains unwritable, the last durable
nonterminal record remains the truth and the service fails closed; recovery cannot
infer success or retry. An interrupted admission directory is retained and the ID
is refused until operator reconciliation. Capacity is bounded to 256 retained task
records; there is no automatic deletion or ledger rollback.

Terminal artifacts are fsynced before terminal task state is committed. A crash
between artifact publication and the state commit produces `interrupted` on
recovery, even if a tentative artifact suggests completion. The state record is
authoritative. Side effects are local; no external mutation is retried.

## Runtime and isolation

`personal-ai-brain-builder.service` runs as the non-login `pab-builder` account,
with only its primary group and no sudo, Docker or LXD membership. Its Python venv
has no downloaded dependencies; runner modules use the standard library only.
The root-owned release and policy cannot be edited by the service or tasks.
The unit starts at boot, restarts on failure, uses `KillMode=control-group`, a
private network/home boundary, read-only system paths, no capabilities and
no-new-privileges. It limits memory to 256 MiB, tasks to 64 and CPU to one core.

The unit intentionally does not use systemd's `ProtectKernelTunables` or
`ProtectKernelLogs` proc submount masks: the actual service-identity probe showed
that Linux then refuses Bubblewrap's nested private proc mount. The sandbox gets
its own read-only proc mount instead. The supervisor has no root identity or
capabilities to modify host kernel settings. No global AppArmor/user-namespace
policy was disabled. This compatibility choice preserves task PID isolation.

Each task gets an independent Git clone with its own object store and
`builder/<UUID>` branch, no remotes or shared writable Git metadata. The root-owned
seed is local. No runtime network fetch, dependency installation or credentials
are needed. Workspaces and failure artifacts are retained.

Bubblewrap creates fresh user, mount, PID, IPC, UTS, network and supported cgroup
namespaces. User namespaces are explicitly requested and further nesting is
disabled. Inside the sandbox the fixture uses non-root UID/GID 65534 with zero
effective capabilities. It sees only the current repository (Git metadata mounted
read-only), the installed read-only fixture, the Python interpreter/stdlib/shared
libraries, private proc/dev, and disposable home/tmp. It receives no host home,
state root, credential path, sockets or other task mount. The environment and file
descriptors are sanitized. There is no general shell entrypoint in the contract.

The supervisor bounds captured output to 16 KiB, enforces the deadline, kills the
sandbox process group and waits for exit. PID-namespace teardown removes detached
children; systemd's cgroup cleanup covers supervisor crashes. File size per sandbox
file is limited to 1 MiB, open descriptors to 64, and core dumps disabled. This is
a fixed-fixture boundary, not approval to run arbitrary unreviewed programs.

Artifact collection accepts only the fixed regular output file with exact size
and contents and rejects symlinks/FIFOs. The patch is generated from verified data;
collection never executes task-supplied Git hooks, config or filters. All declared
isolation checks must be present and true before success is recorded.

## Paths and operations

| Purpose | Location |
|---|---|
| Root-owned runtime and venv | `/opt/personal-ai-brain/builder/` |
| Root-owned offline Git seed | `/opt/personal-ai-brain/builder/repository.git` |
| Root-owned profile | `/etc/personal-ai-brain/builder/profile.json` |
| Durable task truth | `/var/lib/personal-ai-brain/builder/state/tasks/<UUID>.json` |
| Private workspaces | `/var/lib/personal-ai-brain/builder/workspaces/<UUID>/repo/` |
| Private review artifacts | `/var/lib/personal-ai-brain/builder/audit/<UUID>/` |
| Service lifecycle | systemd journal for `personal-ai-brain-builder.service` |

Artifacts are `execution.log`, `patch.diff`, `test-result.json` and `result.json`.
Directories default to 700 and records/artifacts to 600. No transport inbox/outbox
is needed yet. No credentials are installed under the builder service root. The
separate administrative GitHub credential stays at its existing inventoried path.

An administrator bootstraps with `deploy/install_work_runner.py` after reviewing
the source and preparing the fixed local seed bundle. Bootstrap sudo is not a
runner permission. Re-running the installer refuses unrecognized existing release
paths/identity groups and preserves state; it stops/restarts only this new service.
The acceptance harness is an administrative test script, not a service API.

Local submission uses the installed module under the service account:

```sh
sudo -u pab-builder env PYTHONPATH=/opt/personal-ai-brain/builder/src \
  /opt/personal-ai-brain/builder/venv/bin/python -B \
  -m personal_ai_brain.work_runner submit < task.json
```

Use the same prefix with `status <UUID>` or `cancel <UUID>`. Operators may use
`systemctl status/restart personal-ai-brain-builder.service` for recovery. Task
execution continues independently after the submitting session ends. Submission
itself is local administrative access; no ChatGPT/control bridge capability is added.

## Acceptance evidence

Offline tests cover malformed/unknown contracts, payload conflicts, concurrent
admission, cancellation races, restart recovery, worker locking, corrupt/orphaned
state, low-space rejection, injected ENOSPC, terminal-write failure, deadlines,
output limits and symlink-safe collection. Live acceptance runs under the actual
systemd service identity and records UUIDs and boolean evidence, never credentials.

Verified 2026-10-10 under service UID 999 / GID 982, with group membership exactly
982. All 153 Linux tests passed (125 existing plus 28 Work Runner cases).

| Live check | Durable task reference / result |
|---|---|
| Success, valid patch, all 17 isolation checks | `72cc4388-68eb-4963-91f3-68719ead9653` — succeeded |
| Identical duplicate and conflicting payload | Same successful task: no second execution; conflict rejected |
| Deadline and process cleanup | `14b6f288-fd5b-49dc-aa06-af9b9bb2e8b6` — failed/deadline |
| Cancellation | `599f2607-d973-4757-be40-d848fa13f79e` — cancelled |
| Graceful service restart | `c9170aa8-79f4-41ac-afd8-f7261e195cc9` — interrupted, no retry |
| Supervisor SIGKILL and cgroup cleanup | `51de2fb3-4992-4387-b158-b7c76f55826c` — interrupted, no retry |
| Injected fixture failure retains workspace/log/result | `7790ab48-c491-43c0-a6c9-b2f43c7b453c` — failed |
| Live low-space admission guard | `e31d636e-2375-44fd-ad99-484429dccc0d` — blocked without workspace execution |
| Task continues after originating SSH exits | `d80668f9-6bc4-4385-954f-d88d79945878` — succeeded at `2026-10-10T19:22:44.732Z`, read via a fresh SSH session |

Normal completion and interruption left only the supervisor in the service cgroup;
the detached fixture child did not survive. The service is enabled at boot. Initial
failed sandbox compatibility probes remain as failed evidence; they were not retried
under the same task IDs. A live SIGTERM/child-exit race was corrected and covered
by a regression test before the successful final acceptance run.

Reboot testing remains explicitly pending on this shared Homelab;
enabled-at-boot plus service restart is not a
claim that a whole-host reboot was exercised. No production workload is rebooted
to close this milestone. Low-space acceptance raises the private admission
threshold; it does not fill the shared host disk. Actual ENOSPC is injected in
offline tests and is reported separately from that live guard test.

## Remote Work Submission v0.1 integration

The subsequent approved milestone adds a narrow filesystem handoff from the
existing private Issues control transport. The original local-only statements
above describe v0.1 before this integration. See
[Remote Work Submission](remote-work-submission-v01.md). Runner state, artifacts,
fixture allowlist and execution idempotency remain authoritative. A bounded
receiver child handles submit/status/cancel concurrently with the single executor;
task sandboxes gain no transport mount, network or credential access. The fixture
now also verifies transport absence (18 checks including the original 17).
