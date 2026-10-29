# HomeLab Ansible baseline

The existing HomeLab construction playbooks were not found in the repository
or the limited host search. This is a minimal, new baseline; reconcile it with
the existing source if it is located. It does not deploy Compose, change images,
perform backups, restore data, or grant permissions.

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

The role validates the declared baseline. An optional readiness request can be
enabled by setting `home_lab_prometheus_ready_url` in private inventory; the
default makes no network request. Do not put credentials into that URL. Check
mode is not a guarantee of no changes, and a successful syntax or health check is
not proof that declared images are deployed.

`verify-existing.yml` inspects one explicitly selected, already running
container and compares its image reference and state with the baseline. It
requires Docker access and does not create or update containers. This is not a
complete comparison of Compose mounts, ports, environment or volume contents.
The requested equivalent Compose application and version-changing roles remain
unimplemented; the playbooks here cannot yet recreate or update the lab.

The owner accepts proceeding without an additional backup or restore test.
Existing encrypted backups and volumes must be retained. Ansible configuration
can reproduce software and settings, but cannot recreate persistent n8n,
Grafana or Kuma data that has been lost.

Record an applied change and the results of its health and recovery checks in a
separate sanitized maintenance record. Never mark an unexecuted change as applied.
