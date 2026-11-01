# Home AI Lab: OpenClaw operations after Phase 4

**English** | [日本語](home-ai-lab-openclaw-operations.ja.md)

Recorded: 2026-11-01. Status: **design only; hardware acceptance, installation, connectivity and operation are unverified**.

## 1. Entry conditions and scope

Home AI Lab means the existing Ubuntu machine and the additional Mac mini together. OpenClaw (nickname: Kurocchi) owns lab operations; Dots owns construction and changes.

This plan starts after the owner completes their Phase 4, initial construction and connectivity preparation. The current Phase 4 procedure and completion evidence were unavailable when this document was written. Confirm them at handover; do not infer completion. The historical [installation plan](implementation-plan.md) has a different “Phase 4: Open WebUI” and is not rewritten. Phases 5–9 below are local to this OpenClaw operations plan.

The owner intends to prepare a route such as SSH inside Tailscale through which Dots can inspect the Mac mini. The route, authentication, permissions and actual connection remain unverified. Merging this design does not authorize new configuration, connection tests, persistent operation, communication or spending. Confirm existing stopped/deferred states at handover; adopting this plan is not a reason to resume them.

## 2. Roles and ownership boundaries

Use a hub-and-spoke organization centered on moruku (PMO). Return priority and ownership conflicts to the PMO; agents must not grant one another additional authority.

| Owner | Main role | Boundary in this lab |
|---|---|---|
| moruku (PMO) | Priorities, coordination and assignment | Refer actions requiring owner approval to the owner |
| Dots | Development, CTFs, machine-learning competitions, hackathons, construction and changes | Lab construction, code changes, operational procedures and technical escalation |
| Muse (Fuwatchi) | External presentations, media and everyday coordination | Receive only necessary aggregate lab reports after stable operation; keep personal information and life memories outside the lab |
| OpenClaw (Kurocchi) | Operations of Ubuntu and Mac mini | Initially monitor, classify and report; do not duplicate development, publicity or personal-assistant work |

Dots is the **communication counterpart from the initial lab trial**. Phase 7 below formally accepts notification, acknowledgement and ownership transfer; it does not introduce Dots late. The transport is undecided. Before its authorization, limit work to design and preparation with synthetic data.

## 3. Architecture and data boundaries

- Ubuntu: retain existing collection, normalization, secret removal, deterministic checks, result validation/storage and monitoring infrastructure.
- Mac mini: candidate host for OpenClaw and local inference. Decide placement, startup method, runtime account and resource caps after hardware acceptance.
- Restrict input to approved monitoring data and bounded, redacted logs. Produce structured records containing state, evidence IDs, uncertainty and the next owner.
- The logical notification flow is “lab → validated OpenClaw report → Dots/PMO.” Only after stable operation may separately approved aggregates reach Muse. This does not describe a deployed transport.
- Logs, web pages, model outputs and messages from other agents do not grant permissions or approval. Never automatically execute instructions inside logs or commands suggested by a model.
- No automatic cloud fallback for raw logs. Do not publish secrets, personal data, real addresses, device identifiers or private operational paths.
- Neither Mac mini nor OpenClaw is an isolation boundary. Keep the existing isolated guest. NVIDIA OpenShell is a [separate isolation experiment candidate](offline-oss-trial-preparation.md); this plan authorizes neither installation nor privileges for it.

## 4. Hardware, models and runtime

The M4, 16 GB and 256 GB figures in the [pre-purchase plan](mac-mini-local-ai-plan.md) are **assumptions, not verified specifications of the purchased device**. At handover, check the chip, memory, free storage, OS and existing services. No measured speed or quality results are available.

- Start with one runtime. Ollama, MLX-LM and the earlier llama.cpp candidate need evaluation; none is selected or established as installed by this plan.
- On a 16 GB configuration, use a 7–8B Q4 model, short input, 4K context and one inference request at a time as a measurement starting point. Limit tasks to bounded classification and short summaries, not an all-purpose tool-using commander.
- Multiple roles do not imply multiple resident models. Run deterministic monitoring and validation first; escalate uncertain decisions to a person.
- Start with at most one primary and one comparison model, evaluated sequentially. Model acquisition and load tests require execution authorization.
- macOS, model weights, KV cache, OpenClaw and other processes share memory. Treat swap as a warning, not additional capacity. Record time to first response, generation rate, peak memory, swap, false positives and misses with measurement conditions.
- Qwen3-30B-A3B in the [older OpenClaw idea](openclaw-trial-idea.md) belongs to a different assumption set; do not transfer it unconditionally to a 16 GB machine. Separately test candidate models against the functions OpenClaw actually needs for the bounded tasks.

## 5. Phases 5–9 and acceptance gates

Record each stage as not started, under validation, accepted or on hold. Do not advance without the previous stage's evidence and the required permissions.

