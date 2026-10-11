# Codex → ChatGPT: Remote Work Submission v0.1

## Internal completion; external acceptance pending

PR #14 is merged and deployed. CI and 174 tests passed. Internal Codex-originated
private Issues #32–39 verify submit, duplicate/conflict rejection, unsupported
request rejection, safe cancellation and terminal status. Administrative probes
verify durable handoff across control restart, builder interruption without replay,
actual identity separation and all 18 sandbox checks. These are **not external
ChatGPT connector acceptance**. The earlier read-only bridge acceptance (#28/#29)
remains historical evidence, not acceptance of the new work operations.

The existing Issues credential is reused. No model backend, task publisher,
listener, port, generic shell/filesystem API or Media behavior was added.
Whole-host reboot remains pending and outside this milestone.

## Exact project-chat acceptance

Use the ChatGPT project's own GitHub connector. Do not delegate this caller test
to Codex, SSH or a Homelab CLI. Destination: private
`Az1mutt/personal-project-brain`; title exactly `pab-control/v0.1`.
Paste only each JSON object as the issue body, without Markdown fences or prose.

The unused UUIDs and timestamps below were generated at 2026-10-11T00:20:16.964638+00:00.
If delayed beyond seven days, regenerate both request UUIDs and the task UUID,
refresh both envelope timestamps and contract timestamp, and keep the status
`task_id` equal to the newly submitted task UUID. For a subsequent status query,
always generate a new request UUID and current timestamp; reusing one returns its
old transport result. `requested_by` is audit metadata, never authorization.

### 1. Submit

```json
{
  "schema_version": "0.1",
  "requested_by": "chatgpt",
  "requested_at": "2026-10-11T00:20:16.964638+00:00",
  "request_id": "7ef5f9d9-193d-4b3a-980a-b92419c0bf62",
  "capability": "work.submit",
  "arguments": {
    "contract": {
      "schema_version": "0.1",
      "task_id": "a01e1371-2578-41f9-8bf2-46cb7cc69dda",
      "task_type": "fixture.patch-test.v1",
      "repository": "Az1mutt/personal-ai-brain",
      "base_ref": "71f0d82516d059ba2d65e028742cd73b2b9ee6bc",
      "goal": "Create the deterministic Work Runner fixture artifact.",
      "acceptance_criteria": [
        "fixture content matches",
        "isolation checks pass"
      ],
      "requested_at": "2026-10-11T00:20:16.964638+00:00",
      "deadline_seconds": 20
    }
  }
}
```

Read the worker comment and issue state using the same connector. Require the
matching request UUID and closed issue. `capability_completed` plus
`result.outcome: completed` means the runner replied; inspect its task ID and
status. `handoff_pending` means durable handoff only, not task success. Retain the
issue URL and response. Allow a polling cycle (normally 30 seconds; backlog or
backoff can add latency).

### 2. Query durable status

After the submit response, create a separate issue with this body:

```json
{
  "schema_version": "0.1",
  "requested_by": "chatgpt",
  "requested_at": "2026-10-11T00:20:16.964638+00:00",
  "request_id": "9f5115ff-43ff-4066-987a-ceed2369658f",
  "capability": "work.status",
  "arguments": {
    "task_id": "a01e1371-2578-41f9-8bf2-46cb7cc69dda"
  }
}
```

Require the matching request UUID, closed issue, `result.outcome: completed`,
`result.data.task_id` matching the submitted task, `status: succeeded`,
`terminal: true`, `attempts: 1`, and
`result.data.result: {"status":"succeeded","artifacts_retained":true}`.
If still submitted/running or the handoff is pending, query again with a fresh
request UUID/time. Do not create another task merely to obtain its status.
Do not infer success from issue creation or submit acknowledgement alone.

Cancellation was internally tested while running (#37, terminal query #39).
It is optional for external acceptance: `work.cancel` accepts only
`{"task_id":"<submitted task UUID>"}` in the standard envelope. The fixture is
short, so cancellation after completion safely reports the existing terminal
state; that does not prove an in-flight cancellation.

## Report back before claiming external completion

Record both issue URLs, both request UUIDs, task UUID, correlated terminal result
and issue closure. If the connector cannot create/read Issues, report that caller
limitation and leave external acceptance pending. Do not substitute internal
Codex probes. After independently verified external acceptance, synchronize
Project State with that evidence; do not start another implementation milestone.

Implementation and bounded handoff semantics: [Remote Work Submission](../remote-work-submission-v01.md).
