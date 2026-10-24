# Unified history dashboard: narrowed source candidate

Base: a3fbb57aa6b58d1dadf2640491159a73e425cf5e.
Not published, installed or applied. No existing Compose service was changed.
New UID home-lab-unified has 16 panels. Old dashboards remain.

## Current scope
Existing machine/host-NIC Prometheus metrics + retained GitHub daily JSON history
+ security collection state. Update monitoring is deferred: no update report mount,
query probes, update dependency, endpoint, panel, scheduler or transfer in this patch.
Original update code/tests/design remain in the local review directory for a separate
future difference. Their earlier 34-test result is not the current focused test count.

Existing GUI evidence establishes three scrape targets, CPU/memory/disk/boot and
host NIC series. CPU history was observed for seven days; earlier history is unknown.
Host NIC data is not whole-home traffic. Actual dated snapshot count/range is unknown.
Owner metadata checks established latest schema-1 input only.
Sidekick is unlinked: explicit-log CLI analysis exists, but automatic audit collection,
result persistence, scheduled execution and Grafana integration do not. No audit
engine/job is added and Grafana internal audit counters are not used as host audit.

## Correct daily history
Strict dated JSON filenames, generated time and activity window must agree.
Collection JST day D corresponds to validated activity day D-1, shown at its own JST
midnight timestamp. latest.json is excluded. Item keys deduplicate; replacing a day
replaces its point, never adds repeated scrapes.
Missing dates inside retained boundaries are null; outside boundaries are absent.
Partial counts are lower bounds with per-metric quality. Failed/uncollected counts
are null. Old points remain visible; dataset freshness is a separate badge.
Default retention of 30 snapshots is configuration, not actual retention evidence.
The latest corrupt snapshot cannot silently fall back to older security evidence.
Parsing remains bounded to 8 MiB/depth 32, 366 files/calendar days, rejecting symlinks.
Responses contain aggregates, fixed scope names, timestamps and states only.

The existing pull-based latest gauge records scrape-time observations. It cannot
by itself reconstruct historical target dates from JSON. Prometheus backfill is
technically possible but needs a separate timestamp/deduplication/retention design.
This candidate instead reads existing retained JSON through Infinity; it does not
backfill TSDB, use rate/increase, or sum daily values across scrapes.

## Minimal read-only service template
The example is a DESIGN TEMPLATE, not a runnable approved overlay.
All relative paths resolve against stacks/observability, the reviewed base Compose
directory. Do not run it standalone, change the base directory or replace the base
Grafana service.

Input: VERIFIED_SNAPSHOTS_DIR must resolve to the snapshots subdirectory itself,
not the parent state directory. Long bind syntax sets read_only and disables
automatic host-path creation. Destination is /snapshots. Only two script files
are additionally mounted read-only. No update module or report input is mounted.
Existing UID 10001 and image home-ai-lab/python-jobs:1 require verification; no
pull/build is requested by the template.

The adapter listens on container 0.0.0.0:8081, with no published host port.
Only GET /history and /healthz are implemented; no dynamic input paths or request
logging. It has no credentials, external clients, Docker socket or host networking.
Root filesystem is read-only; capabilities dropped; privilege escalation forbidden.

Only grafana and github-history are configured on history-only, a dedicated bridge
with internal:true, attachable:false and IPv6 disabled. github-history joins ONLY
this network: no default/monitor attachment or proxy. Docker's internal network
provides external isolation. No OS firewall/routing change is proposed.
This is not authentication against the Docker administrator, host, or compromised
Grafana, and attachable:false is not a prohibition on a Docker administrator joining
another container. Membership must remain restricted operationally.
Docker DNS/host behavior and actual direct external egress rejection still require
runtime verification after approval; no external probe was executed.

Grafana retains its existing default and monitor networks and appends history-only.
Base image, loopback published port, .env, data volume, existing provisioning mount,
Prometheus dependency and security settings remain inherited. The existing default
and monitor definitions are not changed. This preserves existing Prometheus access
by design; a merged Compose model comparison must verify it before applying.
Grafana is not configured as a router/proxy for the adapter. Its existing outbound
connectivity is not removed; the no-external-egress restriction applies to the adapter.
Joining the new network/installing the plugin may require Grafana recreation and
brief dashboard unavailability; duration is not measured. No other service restart.

