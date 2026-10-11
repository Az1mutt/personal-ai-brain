# Coding broker checkpoint — owner credential gate

2026-10-11. Continue from the clean local branch `feat/coding-agent-broker-v01`
in `/tmp/pab-coding-agent-preflight` on Homelab. Parent checkpoint is `9268c25`;
the current implementation commit is the branch HEAD (reported at handoff).
No push, PR, merge, builder PAT use or live deployment occurred.

Read current `AGENTS.md`, `.project/state.yaml`, and
`docs/coding-agent-backend-v01.md`. Do not redo reconciliation or Codex CLI
feasibility. The owner approved the direct Responses broker; CLI/self-hosted Agents
are not the selected design. Local Windows `coding-agent-files` is a staging copy,
not authoritative Git history.

## Completed and verified

- Strict coding contract, one reviewed real-code profile, unchanged fixture path.
- Provider-neutral runner adapter; authenticated bounded AF_UNIX protocol; separate
  broker code with fixed Responses endpoint/model/tool/output policy and no retry.
- Mediated path-safe workspace operations; deterministic changed-file/AST checks;
  reviewed offline test harness via the existing unchanged Bubblewrap launcher.
- Fsynced per-task/per-turn reservations and sanitized usage; no paid UUID replay.
- Cancellation/deadline/disconnect child reaping and interrupted ledger recovery.
- Durable patch/test/result/agent metadata and fixed diagnostics.
- Broker systemd template passes `systemd-analyze verify` (unrelated installed XFS
  units emit obsolete CPUAccounting warnings). This is syntax verification only.
- Linux pytest: **222 passed**, including 174 existing regressions and 48 new
  cases. Final offline verification completed on 2026-10-11.
- `.project/state.yaml` intentionally unchanged: internal coding acceptance is not
  complete. Credential inventory contains only the planned reference and scope.

## Igor's required OpenAI setup

Do this in the API Platform as the project/organization owner, not in ChatGPT
subscription settings. API usage is separately billed.

1. Project switcher → Create project → name `Personal AI Brain`. Use a dedicated
   project rather than Default. Existing dedicated project may be reused if its
   scope is only this platform inference.
2. Project settings → Limits → Spend → Edit spend limit → Monthly spend limit
   `15` USD → **Enforce a hard limit ON** → Save. An alert alone is insufficient.
   Confirm the enforced limit in the UI; enforcement can slightly overshoot while
   the setting propagates. Do not change organization-wide billing/limits.
3. Project Limits → Model Usage: allow `gpt-6.1-sol` only. If the model or enforced
   hard-limit control is unavailable, stop and report that non-secret condition;
   do not substitute another model or an alert-only budget.
4. Project settings → Members → + Service account → `pab-inference-broker`.
   Keep it project-scoped/non-owner. Save the one-time key in a password manager.
5. Project settings → API Keys → edit that service account key → Restricted.
   Enable **Responses API: Write** (create responses). If the UI presents the
   separate **Model capabilities: Request** permission, allow inference request
   permission as required; keep unrelated endpoint permissions None. No Files,
   Assistants, Threads, Batch, fine-tuning, administration or key-management grant.
   Do not retain the default unrestricted All key settings.
6. Record a rotation/revocation date; do not assume the service key expires itself.
   Report only project name/ID, confirmed model/permissions/hard cap and rotation
   date. **Never paste the key into chat, an Issue, a command argument or a file
   in this repository.** No credential transfer is implemented or initiated here.

[Project/service-account UI](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform),
[permissions](https://developers.openai.com/api/docs/guides/rbac),
[hard-limit UI](https://developers.openai.com/api/docs/guides/spend-limits).
UI instructions checked 2026-10-11; inspect only relevant settings if later UI differs.

## Exact continuation after owner setup

1. Verify this branch is clean and includes parent `9268c25`; retain pending local
   work. No repeated platform inventory. Re-read only changed/current policy.
2. Review an explicit masked-input/SSH-stdin-only credential installation script
   before asking the owner to use it. Never inspect existing credential values or
   copy other authentication. Administrative root bootstrap is owner-operated;
   neither runner nor broker receives sudo. Do not improvise transfer.
3. Create the single `pab-inference` non-login identity, primary group the existing
   `pab-builder` group, no supplementary privileged groups. Create broker-owned
   state 0700 and credential parent 0700/file 0600 at documented paths. Reuse the
   root-owned runtime, stage the unit, and seed exact coding base `cde8c42` into the
   distinct root-owned coding seed so fixture base remains unchanged. No production
   profile enablement until boundary probes pass.
4. Verify actual UID/mount/IPC/credential isolation, offline coding sandbox, process
   cleanup, restart truth, and originating-session independence. The service
   template's masked `/etc` DNS/TLS binds require live validation. Never weaken
   task isolation to fix deployment. No live probe of these new boundaries has yet
   been performed; offline tests under az1mutt do not establish them.
5. With owner-confirmed project hard cap and reviewed root policy, enable coding
   for one fresh UUID using the documented exact goal/criteria/base and deadline
   180. Verify mediated exploration, real patch, all 13 offline checks, unchanged
   other files, durable usage, duplicate/no paid replay, conflict, cancellation,
   deadline, provider errors and existing fixture/control regressions. Some
   failure injection remains offline; label evidence accurately.
6. After all internal acceptance passes, perform administrative PR/CI/merge and
   deployment closure per AGENTS; do not give that capability to model tasks.
   Synchronize Project State only then; prepare a fresh ChatGPT work.submit/status
   handoff and mark external acceptance pending, never self-claim it.

No automatic retry or resume exists. Uncertain paid attempts retain reservations;
future retry requires separately reviewed explicit attempt linkage. Whole-host
reboot and Media remain out of scope.
