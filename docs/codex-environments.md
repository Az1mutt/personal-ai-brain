# Codex environments

Use one capability profile per security/dependency boundary, not per project.
Repository-specific rules belong in that repository's AGENTS.md.

| Access plane | Durable state | Boundary |
| --- | --- | --- |
| Codex Desktop/local | User .codex config, global AGENTS, app-managed authentication | Local process and sandbox permissions; installed plugins do not prove authentication |
| Task workspace | Documents/Codex dated scratch and outputs | Temporary execution context; generated files are not automatically authoritative |
| Canonical checkout | Local checkout of GitHub history; C:\Projects is the local Windows convention only | Preserve uncommitted work; committed and pushed GitHub history is durable implementation truth |
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

## Verified Cloud environment

The existing **pab-homelab-dev** environment implements the **cloud-github-dev**
profile on **Codex Cloud**. Acceptance on **2026-10-12** is
**VERIFIED_WITH_WARNING**, based on the read-only Cloud validation below. This is
an environment acceptance record, distinct from the verification script's
`PASS_WITH_WARNINGS` outcome; it is not a live Homelab acceptance claim.

| Capability | Verified result |
| --- | --- |
| Repository scope | `Az1mutt/personal-ai-brain` and `Az1mutt/homelab-infrastructure`, both available in the isolated Cloud workspace |
| Repository policy | Both repository `AGENTS.md` files load correctly |
| Git | Local Git operations work |
| Python tooling | Python, pytest and PyYAML available |
| Node tooling | Node available |
| PowerShell | Installed under `/workspace/.cloud-setup/powershell`; `pwsh` is not on the default PATH |
| SSH observations | No user SSH directory, SSH agent socket or explicit `homelab` configuration found |
| Credential boundary | No Homelab administrative credential intentionally present; no local Windows paths or credentials assumed |

**Warnings:** Absolute SSH capability absence could not be certified because a
configuration-only probe encountered proxy behavior. No live Homelab connection
was attempted. PowerShell also requires explicit PATH initialization. Observed
absence is not a proof of enforced isolation; the administrative SSH prohibition
remains policy regardless of probe behavior.

### PowerShell startup configuration

The saved Cloud `start_skill` already supplies the following shell initialization.
It makes `pwsh` discoverable in that shell and gives PowerShell writable state
locations; it does not change the default PATH of unrelated task shells:

```sh
export PATH="/workspace/personal-ai-brain/.venv/bin:/workspace/.cloud-setup/powershell:$PATH"
export XDG_CACHE_HOME=/workspace/.cloud-setup/cache
export XDG_CONFIG_HOME=/workspace/.cloud-setup/config
export XDG_DATA_HOME=/workspace/.cloud-setup/data
```

Recommended environment change: retain this initialization in the versioned
`pab-homelab-dev` Cloud startup configuration and execute it in each task shell
before invoking `pwsh`. If the platform supports a persistent startup-PATH setting,
prepend `/workspace/.cloud-setup/powershell` while preserving the platform-provided
PATH, then publish and verify `command -v pwsh` in a fresh task. The exposed draft
configuration does not offer a dedicated additive default-PATH setting; an install
script's `export` alone does not persist into future task shells. Do not substitute
an invented PATH value, edit system shell profiles, or copy binaries into runtime
paths as a workaround. No credentials or additional network access are needed.
Default-PATH acceptance remains a warning until independently verified.

## Surface selection and Codex task lifecycle

1. Codex Cloud is the default for repository-only implementation, tests and docs
   in PAB/Homelab when live infrastructure is not required.
2. Codex Local is required for work explicitly needing the live Homelab, using
   the canonical `ssh homelab` capability and the repository's authorization rules.
3. Never copy the local Homelab administrative SSH credential into Cloud.
4. A new concrete feature, fix or milestone normally starts a new Codex task.
5. Continue an existing task only for the same bounded piece of work when its
   uncommitted task workspace is intentionally needed.
6. Codex task workspaces and task-local `work` branches are disposable execution
   state, not the source of truth. Preserve needed uncommitted work before disposal.
7. Durable implementation truth is committed and pushed GitHub history.
8. Durable project status and the next action belong in Project State.
9. Live runtime truth requires explicit verification in the appropriate runtime
   environment; a merged PR or passing Cloud tests does not establish deployment.
10. Reuse `pab-homelab-dev`; create additional Cloud environments only when
    repository scope, dependencies, network/service access or security boundaries
    materially differ.

