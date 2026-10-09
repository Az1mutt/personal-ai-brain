# Builder Execution Environment Reconciliation

Verified 2026-10-10 Europe/Bratislava (2026-10-09 22:xx UTC). Architecture proposal;
no builder identity, service, credential, permission or deployment was created.
Media remains parked and is excluded from builder scope.

## Verified current map

The authoritative source is `Az1mutt/personal-ai-brain`, default branch `main`,
verified at `828f9ce`. Its current AGENTS policy and `.project/state.yaml` were read
after fetching. The initial Homelab checkout was seven commits behind: its old
pending ChatGPT gate is superseded by recorded acceptance in private Issues #28–29.
The current state explicitly parks Media. Historical acceptance evidence was reused;
no duplicate live control probes or Media operations were performed.

| Area | Observed state and purpose |
|---|---|
| Host / identity | Ubuntu 26.04; `az1mutt` UID/GID 1000 is the only ordinary login in passwd. Groups include `sudo`, `docker`, `lxd`, `adm`; it is an administrator, unsuitable for coding execution. No dedicated builder account exists. |
| Core | `personal-ai-brain-core-1`, image `personal-ai-brain:local`, healthy, detached, restart `unless-stopped`. UID/GID 1000:1000, read-only root, all capabilities dropped, no-new-privileges, no privileged mode or Docker socket. |
| Control | `personal-ai-brain-control-control-1`, image `personal-ai-brain:control`, same restrictions and restart policy; healthy. Separate Compose project. Its six bounded read-only capabilities and private Issues result transport are already accepted. |
| Persistence | Docker is enabled at boot. Core/control were running for two weeks during inspection. This confirms detached operation, not a newly tested whole-host reboot. |
| Source/deployment checkout | `/home/az1mutt/projects/personal-ai-brain`, clean `main` at `a38bb01`; Compose working directory for both services. Its `.venv` is an editable development environment. Source HEAD and running image identity must be recorded separately. |
| Other platform worktrees | `projects/media-control-v04b` (`feat/media-control-v04b`); `projects/worktrees/tautulli-reconciliation-runner` (`feat/tautulli-reconciliation-runner`); `watched-event-ledger-v01` (`feat/watched-event-ledger-v01`); `watched-event-ledger-github` (detached). These share the platform repository. Retained Media development/acceptance artifacts; not builder workspaces. Dirty status/deletion safety was not audited. |
| Other checkouts | `/data/agents/homelab-infrastructure` has a clean tracked main. `/data/agents/trading-intelligence-platform/` contains five independent `.git` directories: `mvp-data-foundation`, `mvp-api-surface`, `mvp-market-context`, `mvp-llm-planner`, `mvp-trade-plan-risk`. The last is the running trading API's Compose directory. These are outside the initial builder allowlist. |
| Existing runtime boundaries | Rootful host Docker serves Core/control and other workloads. Trading API is also non-root/read-only, with persistent `/data/agents/trading-intelligence-platform/data`. Media containers and `/data/agents/movie-intelligence` were identified by name only; no domain inspection or changes. |
| Python | Host and platform `.venv`: Python 3.14.4; venv includes pytest 8.4.2, PyYAML 6.0.3 and editable platform 0.1.0. Existing CI uses Python 3.12; do not equate host tests with CI compatibility. |
| Other tools | Git 2.53.0, Node 22.22.1, npm 9.2.0 (global package list empty), Compose 5.5.0, systemd 259, Bubblewrap 0.11.1. No `gh` or `codex` executable in the inspected login PATH; no platform user service or installed coding backend identified. |
| Sandbox feasibility | Installed `/usr/bin/bwrap` is root-owned mode 755. A harmless process ran with private user/PID/network namespaces, exit 0. Direct `unshare` failed under the host's restricted user-namespace policy. Bubblewrap success under the administrator login is only a feasibility check; the future service identity/profile still requires acceptance. |

Core state: `/home/az1mutt/.local/state/personal-ai-brain/runtime`, mounted writable
at `/state`; control sees it read-only at `/core-state`. Control audit/deduplication:
the sibling `control` directory, writable at `/control`. Both host directories are
700; sampled heartbeat/status files are 600, owned by az1mutt. Existing
`acceptance-*`, `runtime-probe`, `control-auth-probe` and `media-pilot` directories
are retained evidence, not additional live builder state. Never clean the control
ledger as if it were disposable logs.

Git origin is credential-free HTTPS to the public platform repository. Repository
author is `Az1mutt <55916200+Az1mutt@users.noreply.github.com>`. No configured Git
credential helper, SSH command or commit signing setting was found. Standard
`~/.git-credentials`, `~/.gitconfig`, `~/.config/gh` and `~/.codex/auth.json` paths
were absent. The sampled session had no forwarded SSH agent, Git askpass, GitHub
token environment variables or OpenAI API key. Public fetch succeeded; this proves
read access, not Homelab GitHub write authentication or the absence of secrets
elsewhere. The connected GitHub app has repository write/admin authorization;
that external session is not a Homelab runtime credential.

