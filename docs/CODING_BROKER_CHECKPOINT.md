# Coding broker checkpoint — credentialless acceptance complete

## Current integration and milestone decision — 2026-10-13

Closure on 2026-10-14: PR #19 merged as
`1d0275e02a9dcf920381fed7f83b9232da1f3a11`; its tree equals tested PR head
`75a53e4fc6ccddb058fffbbd20e5f28f2f0f88bc`. GitHub Actions run `38547344327`
passed Python tests and offline Codex environment checks. A fresh read-only live
check confirmed unchanged source, receipt, isolation and disabled gates.

Credentialless Coding Agent Broker v0.1 is approved as a standalone foundation
milestone. Real Ollama/OpenAI acceptance is not its merge gate. Runtime gates
remain disabled; no real provider, router, autonomous publisher or deployment
automation is accepted by this milestone.

Exact checkpoint `c3df34fef37df23711b94751255e9ea482c75779` was recovered from the
clean Homelab linked worktree `/tmp/pab-coding-agent-preflight`, owned by the
Personal AI Brain common Git directory. Its direct parent is `83a54fe` and its
recorded base is `cde8c424b687c3ef99b98e4764da4a67c973d8b2`. Complete-history
bundles and local `recovery/coding-agent-broker-c3df34f` preserve that exact history.

Integration starts at main `667a6ef4ded87d65a8e3d920e7c6898f4dac0efe` on
`feat/coding-agent-broker-v01-integration`. The original documentation prerequisite
`9268c25` and broker commits `83a54fe`, `c3df34f` replay as `6746350`, `51c9386`,
`06e12a5`. All three range-diff entries are equal; no conflicts or implementation
changes occurred. Current-main environment, policy, CI and state changes remain.

Validation: 235 Linux tests passed; the count matches recovery because main added
separate PowerShell environment checks, which also passed. Whitespace checks and
a bounded tracked-secret scan passed. Read-only live revalidation confirmed all
17 installed broker/runner modules and the broker unit match after the historical
transfer's text/trailing-whitespace normalization, with root-owned non-writable
modules. The stored acceptance receipt matches committed evidence. Builder and
broker are active/enabled with private networks, no new privileges and empty
capability bounds. Broker IP deny-all remains effective; provider and coding gates
are disabled. No deployment, restart, new inference or destructive acceptance
probe was needed. Historical identity/sandbox evidence below is reused, not
represented as freshly rerun. The checkpoint date below predates the final commit,
which was created on 2026-10-12.

Next milestone: **Local LLM Provider v0.1 — Ollama feasibility and real coding
acceptance**. Paid OpenAI acceptance and external ChatGPT coding acceptance remain
separate pending work. Prepared owner credential procedures are retained.

## Historical checkpoint — 2026-10-11/12

Read current `AGENTS.md`, `.project/state.yaml`, `coding-agent-backend-v01.md`
and `credentialless-broker-acceptance.md`. At this checkpoint no PR, push or merge
had occurred and Project State was unchanged. Its former real-API merge gate is
superseded by the foundation milestone decision above.

## Verified live state

- `pab-inference`: UID 995, primary/only group 982, `/usr/sbin/nologin`,
  `/nonexistent` home; no sudo, Docker/LXD or production deployment grant.
- `personal-ai-brain-inference-broker.service`: active and enabled, independent
  of originating SSH. The owner-authenticated transient bootstrap detached from
  SSH and completed the full live matrix afterward.
- All 15 actual broker identity/namespace probes passed. Builder could not read
  the synthetic credential installed at the future real-key path. Unrelated
  az1mutt/nobody/broker identities could not invoke the builder-only interface.
- Success task `5cca73a9-a64a-4534-9f2a-6f8dc7c07050` traversed local durable handoff,
  real Work Runner, authenticated Unix broker, stub adapter, all four mediated
  tools, deterministic validation and offline tests. Patch/artifacts retained.
- Nine coding sandbox checks passed, including no key/socket, other workspace,
  Docker, network, root or capabilities. The 13 code checks passed.
- Live provider failure, malformed response, escape attempt, failed code tests,
  exhausted task budget, IPC loss, deadline, cancellation, broker restart,
  runner restart, unavailable broker, duplicate/conflict and child cleanup passed.
- Existing fixture `cb43ebb3-e3cd-4d69-862d-4cedad73750e` succeeded with all 18 checks.
- Synthetic production-path key installation validated UID/GID/0600; sentinel
  removed. No real API credential exists. No paid/model API request was made.
- Final offline regression suite: 235 tests (verify final handoff result).
  Systemd unit syntax and deployment Python syntax passed.
- Two real integration defects were fixed with regressions: restore Python
  socket timeout after multiprocessing spawn; share Abort class across the
  runner module entrypoint and coding adapter.

Typed evidence: `credentialless-broker-evidence.json`, copied from
`/var/lib/personal-ai-brain/credentialless-broker-evidence.json`. Earlier failed
attempts remain retained; they were not silently replayed or erased.

## Deliberately gated resting state

Operator config `/etc/personal-ai-brain/inference/operator.json` has provider
`disabled`. Builder profile has `coding_enabled=false`. The root-owned
`credentialless.conf` broker drop-in keeps `PrivateNetwork=yes` and
`IPAddressDeny=any`; IP socket bind denial remains in the main unit. Existing
fixture/control services remain available. The inference credential file is absent.

Runtime/seed are root-owned at the existing builder prefix; state remains under
`/var/lib/personal-ai-brain`. The root-private bootstrap backup is
`/var/lib/personal-ai-brain/credentialless-bootstrap-backup`. No additional repo,
LLM framework, persistent administrative control channel or privileged agent was
introduced. The one-time root systemd bootstrap job was collected after exit.

## Deferred OpenAI owner phase

The owner deliberately postponed OpenAI setup. Do not ask for a key now.
When the owner chooses to proceed:

1. Configure the dedicated Personal AI Brain OpenAI project, project-scoped
   service account, restricted Responses inference permission, only `gpt-6.1-sol`,
   and an **enforced USD 15 monthly project hard cap**. Record rotation date.
   No organization billing modification is automated.
2. Use the reviewed `deploy/owner_input.ps1 -Mode InstallKey` visible masked form.
   It sends the key only over SSH stdin after the privileged installer's ready
   handshake; no value in chat, command arguments, logs or repository files.
   Update only inventory metadata. Do not improvise another transfer.
3. Execute the exact future paid acceptance procedure from
   `credentialless-broker-acceptance.md`. It preserves one task UUID, uses USD 2
   task policy/180-second deadline, retains the sealed patch/test/result, then
   restores provider/network denial. Re-running cannot create another paid task.
   Pricing policy expires closed after 2026-11-10 and needs review after that date.
4. After real internal acceptance complete that separate provider milestone's
   administrative PR/CI/merge and deployment closure per AGENTS. Sync its state and prepare a fresh
   external ChatGPT coding submit/status handoff, explicitly still pending.

No GitHub publication capability belongs to task code. No builder PAT was used.
No real API success, external ChatGPT coding acceptance or whole-host reboot is
claimed. Media, planner/router/multi-agent work and other repositories are excluded.
