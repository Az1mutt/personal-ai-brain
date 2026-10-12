# Coding broker checkpoint — credentialless acceptance complete

2026-10-11. Continue on `feat/coding-agent-broker-v01` in
`/tmp/pab-coding-agent-preflight` on Homelab. The branch includes `83a54fe`;
final checkpoint SHA is reported in the handoff. Do not repeat reconciliation,
architecture or the completed credentialless acceptance.

Read current `AGENTS.md`, `.project/state.yaml`, `coding-agent-backend-v01.md`
and `credentialless-broker-acceptance.md`. No PR, push or merge has occurred.
Real API acceptance remains the milestone's merge gate. Project State is unchanged.

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

## Only remaining owner phase

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
4. Only after real internal acceptance complete administrative PR/CI/merge and
   deployment closure per AGENTS. Sync Project State then and prepare a fresh
   external ChatGPT coding submit/status handoff, explicitly still pending.

No GitHub publication capability belongs to task code. No builder PAT was used.
No real API success, external ChatGPT coding acceptance or whole-host reboot is
claimed. Media, planner/router/multi-agent work and other repositories are excluded.
