# HomeLab Ansible baseline

The existing HomeLab construction playbooks were not found in the repository
or the limited host search. This is a minimal, new baseline; reconcile it with
the existing source if it is located. The service apply role is a review candidate
and has not yet been exercised on the lab.

The role declares the initial desired image tags based on the owner's previous
observations. They are not a current inventory: see the separate
[observation record](../docs/configuration-status.md). Prometheus 3.15.1 is a
candidate, not the declared or confirmed running version. The n8n image tag,
Kuma version, guest tools and image digests remain unconfirmed. A future change
must verify and pin the relevant digest before applying an image update.

Copy `inventory.example.yml` to the ignored `inventory.local.yml` and fill in
connection details locally. Keep identity files, vault passwords, real hosts,
addresses and private paths outside Git. Do not put secrets in this directory;
use the owner's existing private inventory and vault process when identified.

With Ansible already available on an authorized controller, the following checks
parse the playbook without applying it:

```sh
ansible-playbook -i ansible/inventory.example.yml ansible/playbook.yml --syntax-check
```

On 2026-10-29, `ansible-core` 2.21.5 and `community.docker` 5.4.0 were
installed in a user-owned isolated review environment. All three playbooks
passed `--syntax-check`. The local baseline validation was run twice with
`changed=0`; this did not exercise Compose or demonstrate apply idempotency.
The first live apply stopped before any change during Docker inspection. A
synthetic Ansible argument test identified extra backslashes in its Docker
format string; the revised string passed the same synthetic test. The original
Docker error was censored, so its precise cause is not independently confirmed.

The role validates the declared baseline. An optional readiness request can be
enabled by setting `home_lab_prometheus_ready_url` in private inventory; the
default makes no network request. Do not put credentials into that URL. Check
mode is not a guarantee of no changes, and a successful syntax or health check is
not proof that declared images are deployed.

`verify-existing.yml` inspects one explicitly selected, already running
container and compares its image reference and state with the baseline. It
requires Docker access and does not create or update containers. This is not a
complete comparison of Compose mounts, ports, environment or volume contents.

`apply-service.yml` is a draft for the existing Prometheus service only. It
requires explicit enablement and private project details, checks Compose identity,
uses the existing Compose file and applies only that service with dependencies
disabled and no volume or orphan removal. An optional image-only override allows
a fixed Prometheus tag or digest. It performs a loopback readiness check after
applying. It can restart or recreate Prometheus. A preflight compares the known
volume, bind mount and published port with the running container without logging
the resolved configuration. This does not compare all runtime settings, such as
command, environment or networks. The role does not recreate the entire lab; its
live behaviour and idempotency remain untested. Check mode skips the Compose
application and readiness check.

The owner accepts proceeding without an additional backup or restore test.
Existing encrypted backups and volumes must be retained. Ansible configuration
can reproduce software and settings, but cannot recreate persistent n8n,
Grafana or Kuma data that has been lost.

Record an applied change and the results of its health and recovery checks in a
separate sanitized maintenance record. Never mark an unexecuted change as applied.
