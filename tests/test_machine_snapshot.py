from __future__ import annotations

from personal_ai_brain.core_agent import CoreSnapshot, Finding, StateRecord
from personal_ai_brain.machine_snapshot import build_machine_snapshot
from personal_ai_brain.rollup_proposal import RollupProposal


def test_machine_snapshot_groups_records_and_embeds_rollup_proposal() -> None:
    snapshot = CoreSnapshot(
        generated_on="2026-09-17",
        records=[
            StateRecord(
                project_id="recipe",
                project_name="Recipe Intelligence",
                scope="project",
                repository="Az1mutt/recipe-intelligence-system",
                path=".project/state.yaml",
                attention="active",
                status="active",
                phase="old-phase",
                last_verified="2026-09-10",
                sync_status="synced",
                current_gate="Old gate",
                exact_next_action="Old next",
            ),
            StateRecord(
                project_id="recipe",
                project_name="Recipe Intelligence / data-platform",
                scope="workstream",
                repository="Az1mutt/recipe-intelligence-system",
                path=".project/workstreams/data-platform.yaml",
                attention="active",
                status="active",
                phase="creator-scale-pilot",
                last_verified="2026-09-17",
                sync_status="synced",
                current_gate="Validate pilot",
                exact_next_action="Run pilot",
            ),
        ],
        findings=[
            Finding(
                severity="warning",
                code="rollup_outdated",
                subject="Recipe Intelligence",
                message="Root is older than child.",
            )
        ],
    )
    proposal = RollupProposal(
        project_id="recipe",
        project_name="Recipe Intelligence",
        repository="Az1mutt/recipe-intelligence-system",
        root_path=".project/state.yaml",
        basis_paths=[".project/workstreams/data-platform.yaml"],
        changes={"phase": "creator-scale-pilot"},
    )

    payload = build_machine_snapshot(snapshot, [proposal])

    assert payload["schema_version"] == "0.1"
    assert payload["health"] == {
        "states_read": 2,
        "errors": 0,
        "warnings": 1,
        "rollup_proposals": 1,
    }
    assert payload["findings"][0]["code"] == "rollup_outdated"
    assert len(payload["projects"]["recipe"]["records"]) == 2
    assert payload["projects"]["recipe"]["rollup_proposal"]["changes"]["phase"] == "creator-scale-pilot"
    assert payload["rollup_proposals"][0]["project_id"] == "recipe"


def test_machine_snapshot_without_proposals_has_stable_empty_contract() -> None:
    snapshot = CoreSnapshot(generated_on="2026-09-17")

    payload = build_machine_snapshot(snapshot)

    assert payload["health"]["rollup_proposals"] == 0
    assert payload["projects"] == {}
    assert payload["rollup_proposals"] == []
    assert payload["findings"] == []