Administrative SSH uses the Windows `homelab` alias, user az1mutt and dedicated
`id_ed25519_homelab_codex`, with `IdentitiesOnly yes` and agent forwarding disabled.
The Windows key ACL allows its owner, SYSTEM and Administrators. Host `.ssh` is
700 and `authorized_keys` 600. Core and control tokens are distinct files, 600,
inside a 700 directory; live mount metadata confirms read-only file injection,
not token values in container configuration. The prior control acceptance proved
Issues access and private Contents denial; token expiry and current granted scopes
were not re-queried. See the single [credential inventory](credential-inventory.md).

The remaining laptop dependency is the builder itself: Codex reasoning, administrative
SSH commands and source transfer are initiated from Windows. The current Windows
workspace is staging scripts/bundles, not the platform repository. No VS Code server
was found in the bounded home inspection; VS Code is not required by Core/control.
Long-lived services already survive SSH disconnect; coding work has no equivalent
persistent worker, durable task contract or independent model authentication.

## Duplication and ambiguity

- Deployment source doubles as a development checkout and contains stale policy/state.
  Updating the checkout must not implicitly rebuild/restart services.
- Retained domain worktrees and trading milestone clones have distinct historical
  purposes but no common task lifecycle. Do not adopt them as the new workspace pool
  or delete them without their owners' checks.
- Administrator UID 1000 is reused by bounded containers; a non-root UID by itself
  does not make that same host login safe for autonomous coding.
- Credential purposes are documented in separate runtime pages; the inventory below
  becomes the metadata authority. Unknown expiry/scope remains explicitly unknown.
- `docs/arhitecture.md` is already a redirect to `architecture.md`, not a second
  architecture authority. No cleanup is necessary for this milestone.

## Canonical target: systemd supervisor plus per-task Bubblewrap sandbox

Use one new non-login system account `pab-builder` (allocate an unused UID/GID at
implementation), with no sudo, docker, lxd or administrative groups. An
administrator-installed system service `personal-ai-brain-builder.service` runs a
small Python supervisor as that account, starts at boot and restarts on failure.
SSH is used only to install, administer and recover it. Reuse installed systemd,
Python, Git and Bubblewrap; no second container engine, framework, database or queue.

The supervisor is trusted policy code, not an LLM shell. Its released code and
repository/test policy are root-owned and not writable by the service or tasks.
It accepts typed tasks for exactly `Az1mutt/personal-ai-brain` initially. No caller
may supply a shell command, host path, arbitrary URL, image or credential reference.
The existing control worker continues using its own token and ledger; a later
bounded submit/status adapter may pass task envelopes/results through a dedicated
inbox/outbox. Never mount builder credentials into control or expose execution as
a generic control capability. `requested_by` remains audit metadata, not authority.

Run one task at a time initially. Each task gets a fresh standalone repository
workspace with private Git metadata, task-specific HOME/temp, and a unique
`builder/<task-uuid>` branch from a recorded allowed base SHA. A read-only supervisor
cache may reduce transfer, but task clones must have independent objects/config
(no shared writable Git directory or writable hardlinks). This deliberate task
copy is isolation, not another manually maintained checkout. Deny submodules,
external Git filters/hooks, caller-supplied remotes and repository-local execution
configuration unless separately reviewed.

Bubblewrap exposes only the current task workspace as writable plus ephemeral
HOME/temp and a reviewed read-only runtime/dependency set. Use separate mount,
user, PID, IPC and network namespaces, drop capabilities, no-new-privileges,
sanitized environment/file descriptors and process-tree termination. Do not bind
the host root/home, `/run`, Docker socket, supervisor state, credentials, other
tasks, production volumes or Core/control state. The sandbox must not retain the
supervisor's supplementary groups or host IPC endpoints. Local commands/tests are
allowed inside this boundary; default task networking is disabled. No sudo/root
host privileges or deployment path exists for task code.

