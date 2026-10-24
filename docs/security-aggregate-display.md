# Dedicated security aggregate display

This adapter reads validated numeric summaries only. It does not collect data,
authenticate to GitHub, run Sidekick, start a scan, or schedule jobs.

Use a separate owner-controlled display root (0700), containing input and code
subdirectories (0755) and exclusively created aggregate/code files (0444).
Verify ancestors, ownership, links, ACLs, and actual container UID mapping first.
Do not relax existing shared-directory permissions. Never mount a credential
directory, collector code, or the private original-summary directory.

The example overlay adds only three read-only binds and changes github-history's
command. Keep the complete existing Compose file set. Require the merged model
to differ only in those fields. Recreate github-history only, using no-deps and
no image pull. Preserve its image, UID, read-only rootfs, dropped capabilities,
internal network, existing mounts and lack of published ports. Leave Grafana,
Prometheus, existing dashboards and data intact.

Copy only schema-validated aggregates, without printing source content. Preserve
timestamps and save failures and partial results as well as successes; never
substitute an earlier green result. Newest invalid input is an error. Complete
zero applies only to the explicitly selected two-repository scope. Partial zero
is unknown. Summaries older than 26 hours are stale and hide risk counts.
Sidekick remains uncollected. Dependency findings are not host security audits.

Before applying, retain the old Compose invocation and the current dashboard.
Update only panel 16 through Grafana's supported UI/API, never by direct database
writes. Compare the live dashboard first rather than overwriting a newer version
with the repository JSON. Roll back by omitting this overlay and recreating only
github-history, then restoring panel 16. Preserve input originals and backups.

This example needs explicit owner approval and host preflight. No deployment,
periodic collection, permission change to existing objects or network change is
implied by publishing these files.