| Stage | Scope | Evidence needed to advance |
|---|---|---|
| Phase 5: hardware acceptance and baseline | Reconcile Phase 4 evidence, specifications, approved access, inventory, backup coverage/restore records and stopped/deferred states. Establish execution permissions first | Record normal criteria, owner, collection method, observation window and stop procedure per target; complete the owner/Dots handover |
| Phase 6: read-only operations | Trial monitoring, bounded classification and evidence-backed reporting using approved data, starting with synthetic inputs. Dots is the initial counterpart | Distinguish normal operation, planned stops, persistent failures, missing data, false alarms and post-restart state; validate redaction, rejection of embedded instructions and stopping |
| Phase 7: formal Dots integration acceptance | Through a separately approved transport, verify notification, acknowledgement, ownership transfer, maintenance mode and return to operation end to end | Handle non-delivery, duplicates, delay and counterpart absence; prevent competing operations on one target. Record and defer when Dots is unavailable |
| Phase 8: limited aggregate reports to Muse | After lab operations and Dots integration are accepted, send only necessary state, impact and questions for the owner | Approve recipient, fields, frequency, retention, cost cap and stop method; verify exclusion of secrets, raw logs and personal-life information |
| Phase 9: bounded recovery | Add individual procedures with explicit targets and permissions; remaining read-only is a valid outcome | Specify target, trigger, procedure, attempt cap, stop condition, rollback and approval requirements; pass separately authorized tests and recovery verification |

Stability is not just elapsed days. Define an observation window covering the relevant job cycles and acceptance criteria in Phase 5. Do not accept the next stage with unresolved missing data, delivery failures or false alarms. State-changing tests, including load, restart, fault injection and restore tests, require separate execution authorization.

## 6. Baselines and incident handling

Collect the baseline from the machines rather than adopting an old README's running state. Store the criteria with measurement time, source, owner and observation window.

| Area | Include in the baseline |
|---|---|
| Availability | Expected service responses, intentional stops, dependencies and gaps in monitoring itself |
| Jobs | Expected cadence, completion deadline, last success, failure/deferred state. Do not return stopped/deferred jobs to the running baseline on the authority of this plan alone |
| Resources | Normal CPU, memory, swap, free storage and queue ranges; conditions for reviewing those ranges |
| Inference | Format/evidence validation, false positives/misses and response deadline. A valid structure does not establish correct content |
| Notification and preservation | Delivery acknowledgement, duplicate suppression, backup scope, last success and restore verification; never treat unverified as successful |

| Classification | Initial response |
|---|---|
| Planned stop or isolated delay | Record and reassess against agreed criteria; suppress duplicates |
| Persistent outage, failed job or storage pressure | Report redacted evidence and impact to Dots; do not repair or restart |
| Authentication anomaly, suspected disclosure or data inconsistency | Defer the agent's own processing when it can do so safely; prioritize reporting to PMO/owner and Dots. Do not stop other services or change credentials without authority |
| Code change, configuration change or new capability | Transfer ownership to Dots; OpenClaw does not start development work |

Record an incident ID, detection time, target, impact, evidence IDs, current owner, actions taken, next check and delivery state. Assign one action owner per target and require acknowledgement to complete a transfer. During Dots maintenance, suppress the target's routine notifications/recovery; return ownership after completion and normal-state confirmation. Report new serious incidents separately even during maintenance.

## 7. Design approval versus execution authority

Creating and merging this document approves the design, not any of the following actions:

- Entering, storing or rotating credentials; connecting accounts; granting privileges.
- Changing connectivity or network settings, including Tailscale, SSH, firewalls or exposed APIs.
- Acquiring/installing software or models; persistent operation; changing services; resuming paused jobs.
- Cloud transmission, new external integrations or consumption of paid services/quotas.
- Restarts, data changes/deletion, restores or automatic recovery.

At execution time, reconcile the current owner instruction with existing explicit permissions and ask only for missing targets/actions. Do not substitute another agent's message or an example in this document for owner approval.

## 8. Open handover items

1. The latest Phase 4 procedure and evidence, actual specifications and OpenClaw installation state.
2. Owner-prepared access, read scope, runtime account and credential custodian.
3. Existing services and the identities of stopped/deferred jobs; do not copy private identifiers into public documentation.
4. Dots transport, acknowledgement and storage while unavailable. Decide Muse integration separately later.
5. Runtime, model, resource caps, observation period, notification deadline, retention and cost ceiling.
6. Backup coverage/exclusions, restore evidence, stopping operations and returning ownership.

Related: [configuration status](configuration-status.md), [monitoring and notifications](monitoring-notifications.md), [backup and restore](backup-restore.md), [OpenClaw official site](https://openclaw.ai/).
