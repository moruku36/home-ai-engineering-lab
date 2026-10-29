# Configuration status and Ansible integration

This is a non-secret observation record, not an inventory, a deployment manifest,
or proof that the desired configuration has been applied. The HomeLab construction
Ansible source has not yet been located in this repository. A new, read-only
[Ansible baseline](../ansible/README.md) is available for review; reconcile it
with the construction source if found. It is not a second state database.

## Observed host services

The owner supplied container status on 2026-10-28. These observations are not a
fresh scan and do not establish the latest available or desired versions.

| Component | Observed | Limit |
| --- | --- | --- |
| Prometheus | 3.15.1, running | Readiness HTTP 200 and 3/3 targets up after the owner-reported update. |
| Grafana OSS | 12.4.3, running | Backup and update verification remain open. |
| n8n | 2.44.6, running | Backup and update verification remain open. |
| node_exporter | 1.12.1, running | No update verified. |
| Uptime Kuma | Running | Exact version not confirmed. |
| Open WebUI | Stopped, data retained | Not an update target until its treatment is agreed. |
| Local jobs and MCP | Running | Source and deployed image correspondence not established. |
| KVM analysis tools | Not freshly inspected | Host observations do not establish guest versions. |

Prometheus readiness and health subsequently returned HTTP 200, with three of
three configured scrape targets up. An encrypted backup was created and its
stored checksums matched; independent checksum provenance and isolated restore
remain unverified. The restore attempt did not complete. Preserve the backup and
the existing recovery identity; generating a new key cannot decrypt old backups.

On 2026-10-29 the owner reported the targeted baseline Ansible command succeeded.
The recap and change count were not provided. A subsequent nonprivileged read
confirmed Prometheus readiness HTTP 200 and build version 3.15.0; it did not
independently inspect Docker volumes. After the owner reported the subsequent
update, another read confirmed version 3.15.1, readiness HTTP 200 and 3/3 targets
up. Post-update volume identity and the Ansible recap remain unverified.

## Integration boundary

Record desired image versions and digests independently from observed versions
and the result of each application. The owner accepts updates without an
additional backup or restore test. Preserve existing backups and data, and add
service-specific apply and health tasks after their actual inputs and dependencies
are understood. A syntax check or Ansible check mode is not
evidence of a successful deployment or a guarantee of zero changes.

Keep actual inventories, connection details, secrets, recovery identities,
private paths and raw logs out of this public repository. Publish only sanitized
configuration, observations, verification dates and operating guidance. Do not
change running services merely to make this record match a desired version.
