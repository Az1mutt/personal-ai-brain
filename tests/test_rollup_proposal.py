from __future__ import annotations

import yaml

from personal_ai_brain.rollup_proposal import RollupProposalEngine


class FakeReader:
    def __init__(self, files: dict[tuple[str, str, str], str]) -> None:
        self.files = files

    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        return self.files[(repository, path, ref)]


def dump(value: dict) -> str:
    return yaml.safe_dump(value, sort_keys=False)


def test_single_active_workstream_proposes_unambiguous_narrative() -> None:
    central = "Az1mutt/personal-project-brain"
    repo = "Az1mutt/recipe-intelligence-system"
    project_map = {
        "projects": [
            {
                "id": "recipe",
                "name": "Recipe Intelligence",
                "storage": "project_repo",
                "repository": repo,
                "state_path": ".project/state.yaml",
                "core_attention": "active",
                "workstreams": [
                    {
                        "id": "data-platform",
                        "state_path": ".project/workstreams/data-platform.yaml",
                        "owner": "technical chat",
                        "state_status": "synced",
                        "core_attention": "active",
                    },
                    {
                        "id": "product",
                        "state_path": ".project/workstreams/product.yaml",
                        "owner": "unassigned",
                        "state_status": "future_unassigned",
                        "core_attention": "none",
                    },
                ],
            }
        ]
    }
    root = {
        "state_scope": "project_rollup",
        "status": "active",
        "phase": "old-phase",
        "current_gate": "Old gate",
        "exact_next_action": "Old next",
        "workstreams": [],
        "rollup_policy": {
            "specialist_writes_root": False,
            "generated_from": [],
        },
        "verification": {"last_verified": "2026-09-10"},
    }
    active = {
        "status": "active",
        "phase": "creator-scale-pilot",
        "current_gate": "Validate creator-scale ingestion.",
        "exact_next_action": "Run bounded creator pilot.",
        "verification": {"last_verified": "2026-09-17"},
    }
    future = {
        "status": "future_unassigned",
        "phase": "not_active",
        "verification": {"last_verified": "2026-09-17"},
    }

    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (repo, ".project/state.yaml", "main"): dump(root),
            (repo, ".project/workstreams/data-platform.yaml", "main"): dump(active),
            (repo, ".project/workstreams/product.yaml", "main"): dump(future),
        }
    )

    proposals = RollupProposalEngine(reader).propose()

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.manual_synthesis_required is False
    assert proposal.basis_paths == [".project/workstreams/data-platform.yaml"]
    assert proposal.changes["phase"] == "creator-scale-pilot"
    assert proposal.changes["current_gate"] == "Validate creator-scale ingestion."
    assert proposal.changes["exact_next_action"] == "Run bounded creator pilot."
    assert proposal.changes["verification.last_verified"] == "2026-09-17"
    assert proposal.changes["rollup_policy.generated_from"] == [
        ".project/workstreams/data-platform.yaml"
    ]
    assert proposal.changes["rollup_policy.future_workstreams_do_not_block_rollup"] is True


def test_multiple_active_workstreams_do_not_get_fake_narrative_synthesis() -> None:
    central = "Az1mutt/personal-project-brain"
    repo = "Az1mutt/homelab-infrastructure"
    project_map = {
        "projects": [
            {
                "id": "homelab",
                "name": "Homelab",
                "storage": "project_repo",
                "repository": repo,
                "state_path": ".project/state.yaml",
                "core_attention": "active",
                "workstreams": [
                    {
                        "id": "infra",
                        "state_path": ".project/workstreams/infra.yaml",
                        "owner": "infra chat",
                    },
                    {
                        "id": "media",
                        "state_path": ".project/workstreams/media.yaml",
                        "owner": "media chat",
                    },
                ],
            }
        ]
    }
    root = {
        "state_scope": "project_rollup",
        "status": "active",
        "phase": "project-phase",
        "rollup_policy": {
            "specialist_writes_root": False,
            "generated_from": [".project/workstreams/infra.yaml"],
        },
        "verification": {"last_verified": "2026-09-16"},
    }
    infra = {
        "status": "active",
        "phase": "infra-phase",
        "verification": {"last_verified": "2026-09-17"},
    }
    media = {
        "status": "active",
        "phase": "media-phase",
        "verification": {"last_verified": "2026-09-17"},
    }

    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (repo, ".project/state.yaml", "main"): dump(root),
            (repo, ".project/workstreams/infra.yaml", "main"): dump(infra),
            (repo, ".project/workstreams/media.yaml", "main"): dump(media),
        }
    )

    proposal = RollupProposalEngine(reader).propose()[0]

    assert proposal.manual_synthesis_required is True
    assert "phase" not in proposal.changes
    assert "current_gate" not in proposal.changes
    assert "exact_next_action" not in proposal.changes
    assert proposal.changes["verification.last_verified"] == "2026-09-17"
    assert proposal.changes["rollup_policy.generated_from"] == [
        ".project/workstreams/infra.yaml",
        ".project/workstreams/media.yaml",
    ]


def test_root_verification_is_never_downgraded() -> None:
    central = "Az1mutt/personal-project-brain"
    repo = "Az1mutt/example"
    project_map = {
        "projects": [
            {
                "id": "example",
                "name": "Example",
                "storage": "project_repo",
                "repository": repo,
                "state_path": ".project/state.yaml",
                "core_attention": "active",
                "workstreams": [
                    {
                        "id": "one",
                        "state_path": ".project/workstreams/one.yaml",
                        "owner": "owner",
                    }
                ],
            }
        ]
    }
    root = {
        "state_scope": "project_rollup",
        "status": "active",
        "phase": "newer-rollup",
        "workstreams": [
            {
                "id": "one",
                "path": ".project/workstreams/one.yaml",
                "owner": "owner",
            }
        ],
        "rollup_policy": {
            "specialist_writes_root": False,
            "generated_from": [".project/workstreams/one.yaml"],
        },
        "verification": {"last_verified": "2026-09-18"},
    }
    child = {
        "status": "active",
        "phase": "child-phase",
        "verification": {"last_verified": "2026-09-17"},
    }

    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (repo, ".project/state.yaml", "main"): dump(root),
            (repo, ".project/workstreams/one.yaml", "main"): dump(child),
        }
    )

    proposal = RollupProposalEngine(reader).propose()[0]

    assert "verification.last_verified" not in proposal.changes
