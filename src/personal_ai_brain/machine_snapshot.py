from __future__ import annotations

from dataclasses import asdict
from typing import Any

from personal_ai_brain.core_agent import CoreSnapshot
from personal_ai_brain.rollup_proposal import RollupProposal


SNAPSHOT_SCHEMA_VERSION = "0.1"


def build_machine_snapshot(
    snapshot: CoreSnapshot,
    proposals: list[RollupProposal] | None = None,
) -> dict[str, Any]:
    proposals = proposals or []

    projects: dict[str, dict[str, Any]] = {}
    for record in snapshot.records:
        project = projects.setdefault(
            record.project_id,
            {
                "project_id": record.project_id,
                "records": [],
            },
        )
        project["records"].append(
            {
                "project_name": record.project_name,
                "scope": record.scope,
                "repository": record.repository,
                "path": record.path,
                "attention": record.attention,
                "status": record.status,
                "phase": record.phase,
                "last_verified": record.last_verified,
                "sync_status": record.sync_status,
                "current_gate": record.current_gate,
                "exact_next_action": record.exact_next_action,
            }
        )

    findings = [asdict(finding) for finding in snapshot.findings]
    severity_counts = {
        "error": sum(1 for finding in snapshot.findings if finding.severity == "error"),
        "warning": sum(1 for finding in snapshot.findings if finding.severity == "warning"),
    }

    proposal_payload = [proposal.to_dict() for proposal in proposals]
    proposal_index = {proposal.project_id: proposal.to_dict() for proposal in proposals}

    for project_id, project in projects.items():
        if project_id in proposal_index:
            project["rollup_proposal"] = proposal_index[project_id]

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_on": snapshot.generated_on,
        "health": {
            "states_read": len(snapshot.records),
            "errors": severity_counts["error"],
            "warnings": severity_counts["warning"],
            "rollup_proposals": len(proposal_payload),
        },
        "findings": findings,
        "projects": projects,
        "rollup_proposals": proposal_payload,
    }
