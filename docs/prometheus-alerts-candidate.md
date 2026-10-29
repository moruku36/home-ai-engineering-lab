# Prometheus availability and alerting candidate

This is a review candidate; no rule, exporter or notification destination has
been deployed. A live read on 2026-10-29 showed three scrape jobs: Prometheus,
node exporter and Grafana. It also showed zero configured Prometheus rule groups
and zero active Alertmanager endpoints. Grafana alerting and contact points have
not been independently inspected.

The Ansible role `prometheus_alerts_candidate` contains rules for a failing or
missing node exporter or Grafana metrics scrape; failing, unreachable or missing
n8n/MCP HTTP and SSH TCP probes; and stale or missing GitHub snapshot/exporter
metrics. A snapshot timestamp measures the last available snapshot, not the last
collector attempt, and a missing metric is not proof that the workflow failed.
These checks do not cover all host, application or workflow failures. The role only places
the rules file when explicitly enabled; it does not change the live service,
mount the file, configure `rule_files`, reload Prometheus, or deliver alerts.
The existing Prometheus Compose mounts only its configuration file, so a
reviewed rule-file mount and Prometheus configuration change are needed before
the rules can be used. Check syntax and behaviour before applying them.

Existing historical Kuma documentation describes separate SSH TCP, n8n and MCP
HTTP checks and a collector push/heartbeat monitor. `blackbox_candidate` renders
an HTTP/TCP probe configuration and Prometheus scrape fragment using explicitly
provided private addresses. These are candidates only: no exporter, credentials,
port or network change has been deployed. HTTP status and TCP connection checks
do not prove authenticated workflows work; SSH TCP does not test SSH login. No
credential-bearing URL or query string is accepted. The GitHub snapshot and
export timestamps are already exposed by the current node exporter, but do not
prove a collector attempt and are not equivalent to the collector push monitor.
Open WebUI is intentionally stopped and is excluded from the candidate.

On 2026-10-29 all 12 candidate PromQL expressions passed the running
Prometheus read-only parse API. Both probe templates were rendered with reserved
dummy addresses and their YAML parsed in an isolated review directory. This does
not validate real probe reachability or a merged live Prometheus configuration;
`promtool` and live rule evaluation remain untested. The missing-probe alerts
must only be enabled together with their matching configured probe jobs.

Prometheus can evaluate alert rules, but delivery needs a separately configured
Alertmanager or Grafana alerting contact point. No external destination or
credential is specified here. A monitoring process on the same host also cannot
send an alert when that entire host or its network is down; an independent
external heartbeat is needed for that case. Kuma remains in place until coverage
and delivery are verified and the owner decides its future.