Cloud tasks already have isolated workspaces. Use their existing checkouts; do
not create an additional Git worktree unless explicitly requested. The Windows
paths in the local setup section below apply only to Codex Local.

## Canonical Local execution lane

**local-homelab-admin** is the canonical logical profile for Codex Desktop
**Local / Worktree on Igor's Windows PC**. One logical profile covers both
canonical repositories:

- `C:\Projects\personal-ai-brain`
- `C:\Projects\homelab-infrastructure`

Use this lane when a task needs or is likely to need live Homelab inspection,
Docker/service/log/filesystem inspection on the Homelab, deployment or runtime
acceptance. For a bounded implementation followed by deployment/acceptance,
prefer Local from the start. Use **pab-homelab-dev** Cloud when work is strictly
repository-only and requires no live Homelab access.

Repository `AGENTS.md` remains the project-specific authority; the existing
`~/.codex/AGENTS.md` supplies global Local instructions. Do not duplicate the global
file into either repository. The Windows checkout paths are Local conventions,
not Cloud dependencies.

### Existing SSH route and credential ownership

Live Homelab administration requires explicit task authorization and the existing
canonical **`ssh homelab`** route. Inherit machine SSH resolution from
`~/.ssh/config`; the existing administrative identity remains in the user's
machine-local `.ssh` store. Its purpose is Homelab administration, and the manifest
stores only that external reference. Never copy it into a task workspace,
repository or Cloud environment, and never track its actual path, Homelab IP or
username in project configuration.

The previously verified baseline includes usable canonical checkouts, existing
global instructions and a successful non-interactive BatchMode probe. This is
retained evidence, not a new live check. Historical/ambiguous SSH candidates remain
preserved; revisit them only if they affect the canonical route. No deletion,
rotation or new key is authorized by this policy. Consider a new key only after
proving the canonical route unusable and finding no suitable authorized credential.

### Desktop configuration and remaining Local acceptance

As of **2026-10-13**, this policy update was prepared from Cloud. The current
Windows Desktop installation, machine-global configuration and Windows
project-root `.codex` settings were not accessible. Whether that installed version
exposes first-class project-local environments is **UNKNOWN**. Effective
Organization / Agent Security / managed Local policy is **UNKNOWN**; no policy was
created or inferred. No Desktop-recognized repo-local environment file has been
created or verified by this update. The logical profile alone does not provision
an execution environment.

Complete the following narrow acceptance in Codex Desktop Local, reusing prior
evidence instead of repeating the broad audit:

1. Inspect Local / Worktree mode, exposed Local environment settings, existing
   `.codex` settings in both canonical Windows checkouts, and relevant global
   configuration/instructions. Read only relevant settings, never credential
   values. Record the installed version and visible managed-policy effects;
   unavailable policy stays UNKNOWN.
2. If the installed product supports project-local environments, use its supported
   UI/configuration format in each repository's `.codex` directory under the
   single logical `local-homelab-admin` profile. Do not invent a format or track
   machine secrets/private connection details. Setup scripts prepare project
   dependencies only and must never automatically connect to the Homelab.
3. If explicit actions are supported, add **Verify Homelab** using only:

   ```sh
   ssh -o BatchMode=yes -o ConnectTimeout=10 homelab true
   ```

   Run it explicitly from Local using existing SSH configuration. Report alias
   availability, resolved identity path only, BatchMode PASS/FAIL, and whether
   that identity actually authenticated. Configuration resolution alone does not
   prove which identity authenticated; use bounded sanitized authentication
   evidence if needed. Do not enumerate unrelated keys or export raw SSH logs.
4. Verify Desktop recognizes each repo-local environment, both canonical paths
   are usable, and global plus repository instructions resolve correctly. If
   Worktree mode is tested, verify setup in a fresh worktree without changing
   live Homelab state. Do not infer Worktree acceptance from Local acceptance.
5. Verify no SSH credential entered either repository or Cloud configuration and
   the Cloud manifest still forbids administrative SSH. Record actual generated
   configuration paths, sanitized results and remaining warnings here and in the
   manifest; update Project State only after a meaningful verified milestone.

Current Local acceptance is **NOT_RUN** from this Cloud task: Desktop execution,
configuration recognition, Windows paths, instruction resolution, current SSH
identity and BatchMode result remain unverified. No live connection, credential
copy, key operation, service change or new platform capability was performed.

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
