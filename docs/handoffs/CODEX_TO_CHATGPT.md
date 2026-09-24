# Codex → ChatGPT Handoff

## Timestamp
2026-09-24 20:00 Europe/Bratislava

## Scope
Bootstrap the first live v0.2 acceptance run on Homelab; no persistent deployment.

## Environment
- Host: Igor's Ubuntu Homelab (private connection details omitted).
- Repo: Az1mutt/personal-ai-brain; ~/projects/personal-ai-brain.
- Branch: main.
- Commit / PR: implementation checkout 62afa941b5eec128f9f50f3c6928ef0f42fd9ac1; state sync 795fc057b0e9e38b38d52400822bb28d045252e6.
- Runtime/deployment target: isolated user virtualenv for manual acceptance; persistent runtime not deployed.

## Verified starting state
SSH key authentication works. Python 3.14.4, Git 2.53.0, Docker 29.7.2 and Compose 5.5.0 are available. Outbound GitHub access works. No clone was found in the bounded initial search. GITHUB_TOKEN was not set in the SSH session. Existing media containers were listed running; application health was not tested.

## Changes made
Cloned main into ~/projects/personal-ai-brain. Attempted creation of .venv, which failed due to missing ensurepip. Staged interactive prerequisite helpers outside the repo under ~/.local/share/codex-bootstrap. They install python3.14-venv via interactive sudo, prompt for a token with hidden input, verify private Project Map read access, and save it outside Git at ~/.config/personal-ai-brain/github-token with mode 600. Helpers have not been executed; no credential has been provisioned by this session.

## Commands / checks run
- Read default-branch AGENTS, README, architecture, roadmap and Project State.
- Verified SSH identity, tool versions, public git ls-remote and clone.
- python3 -m venv .venv: failed (ensurepip unavailable).
- sudo -n true: interactive authentication required.
- bash -n and Python compilation of prerequisite helpers: passed.
- git status --short: clean (incomplete .venv ignored).

## Verification results
Repository clone and SSH are verified. Package installation, pytest, agents validate, core-report, rollup-proposals and core-snapshot have NOT run. Live private-data acceptance is pending. No claim of Python 3.14 package compatibility or deployed runtime is made.

## Live Homelab state
Existing media services were not changed. No Docker configuration, scheduler, service, database or autonomous write capability was added.

## Blockers / risks
Igor must authenticate sudo to install python3.14-venv and supply a fine-grained token with Contents read-only for personal-project-brain. Token creation and permissions must be selected by Igor; successful API read alone does not prove absence of write permission. The Codex GitHub connector is distinct from the runtime credential.

## Exact next action
Igor runs bash ~/.local/share/codex-bootstrap/bootstrap-prerequisites.sh in an interactive SSH terminal. Codex then finishes venv/install/tests and all four acceptance commands, keeping private reports outside the public repository.

## Project State impact
.project/state.yaml updated and synced.

## Notes for ChatGPT
Continue from the actual installation prerequisite, not Docker packaging. The old machine-access blocker is resolved. Distinguish existing CI evidence from this still-pending Homelab acceptance. No secret values or raw private Project OS reports belong in this public handoff.
