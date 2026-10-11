# Coding Agent Backend v0.1 — trusted inference broker

Owner-approved Responses broker decision, 2026-10-11. Implementation checkpoint,
not production or live-model acceptance. Codex CLI and self-hosted Agents are not
used. No framework or dependency added. Project State still records the last
verified remote-fixture milestone.

## Boundaries and paths

The existing `pab-builder` supervisor owns admission, disposable Git checkout,
four validated filesystem operations, deterministic patch validation and offline
tests. `CodingAgent.run(task, workspace, guard, progress)` separates that lifecycle
from the provider. The separate proposed non-login `pab-inference` identity owns
only inference. It uses the existing root-owned Python runtime; no sudo, root,
Docker, GitHub/Core/control/SSH credentials or publication/deployment API.

| Authority | Canonical reference |
|---|---|
| Reviewed runtime | `/opt/personal-ai-brain/builder/src/personal_ai_brain` and existing stdlib venv |
| Broker unit | `deploy/personal-ai-brain-inference-broker.service` (not installed) |
| Broker IPC | `/run/personal-ai-brain-inference/broker.sock`, directory 0750, socket 0660, broker UID / existing builder GID |
| Inference ledger | `/var/lib/personal-ai-brain/inference`, broker-owned 0700, records 0600 |
| Credential | `/etc/personal-ai-brain/inference/credentials/openai-api-key`, broker-owned 0600, enclosing credentials directory 0700; absent |
| Existing runner state/artifacts | `/var/lib/personal-ai-brain/builder/{state,workspaces,audit}` unchanged |
| Coding offline seed | `/opt/personal-ai-brain/builder/coding-repository.git`, root-owned, absent until reviewed bootstrap |

Broker accepts only the actual `pab-builder` UID via `SO_PEERCRED`; runner checks
the `pab-inference` peer UID. No TCP listener. Socket and credential are absent
from task mounts. Broker receives task text and mediated file responses, never a
workspace mount. The service template masks host `/etc`, `/var/lib` and `/run`,
reintroducing only broker state/socket/credential and DNS/TLS/account dependencies;
home, devices, capabilities and process visibility are constrained separately.
Actual systemd namespace validation remains required before enablement.

## Reviewed first coding profile

`coding.patch-test.v1` uses the existing version 0.1 field set and the sole
repository `Az1mutt/personal-ai-brain`. Its exact approved base is
`cde8c424b687c3ef99b98e4764da4a67c973d8b2`. Fixture base and behavior are unchanged.
Coding deadline is 1–180 seconds. The operator profile must explicitly set
`coding_enabled: true`; otherwise admitted coding work becomes blocked without
contacting the broker. The production profile has not been changed.

The first profile is deliberately one real, small coding exercise. Exact goal:
`Implement the reviewed label normalization exercise.` Exact criteria list:
`["Normalize Unicode whitespace and case; reject nonstrings."]`.
Only a new `src/personal_ai_brain/coding_exercise.py` may change. It must define
`normalize_label(value)`: collapse Unicode whitespace, casefold, and raise
TypeError for nonstrings. Other goals are rejected so fixture tests cannot falsely
validate unrelated acceptance criteria. Broad coding is a later profile review.

Tools are `list_files`, `read_file`, literal `search_text`, and `apply_patch` with
exact `{path, old, new}` replacement (old must match once, empty old creates a new
file). No shell, model test commands, URLs, environment, provider or runtime flags.
Paths are relative, non-hidden and bounded; component walks use `O_NOFOLLOW`.
Read limits are 16 KiB, edit limit 8 KiB, file inventory 256 entries. Symlinks,
hardlinks and traversal are rejected. Whole-workspace hashes include Git metadata;
only the approved new file may differ. A narrow AST allowlist excludes imports,
dynamic execution, loops, decorators and executable annotations.

