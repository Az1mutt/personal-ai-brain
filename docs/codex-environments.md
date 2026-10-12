# Codex environments

Use one capability profile per security/dependency boundary, not per project.
Repository-specific rules belong in that repository's AGENTS.md.

| Access plane | Durable state | Boundary |
| --- | --- | --- |
| Codex Desktop/local | User .codex config, global AGENTS, app-managed authentication | Local process and sandbox permissions; installed plugins do not prove authentication |
| Task workspace | Documents/Codex dated scratch and outputs | Temporary execution context; generated files are not automatically authoritative |
| Canonical checkout | C:\Projects repository history, branches and preserved worktrees | Project source of truth; follow its AGENTS.md |
| Published/cloud environment | Repository commits plus explicitly configured platform environment | Local config, disk, SSH identities and connector sessions are not inherited |
| ChatGPT connector/plugin | Service-managed connection and repository/account grants | Independent of Git CLI authentication and local SSH |

## Profiles and credentials

- **local-homelab-admin:** Desktop/local project work, GitHub via whichever access
  plane is verified, administrative SSH through the canonical homelab alias.
- **cloud-github-dev:** Repository development only. Administrative homelab SSH is
  forbidden; never upload its private key or assume local machine credentials.

The manifest contains capability descriptions and external credential references,
never credential values, destinations or machine addresses. It uses JSON-compatible
YAML 1.2 so PowerShell can parse it without installing a YAML module.
Profile restrictions describe policy; these scripts do not provision or enforce a
cloud sandbox. Platform credential isolation still requires operator verification.

Canonical SSH configuration/identities stay in the user's .ssh directory.
Keep other credentials in their approved external/platform stores; leave Codex
app-managed auth under app control. Never copy private keys or tokens to task
folders, repositories, manifests, reports or cloud development environments.
Documents/Codex is scratch/output, not a credential store or canonical checkout.
Scratch may still contain valuable work: location alone never authorizes deletion.

## Repeatable local setup

1. Inspect C:\Projects destination collisions. Stop a component if meaningful
   content exists; never overwrite a checkout to install this layout.
2. Establish canonical Git repositories using existing authoritative history.
   Preserve refs before updating from remotes. Keep original checkouts until
   preservation is independently verified.
3. Preserve dirty files byte-for-byte, including untracked files. Recreate linked
   worktrees through Git; do not copy .git pointer files into new locations.
4. Review config/codex/AGENTS.global.example.md and install it as the user's
   .codex/AGENTS.md only if absent, or reconcile existing instructions explicitly.
5. Run the commands below in PowerShell 7+. Audit and verify do not install
   software, modify configuration, fetch Git history, or read credential values.

```powershell
./scripts/codex/audit-environment.ps1
./scripts/codex/audit-environment.ps1 -ProbeHomelab
./scripts/codex/verify-environment.ps1 local-homelab-admin
./scripts/codex/verify-environment.ps1 cloud-github-dev
```

Audit probes SSH only with -ProbeHomelab. Local profile verification probes by
default; -SkipHomelabProbe yields INCOMPLETE because connectivity is required.
The SSH probe uses BatchMode, requires an existing trusted host key, suppresses
forwarding, connection sharing, proxy/local commands and host-key writes.
It does not change saved SSH behavior. Include/Match configurations are reported
UNKNOWN rather than evaluated. The probe deliberately tests a direct alias path.

GitHub CLI status is suppressed and reduced to a status; absent CLI authentication
does not disprove connector access. No credential helper is invoked by Git status.
Executable metadata is used for Codex version because CLI startup may write state.
No version or surface is guessed when metadata is unavailable.

PASS means that specific check succeeded; WARN needs review; MISSING means an
expected item was absent; UNKNOWN means unverified/inaccessible. A required check
that does not pass makes verification INCOMPLETE (exit 1). Optional warnings produce
PASS_WITH_WARNINGS (exit 0). -AsObject returns structured evidence without exiting.
Filename candidates include scripts and documentation; they are not proof of
credentials or duplicates. Inaccessible paths and skipped links remain warnings.
Neither script decides deletion safety.

## Preservation and review

Use Change / Review Lane for this policy and executable tooling: branch, tests,
secret scan, diff check and PR. Keep distinct media work and ledger README changes
until reconciled. Preserve runner worktree relationships and feature commit refs.
The old SSH candidate and old task roots require separate review; this setup does
not authorize their deletion, credential rotation or authentication ACL changes.

Run offline script tests with:

```powershell
./scripts/codex/test-environment.ps1 -FixtureRoot <new-empty-scratch-path>
```

Tests create only synthetic fixtures, mock external commands, and retain fixtures
at the specified path for review. They never run a live SSH or GitHub probe.
