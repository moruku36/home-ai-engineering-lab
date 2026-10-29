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

## Proposed deployment for a single owner review

1. Add one blackbox exporter container, candidate
   `prom/blackbox-exporter:v0.29.1@sha256:66eae352a79e6f677aeddd8c25a9bdb017586dc5fbd230f22329213d891f94bd`
   (Linux amd64 manifest, checked 2026-10-29). Its probe endpoint would
   listen on container port 9115 only, without a published host port. Attach it
   to the existing monitoring network for Prometheus and n8n, and the existing
   internal MCP network for the MCP health endpoint. Verify the actual network
   names and endpoint reachability first; attaching a container to both networks
   expands its access and requires approval.
2. For SSH, a TCP probe needs a route to the host's SSH port. The existing Kuma
   default network and firewall rule may provide such a route, but this has not
   been validated for a new container. Joining that network would expand access
   and must be approved; do not change the firewall or rely on this route without
   checking. If Kuma is later removed, its network lifecycle also needs a plan.
3. Mount the reviewed rule files into Prometheus, merge the private probe scrape
   fragment, preserve the existing Compose inputs, and reload or restart only
   Prometheus as appropriate. The existing snapshot/export timestamps can be
   used without adding a collector or scheduled task. Compare the existing
   collector push monitor before claiming equivalent coverage.
4. One concrete delivery option is a separate Alertmanager container, candidate
   `prom/alertmanager:v0.34.1@sha256:84967b9b7ba45e38a9278d3e594305f43d4993c310df3905b51138b816c365f3`
   (Linux amd64 manifest, checked 2026-10-29), on the monitoring network, using
   internal container port 9093 with no host port
   published. Configure Prometheus to send alerts there and configure one
   explicitly chosen destination in a private file. Recipient, credential storage,
   image digest, outbound access and any test notification require owner review.
   Grafana-managed alerting is an alternative if its existing contact points are
   verified; it could avoid a separate Alertmanager container, but that setup has
   not been inspected.

The full proposal is therefore two new containers for the Alertmanager option,
no new host-published ports, explicit connections to existing Docker networks,
one Prometheus configuration/mount change, and one selected notification
destination. No part of this proposal has been applied.