## Infinity pin and contract review
Pin official signed yesoreyeram-infinity-datasource to 4.1.3, not latest.
The official catalog and v4.1.3 plugin.json declare a range including Grafana 12.4.3.
This confirms declared compatibility, not successful runtime rendering.
Official v4.1.3 release Linux amd64 asset hash and URLs are recorded in
infinity-version.json. Actual architecture must match; no asset was downloaded.
Keep normal signature verification enabled; no unsigned-plugin exception.

The candidate query was compared to that tag's query.types.ts, constants.ts and
official JSONata dashboard: JSON/url/backend, GET, root_selector, columns with
selector/text/type, explicit timestamp, table/timeseries formats. Target datasource
references are explicit. No simulated timestamps, arbitrary URLs, request headers
or query-driven paths are used. Backend root selectors are $.days, $.meta, $.security.
These are source contract checks, not an execution test of the plugin.

The separate datasource template creates non-default, non-editable homelab-history,
with auth_method:none, explicit allowed host http://github-history:8081,
proxy_type:none, no OAuth passthrough, no cookies or secureJsonData.
It only queries the internal adapter. Existing Prometheus configuration is unchanged.
Grafana users continue to use existing Grafana authentication; the adapter has none.

Plugin acquisition uses official Grafana/GitHub distribution and is a separate
approved installation step, not runtime adapter traffic. A pinned official artifact
could be acquired outside the isolated adapter and verified before installation.
Exact install/restart procedure is not authorized or executed here.

## Low-load preflight, existing authorized path only
1. Return only dated-file count/min/max valid dates, readability by intended UID,
   and boolean confirmation that the mount source is the snapshots directory.
   Do not print paths, snapshot contents, repo names or credentials.
2. Return image presence, interpreter availability, architecture and Compose version.
   Do not pull/install or run the snapshot collector.
3. Inspect only Grafana's current network membership and relevant mount metadata.
   Compare merged Compose model locally: old networks/mounts/port/env-file references
   unchanged; only the two intended services join history-only. Do not dump .env or
   the full rendered Compose environment.
4. Check installed plugin ID/version/signature state and existing datasource UID
   presence without opening secrets. Confirm no UID conflicts.
No SSH retry, new login, scan, jobs, API collection, permissions or network changes
are included. Actual network reachability/rendering checks require later approval.

## Reviewable difference before publication/application
Seven new repo files: history reader, focused tests, dashboard JSON, service example,
datasource example, Infinity version/source evidence JSON, this document.
No existing active provisioning or Compose file is edited.
Publishing/merging the candidate and applying runtime changes are separate decisions.
Required runtime changes: create one isolated network and adapter, append Grafana
membership, install signed fixed plugin if absent, add new datasource/dashboard.
No update schedule/report transfer, new auth, broad mount, collection or data deletion.

Rollback after approval: remove only the new dashboard/datasource and adapter/network
membership; restore Grafana's prior plugin/config if necessary. Preserve old
dashboards, .env, volumes, snapshots and Prometheus data. Do not use broad docker down.

## Verification
21 focused synthetic/static tests pass on local Python 3.11.9; syntax compiled.
The YAML isolation/merge contract is checked statically as text. Docker and PyYAML
are unavailable here; no YAML parser/Compose model validation or network test ran.
Linux CI, Infinity execution, actual historical retention, new dashboard import and
live rendering remain untested. Earlier update-specific tests are outside this patch.

## Primary sources
- https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/
- https://github.com/grafana/grafana-infinity-datasource/releases/tag/v4.1.3
- https://raw.githubusercontent.com/grafana/grafana-infinity-datasource/v4.1.3/src/plugin.json
- https://raw.githubusercontent.com/grafana/grafana-infinity-datasource/v4.1.3/src/types/query.types.ts
- https://raw.githubusercontent.com/grafana/grafana-infinity-datasource/v4.1.3/src/types/config.types.ts
- https://raw.githubusercontent.com/grafana/grafana-infinity-datasource/v4.1.3/provisioning/dashboards-actual/infinity-jsonata-jq-filter.json
- https://docs.docker.com/reference/compose-file/networks/#internal
- https://raw.githubusercontent.com/moruku36/home-ai-engineering-lab/a3fbb57aa6b58d1dadf2640491159a73e425cf5e/stacks/observability/compose.yaml