After reasoning ends, a root-owned harness runs 13 independent input/type checks
through the unchanged Bubblewrap launcher. No model process runs inside it.
The sandbox retains private network/PID/user namespaces, UID 65534, no capabilities,
no credentials/socket/other workspaces and no unrestricted host filesystem.
Tests have memory/CPU/output/deadline bounds; namespace processes are reaped.
The supervisor checks workspace hashes again after tests. Model prose is discarded
and cannot declare success. No repair iteration is enabled.

## Provider, money and interruption truth

Root-owned policy: `gpt-6.1-sol`, medium reasoning, fixed
`https://api.openai.com/v1/responses`, standard service tier, `store=false`, four
custom tools, at most 8 turns, 4096 output tokens/turn, 48 KiB serialized request,
256 KiB response. Proxies and redirects are disabled; TLS verification stays on.
No automatic retries. Reasoning/encrypted history exists only in broker RAM.

Before each request the ledger fsyncs USD 0.25 reservation. Eight reservations
exhaust USD 2/task; a separate USD 15/calendar-month local reservation cap spans
tasks. Unknown outcomes retain their full reservation. Usage records project only
integer input/output tokens and conservative estimated cost, never provider text.
The reviewed standard price is USD 2/M input and 10/M output; estimates use 3/11
micro-USD per input/output token to cover cache-write/regional headroom. A 48 KiB
request plus 8192 token framing allowance and 4096 output tokens fits the 0.25
reservation under that conservative byte/token assumption. This is a local bound,
not a provider billing guarantee. Pricing expires closed after 2026-11-10 and must
be reviewed again. The owner's independently enforced project USD 15 hard cap is
mandatory before live use; enforcement can slightly overshoot during propagation.

Broker reserves each task UUID once. Existing UUIDs never initiate another paid
attempt, including after crash. Runner preserves existing duplicate/conflict truth.
One broker child owns the current HTTP interaction; socket disconnect, deadline
or service stop terminates and reaps it. Broker recovery marks uncertain records
interrupted without replay. Runner restart similarly preserves interrupted truth.
No automatic ledger pruning; 256-record cap requires operator reconciliation.

Artifacts: existing `result.json`, `test-result.json`, `patch.diff`, plus bounded
`agent-result.json` (policy/model/timestamps/usage/verified changed files), fixed
`agent.log`. Valid patches survive test failure; rejected edits remain only in the
retained disposable workspace. No raw API messages, headers, environment, keys,
model summaries or reasoning are logged. Cancellation closes IPC; process teardown
may stop local waiting after a remote provider already received a request, so its
reservation remains spent/uncertain rather than promising remote cancellation.

## Credential and live-acceptance gate

The source and offline tests are implemented. No new account, credential, seed or
service has been installed. No live API call, actual broker identity/mount proof,
paid coding task, SSH-independence proof for the new broker, or external ChatGPT
coding acceptance is claimed. The existing fixture proofs are not substitutes.

After owner setup in the checkpoint: review a masked-input/stdin-only installation
flow before using it; bootstrap the single non-login identity and broker-only file;
stage the reviewed unit/runtime/seed with coding admission disabled. Validate
actual builder and broker UID permissions, masked mounts, IPC peer rejection,
offline sandbox denial of broker socket/key, DNS/TLS, shutdown/restart/cancellation
and disconnected-session operation. Then enable the reviewed profile for one
bounded real model acceptance and repeat the complete regression suite.

Only verified internal completion permits the human administrative Change/Review
Lane closure and Project State sync. Tasks never push, create PRs or deploy; the
builder PAT is not used by this implementation. External ChatGPT submit/status
handoff is prepared after deployment and remains user-performed. Media and reboot
are excluded. See `CODING_BROKER_CHECKPOINT.md` for the exact stop/continuation.

Sources checked 2026-10-11: [model/pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[function calling](https://developers.openai.com/api/docs/guides/function-calling),
[stateless reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[hard spend limits](https://developers.openai.com/api/docs/guides/spend-limits).
