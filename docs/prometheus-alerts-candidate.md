# Prometheus availability and alerting candidate

This is a review candidate; no rule, exporter or notification destination has
been deployed. A live read on 2026-10-29 showed three scrape jobs: Prometheus,
node exporter and Grafana. It also showed zero configured Prometheus rule groups
and zero active Alertmanager endpoints. Grafana alerting and contact points have
not been independently inspected.

The Ansible role `prometheus_alerts_candidate` contains rules for a failing or
missing node exporter or Grafana metrics scrape. These are metrics endpoint
checks, not complete host, application or workflow checks. The role only places
the rules file when explicitly enabled; it does not change the live service,
mount the file, configure `rule_files`, reload Prometheus, or deliver alerts.
The existing Prometheus Compose mounts only its configuration file, so a
reviewed rule-file mount and Prometheus configuration change are needed before
the rules can be used. Check syntax and behaviour before applying them.

Existing historical Kuma documentation describes separate SSH TCP, n8n and MCP
HTTP checks and a collector push/heartbeat monitor. Equivalent Prometheus
coverage requires additional probes or exported freshness metrics; the `up`
rules in this candidate do not replace them. An HTTP/TCP probe exporter is one
option, but no exporter, credentials, port or network change is approved or
included here. Open WebUI is intentionally stopped and should not be treated as
an unexpected outage.

Prometheus can evaluate alert rules, but delivery needs a separately configured
Alertmanager or Grafana alerting contact point. No external destination or
credential is specified here. A monitoring process on the same host also cannot
send an alert when that entire host or its network is down; an independent
external heartbeat is needed for that case. Kuma remains in place until coverage
and delivery are verified and the owner decides its future.
