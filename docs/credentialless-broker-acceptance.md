# Credentialless broker deployment and isolation acceptance

Continuation of `83a54fe`, same Change/Review branch. No OpenAI project, API key,
billing change or real API request is permitted in this slice. On 2026-10-13 the
owner approved this credentialless foundation as a standalone mergeable milestone;
real provider acceptance is a separate gate. Project State must not claim real
model completion. Recovery, reconciliation and current validation are recorded in
`CODING_BROKER_CHECKPOINT.md`.

## Operator gate and acceptance adapter

The root-owned `/etc/personal-ai-brain/inference/operator.json` selects exactly
`disabled`, `acceptance` or `openai`; only root configuration selects a fixed
acceptance scenario. Task contracts cannot select the backend, scenario, model,
URL, headers or environment. The same runner `BrokerAgent`, authenticated Unix
socket, broker loop and filesystem mediation execute both provider adapters.
The stub requests list/read/search/apply_patch in sequence, then returns a proposal
completion. Independent root-owned sandbox tests determine success.

Acceptance usage is explicitly labelled synthetic in the ledger and artifacts;
it never consumes real-provider monthly reservations. UUID deduplication spans
both modes, so switching providers cannot replay an already used task ID.
The acceptance adapter is retained for controlled administrative verification,
never exposed as a public or task-selectable tool.

## Administrative deployment

`deploy/install_credentialless_broker.py` creates only the planned `pab-inference`
non-login identity with the existing IPC group. It reuses the installed Python
runtime, stages the reviewed root-owned source and offline seed, installs/enables
the broker unit and executes fixed acceptance via `credentialless_acceptance.py`.
It refuses to interrupt existing submitted/running work and keeps a root-private
backup of replaced runtime modules/profile. It never adds sudo/group privileges
to either service identity.

`deploy/owner_input.ps1 -Mode Bootstrap` opens a masked **sudo password** form.
It starts the fixed bootstrap through an administrative transient systemd job,
then closes SSH. The job and persistent services continue independently. Only
fixed flow status is retained on Windows. Neither password nor API key is a
command argument, environment variable, file or log entry. An API key field is
not shown in bootstrap mode.

Final acceptance evidence is boolean/typed JSON at
`/var/lib/personal-ai-brain/credentialless-broker-evidence.json`.
Failures record the stopped phase and gate new coding work off. Do not treat a
running form, queued job or active service alone as passed acceptance.

## Enforced and intentionally unclaimed network properties

The credentialless systemd drop-in sets `PrivateNetwork=yes` and
`IPAddressDeny=any`; even a mistaken OpenAI mode selection cannot make a real
request. `SocketBindDeny=any` denies explicit IP binds, while the broker exposes
only its fixed filesystem Unix socket. Root is the administrative trust boundary.

For eventual inference, the single root-owned acceptance procedure temporarily
removes the credentialless network drop-in. The real adapter then owns one fixed
verified HTTPS endpoint, rejects redirects and ignores proxy environment. IPC has
no URL/header/model selection. No hostname-level OS egress allowlist is claimed;
static OpenAI/CDN IP pinning would be brittle. Repository/test sandboxes retain
their separate network-free namespace and never see the broker socket or key.

## Prepared future key installer — do not run yet

Only after Igor deliberately configures the dedicated OpenAI project, model scope
and enforced USD 15 monthly project hard cap:

1. Run `deploy/owner_input.ps1 -Mode InstallKey` on the owner Windows session.
   Both sudo and key fields are masked. The SSH process first authenticates sudo;
   the key is sent over stdin only after the root installer emits its exact ready
   marker. Framing prevents confusing the password with the key.
2. The fixed installer validates every parent without following symlinks, verifies
   root-owned non-writable ancestors and broker-owned 0700 credential directory,
   and atomically installs a broker UID/GID 0600 regular single-link file. Existing
   unsafe targets are rejected. The key is never passed to tasks or shell parsing.
3. Record only scope/path/expiry or rotation date/owner in the single inventory.
   The API credential remains absent at the end of credentialless acceptance;
   the only installed test value is synthetic and is removed in `finally`.

The exact later **paid** test command, deliberately not executed in this slice:

```sh
sudo /usr/bin/python3 -B /tmp/pab-coding-agent-preflight/deploy/real_api_acceptance.py --owner-confirmed-project-hard-cap
```

It requires passed credentialless evidence, safe credential metadata and current
pricing policy. It persists one immutable acceptance task at
`/var/lib/personal-ai-brain/broker-live-acceptance-task.json` before submission.
Re-running reuses that UUID; it does not create another paid attempt. The task uses
the exact reviewed base/goal/criteria, deadline 180 seconds, USD 2 policy and the
tiny normalization module. It retains the patch and tests, never publishes GitHub
content, and restores disabled provider/network denial afterward. An interrupted
or failed paid attempt requires explicit review, not automatic regeneration.

After genuine API acceptance, that separate provider milestone's administrative
PR/CI/merge/deployment closure remains required. External ChatGPT coding acceptance is still independent
and pending. Media, reboot, planner/router and additional repositories are excluded.
