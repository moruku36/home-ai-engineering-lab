# Defender and Dependabot collection: trial record

This record separates observed behavior from proposed changes. It contains aggregate results only; it does not include credentials, raw security events, host identifiers, repository names, or private paths. It is a snapshot, not a claim about current protection.

## Observed on 2026-10-28 UTC

- The existing daily Dependabot collection and publication produced a current aggregate for the approved set. The latest observed run attempted 83 repositories: 18 complete, 63 unavailable and 2 failed, with 83 requests and no request or page limit reached. The previous run recorded 18 complete, 64 unavailable and 1 failed. These categories do not establish the reason for each inaccessible repository.
- The latest Defender display input was observed on 2026-10-25. It had complete status data at that observation and unavailable detection history. A matching owner-supplied status input exists in the earlier display package. This establishes neither current protection status nor a working recurring transfer.
- The Defender receiver and protected input entry point exist as code. Neither their presence nor a stale input proves a configured or functioning transfer. The Windows source and previous transfer records remain unverified.
- Grafana's local health endpoint responded successfully; the history adapter process was observed running. Container health and Grafana's current panel rendering were not verified in this investigation.

## Review candidate

The isolated [classification candidate](../experiments/security-collection/) preserves the aggregate schema and existing request limits. It adds bounded reason labels for HTTP 403, HTTP 404, other HTTP responses, transport errors, schema/protocol errors, and unexpected internal errors. It records whether a category occurred, not repository names, error bodies, individual status codes beyond those categories, or per-category counts. Rate limiting and authentication failures retain their existing handling.

The collector and aggregate validator must be updated together. Existing summaries remain accepted. The candidate is **not deployed** and does not initiate requests, install a job, change permissions, or repair GitHub access. A 403 or 404 alone does not prove whether access is missing or the feature is disabled.

Offline tests cover classification, existing reason compatibility, and stopping on a rate limit. A separate offline check exercised the existing display adapter against an 83-target synthetic aggregate; it accepted the new labels. These checks do not establish live deployment or next-run behavior.

## Remaining work and boundaries

1. Review the candidate and, if adopted, preserve existing ownership, permissions and backups when placing both files. Verify the next already-scheduled run without an immediate full recollection or added budget.
2. For a representative unavailable repository, inspect the alerts setting and effective access with an already authorized account. If the existing account cannot view the setting, record the cause as unknown. Do not infer enabled or disabled from a 403 or 404. A new token, expanded access, or feature enablement requires separate authorization.
3. Identify the Windows source and its existing collection and transfer records, then establish whether collection, transfer, or display is stale. Do not equate a missing recent input with disabled protection. Creating or restarting a recurring job requires separate authorization.
4. Verify the live Grafana panel, its freshness indication and lower-bound wording when the existing UI is available. Image and container-health verification remain outstanding in this record.

The trial remains limited to its existing 83-repository scope, budget, permissions, and end time (2026-10-31 09:00 JST); it is not extended by this proposal.
