# Coding Agent Backend v0.1: preflight and architecture gate

Verified 2026-10-11 against origin/main
`cde8c424b687c3ef99b98e4764da4a67c973d8b2` and current official documentation.
**Status: stopped before installation/authentication, pending architecture review.**
This is not an implemented or accepted coding backend. Remote Work Submission
remains externally accepted. No production runtime, task contract, seed,
credential or service was changed; Project State retains verified reality.

## Current supported Codex path

Official [CLI installation](https://learn.chatgpt.com/docs/codex/cli) supports
Linux and currently presents a standalone installer. Do not execute a floating
installer for the service: a future deployment must pin an exact reviewed Linux
release and verified artifact digest. No binary was installed or release pinned
in this preflight; runtime CLI behavior has not been tested on the service identity.

[Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
documents `codex exec`, explicit `--sandbox workspace-write`, JSONL events,
`--output-schema`, final-message output and `--ephemeral`. `--full-auto` is
deprecated. JSONL includes reasoning items: raw event streams must not be retained.
Only selected bounded usage/final-result fields could enter durable artifacts.
The final message or a zero exit is not deterministic test acceptance.

[CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
documents stdin prompts (`-`), `--cd`, approval policy `never`, strict config,
and ignoring user config/rules. Ignoring user config does not disable auth lookup.
A future adapter must additionally deny repo-driven hooks, plugins, MCP, search,
subagents and local configuration that could widen policy. No bypass flags are
approved by this preflight.

[Configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
provides subprocess environment inheritance/filter controls and provider retry
settings. Environment filtering alone is not proof of credential isolation from
filesystem, inherited descriptors or process inspection. Request retries default
to four; provider request/stream recovery must be reviewed and bounded separately
from the runner's one-attempt rule. No automatic resume/replay is acceptable.

The cited CLI pages do not establish an exhaustive exit-code classification or
full descendant cleanup guarantee for our service. Those remain release-specific
acceptance gates: supervisor hard deadlines, cancellation, PID/cgroup teardown,
strict structured-output parsing and explicit sanitized auth/quota/network/crash
failures. No live model invocation or coding acceptance was performed.

## Concrete integration blocker

The bounded host check confirmed `User=pab-builder`, `Group=pab-builder`,
`PrivateNetwork=yes`, `NoNewPrivileges=yes`. The existing task launcher has
`--unshare-all`, `--disable-userns`, `--assert-userns-disabled`, private read-only
proc, sanitized environment and a mount set exposing only its current workspace
and reviewed runtime. No `codex` was found in the inspected administrative PATH;
that is not a host-wide installation search.

The supported [Linux Codex sandbox](https://learn.chatgpt.com/docs/sandboxing)
uses Bubblewrap/user namespaces. Dropping the CLI into today's task namespace
does not provide model connectivity or permit a second user namespace. Moving it
outside that namespace under the supervisor identity does not preserve the
current workspace-only access boundary either.

[Security documentation](https://learn.chatgpt.com/docs/agent-approvals-security)
explicitly separates command networking from model/auth traffic: Codex's command
network proxy does not constrain model/auth requests or all hosted tools. A command
domain allowlist therefore does not prove inference-only egress for the harness.
Enabling network on today's task namespace would also violate offline execution.

**Decision:** there is no verified drop-in `codex exec` deployment satisfying this
host's existing boundary. This is an integration/proof gap, not a claim that Codex
cannot be securely deployed in a different reviewed architecture. Do not remove
namespace restrictions, enable task networking, expose a token via environment or
mount an auth cache merely to make invocation succeed. The user's explicit
fail-closed/architecture-review condition applies here.

## Authentication decision

| Option | Security / operations | Cost and recommendation |
|---|---|---|
| Dedicated API project/service credential, held only by a separate trusted broker | Separately scoped, rotated and revoked; needs a validated broker/process boundary and independently enforced task budgets | API usage is billed separately from ChatGPT credits. Recommend for this unattended platform only after architecture approval and an owner-approved spend cap/model policy. No key provisioned. |
| Fresh ChatGPT-managed runner login | Persistent sensitive auth cache and refresh lifecycle; must never copy laptop/VS Code auth. Enterprise automation token eligibility is unknown and must not be assumed. | Uses ChatGPT/Codex entitlements and their limits. Not selected for this public-repository automation. |

[Authentication](https://learn.chatgpt.com/docs/auth) distinguishes subscription
and usage-based access, documents local credential caching, and describes
Enterprise Codex access tokens for eligible trusted automation.
[Managed account CI guidance](https://learn.chatgpt.com/docs/auth/ci-cd-auth)
requires preserving refreshed sensitive auth state and explicitly advises against
that workflow for public/open-source repositories. The platform repository was
public in the prior verified GitHub metadata. A private Issues queue does not make
its coding repository private. No account tier, billing balance or key scope was
assumed or changed.

Do not create a credential yet: authentication alone does not solve the blocker.
After an approved broker design and credential-free isolation tests, obtain an
owner-approved dedicated inference credential and install it using a reviewed
hidden-input flow. Record only purpose/path/scope/expiry/owner in the existing
credential inventory. Do not invent a model or spend allowance, use a broad default
key, or ask for a token in chat, command arguments or repository files.

## Smallest safe alternatives for review

Preferred Codex-preserving investigation: a secret-owning broker in a separate
process identity and mount/PID boundary; a secret-free Codex harness sees only the
current workspace and a narrowly authorized inference channel. Its command/test
executor must retain the existing offline boundary. Broker endpoint access must
be unavailable to repository commands, including via inherited FDs, proc or Unix
sockets. Broker routes, model, size, usage and deadlines are fixed reviewed policy;
no general HTTP proxy or host listener. The official
[Codex Action](https://learn.chatgpt.com/docs/github-action) demonstrates a
Responses-proxy approach, but its CI safety strategy is not a drop-in Homelab
security proof. No action framework is proposed for installation here.

Smaller fallback: a direct API-backed adapter whose trusted broker sends bounded
repository snapshots and receives structured proposed edits. The model gets no
local shell tool. The supervisor validates edits and runs reviewed tests in the
existing offline sandbox. This avoids nesting the Codex command executor, but
changes the requested provider implementation and requires explicit architecture
selection; it is not silently substituted for `CodexCodingAgent`.

Either design keeps `CodingAgent.run(task_context) -> CodingAgentResult` provider
neutral. Proposed result: provider/version/model, timestamps, bounded usage,
sanitized failure class, short final summary, verified changed files, patch
metadata and independent test outcome. No reasoning persistence. Policy-owned
model/test settings never enter caller arguments. Add `coding.patch-test.v1` only
after the boundary is approved; preserve fixture compatibility and existing
deduplication/interruption semantics. No implementation is enabled by this sketch.

## Exact continuation gate

1. Review/select the separated broker architecture above; retain the current
   offline runner and all existing services unchanged meanwhile.
2. Pin/review a release and verify its actual flags, config loading, environment,
   process/file visibility, offline command execution and inference channel using
   dummy credentials under the actual proposed service boundaries.
3. If that passes, resolve owner authentication and spend policy through a secure
   setup flow; update the single credential inventory with metadata only.
4. Implement the neutral adapter, strict coding contract, reviewed offline test
   environment and sealed artifacts. Exercise the user's coding acceptance matrix,
   including full process cleanup and no model replay after uncertainty.
5. Only after real internal acceptance perform PR/CI/merge/deployment verification
   and Project State sync. External ChatGPT coding acceptance remains pending.

No model task was submitted. No GitHub publication permission was added to a task.
Media and whole-host reboot remain out of scope.
