# Credential inventory

Metadata authority for platform execution. Values, token fragments and hashes do
not belong here. Paths denote references, not a request to copy credentials.
Verified 2026-10-10 Europe/Bratislava; unknowns must be resolved by the owner before
the corresponding new capability is enabled. File permission evidence is in
[the execution map](builder-execution-plane.md), not duplicated as token material.

| Purpose | Path/reference | Scope | Expiry | Owner |
|---|---|---|---|---|
| Administrative Windows → Homelab SSH | `C:\Users\megoi\.ssh\id_ed25519_homelab_codex`; host `/home/az1mutt/.ssh/authorized_keys` | Login as administrative az1mutt; no agent forwarding; never builder auth | No certificate expiry observed; revocation by key removal | Igor / az1mutt |
| Core source reads | `/home/az1mutt/.config/personal-ai-brain/github-token` → `/run/secrets/github_token` | Documented Project OS private Contents read; granted scope not re-queried this milestone | Unknown; owner verification required | Igor / az1mutt |
| Control Issues transport | `/home/az1mutt/.config/personal-ai-brain/github-control-token` → `/run/secrets/github_control_token` | `Az1mutt/personal-project-brain`: Metadata read, Issues read/write; prior live Contents denial | Unknown; owner verification required | Igor / az1mutt |
| Current interactive repository connector | Connected GitHub app, externally managed; no Homelab credential file established | Connector reports push/admin access to platform repo; broader grant not audited | Externally managed / unknown | Igor / connected app account |
| Parked Media client reference | `/home/az1mutt/.config/personal-ai-brain/trakt-client.json` | Media-owned; contents/scopes not inspected | Not inspected | Igor / Homelab-Media |
| Parked Media device-flow reference | `/home/az1mutt/.config/personal-ai-brain/trakt-device.json` | Media-owned historical device-flow artifact; validity not assumed | Not inspected | Igor / Homelab-Media |
| Parked Media token reference | `/home/az1mutt/.config/personal-ai-brain/trakt-token.json` | Media-owned; contents/scopes not inspected | Not inspected | Igor / Homelab-Media |
| Builder GitHub publication — `personal-ai-brain-builder` | `/home/az1mutt/.config/personal-ai-brain/builder/github-token` | Only `Az1mutt/personal-ai-brain`; Contents read/write, Pull requests read/write, automatic Metadata read; selected UI scope per owner setup, branch push verified | 2026-12-09 (owner supplied) | Igor / Az1mutt |
| Future headless model access — absent/not selected | Proposed `/etc/personal-ai-brain/builder/credentials/model-provider` | Selected provider/project and bounded usage only; distinct from GitHub | Provider-specific; record before enabling | Igor; provider custodian to be assigned |

Inventory scope is observed platform execution references, not a host-wide secret
discovery exercise. Media internals and unrelated trading credentials are excluded.
Add future entries here rather than creating separate builder token inventories.
