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

`upgrade-gate.yml` is a review-only gate for future upgrade work. It requires
an explicit enable flag, one known target, and a matching record of isolated
restore evidence. Missing inputs cause rejection. Even if all inputs are set,
the playbook deliberately stops without updating anything. Evidence is an
operator assertion, not automatically verified proof; it must be reviewed and
must not contain secret paths or contents. Any future mutating role must include
this gate in its own execution path and provide separately reviewed backup,
restore and rollback procedures; this standalone gate cannot enforce safety on
other playbooks.

Backup and rollback are intentionally not automated yet: the current encrypted
Prometheus backup has not passed an isolated restore. Identify the existing
recovery key, verify a separate restoration and document the tested recovery
procedure before adding mutating tasks. For other components, establish their
own backup coverage and rollback procedure before applying updates.

Record an applied change and the results of its health and recovery checks in a
separate sanitized maintenance record. Never mark an unexecuted change as applied.