Use systemd resource/process controls, a hard task deadline and bounded output;
terminate the complete sandbox before sealing or reusing task results. Test service
hardening together with Bubblewrap on this host: do not globally disable AppArmor
or namespace restrictions to make it work. Fail closed if isolation cannot start.
The [Bubblewrap security model](https://github.com/containers/bubblewrap) makes the
launcher responsible for the actual policy; the probe is not a security acceptance.
[systemd execution controls](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
provide the service boundary. Neither tool alone is the complete builder policy.

| Purpose | Canonical proposed host location / ownership |
|---|---|
| Released supervisor/runtime | `/opt/personal-ai-brain/builder/` — root-owned read-only release and one isolated venv; do not use az1mutt's editable venv as a daemon runtime |
| Policy and credential references | `/etc/personal-ai-brain/builder/` — root-managed repo/test profiles; credential references only in config |
| Future secret files | `/etc/personal-ai-brain/builder/credentials/` — restricted supervisor access, never mounted into coding/test sandboxes |
| Repository cache | `/var/lib/personal-ai-brain/builder/repos/` — supervisor-only, optional after correctness |
| Task workspaces | `/var/lib/personal-ai-brain/builder/workspaces/<task-uuid>/repo/` — only current task exposed writable |
| Mission/task truth | `/var/lib/personal-ai-brain/builder/state/` — supervisor-only atomic records, reservations, locks and result-delivery state |
| Private artifacts/audit | `/var/lib/personal-ai-brain/builder/audit/<task-uuid>/` — sealed results, patch, base/head SHAs, tests, bounded redacted logs; systemd journal for lifecycle |
| Transport handoff | `/var/lib/personal-ai-brain/builder/transport/` — narrowly separated inbox/outbox; never an arbitrary file-execution spool |

All new persistent private roots default to 700/files 600. A later transport
adapter gets only the minimum handoff-directory access, not the builder state root.
Task artifacts are untrusted: reject symlinks/path escapes and enforce size limits
when collecting. Do not let task-written JSON redefine supervisor truth. Collection
and later publication must not execute task-modified Git hooks, configuration or
filters; import validated output into supervisor-controlled Git metadata instead.

Use standard-library atomic JSON plus fsync/rename and a single flock. Persist
request UUID + canonical payload hash before execution; same ID/different payload
is rejected. Record queued, running, succeeded/failed, interrupted and cancelled
states, attempts, base/head SHA, policy version and test outcomes. Restart marks
running tasks interrupted, preserves their workspaces and never blindly replays
them. Retry/resume requires an explicit linked attempt. Result delivery has a
separate retry state; retries reuse the sealed result. Preserve deduplication
records independently of log retention. Disk-full must fail before execution.

Dependencies/tests run locally using reviewed pinned environments. Existing host
Python 3.14 can support initial host tests; a Python 3.12 CI parity run remains a
separate gate until a matching runtime is deliberately provided. Do not blindly
install repository dependencies with network/credentials available. The first
runner accepts deterministic patch/test fixtures, not an installed LLM backend.
Later model access needs its own provider credential and narrowly brokered egress;
no copying a laptop login or exposing a general Internet proxy to task code.

Git writes remain disabled. Later use a short-expiry, repository-selected
fine-grained GitHub credential for Contents and Pull requests only, no workflow,
administration or deployment permission. Keep it in a trusted publisher outside
the coding sandbox; never reuse Core, Issues, SSH or model credentials. Its adapter
accepts only an approved sealed task artifact and the permitted branch prefix;
deny protected branches, workflow changes and arbitrary HTTP/Git commands. A GitHub
App can replace this credential provider later without changing the task contract.
Record owner/scope/expiry before enabling it; repository branch protection and
publisher validation must enforce limits a PAT cannot express by branch.

Branch lifecycle: reserve task ID and branch, record the base, preserve patch and
tests, later publish a review PR, merge only under the approved review policy, then
verify merge before deleting branch/workspace. Failed/interrupted tasks retain
artifacts for bounded operator retention; do not auto-delete unmerged work.
Initial runner produces local review artifacts only and records cleanup status.

## Migration and exact next milestone

1. Keep existing Core/control and administrator checkouts in place. Land this
   documentation through the Change/Review lane; do not rebuild services.
2. **Work Runner v0.1: durable local task execution, no GitHub writes or LLM.**
   Implement the account/service, reviewed sandbox launcher, fixed platform repo
   profile, single-worker task state machine, isolated workspace and patch/test
   artifact output described above. Administrative bootstrap provisions them once.
3. Prove a submitted deterministic coding fixture completes after SSH disconnect;
   prove service restart and reboot preserve task truth. Exercise duplicate IDs,
   payload conflicts, cancellation, deadlines, full-disk failure and interrupted
   child cleanup. Prove tasks cannot read credentials, other workspaces, production
   state or host sockets, mutate supervisor policy/audit, access the network or
   retain background processes. Re-test Bubblewrap under the actual service identity.
4. Only after that gate, add bounded remote submit/status through the existing
   accepted transport, with explicit coding authorization distinct from read-only
   health requests. Verify ChatGPT-originated submission and correlated results.
5. Select and authenticate a headless coding backend in a separate milestone.
   GitHub publication is another explicit gate with its own narrow credential and
   PR/branch lifecycle acceptance. Production deployment and Media stay excluded.

The next milestone is complete when an isolated local patch/test task survives
session loss and produces durable review artifacts under the constrained identity.
It does not yet remove the relay for every coding request: remote task intake,
model execution and PR publication are explicit subsequent steps. No host cleanup,
new credential or permission expansion was necessary for this reconciliation.

