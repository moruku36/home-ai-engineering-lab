# Operations runbook / 運用手順書

English first, Japanese below each section. Measured on the NUC on 2026-10-15. / 各節は英語が先、日本語が後。実機での実測値（2026-10-15）。

All commands run **on the NUC** over SSH (`sudo` asks for your password). Scripts live in `~/` (copies of `scripts/` in this repo).

## 1. Open WebUI: stop / start

**Current state: stopped on purpose.** Container, volume `open-webui_open-webui-data` (chats, the admin user), `.env` and `secrets/` are all kept. Nothing was deleted.

| Goal | Command | What it does |
|---|---|---|
| See state | `bash ~/ops-open-webui.sh status` | container state, restart policy, volume name |
| **Start again** | `bash ~/ops-open-webui.sh start` | `docker compose start` → same container, waits for `healthy` |
| Stop again | `bash ~/ops-open-webui.sh stop` | `docker compose stop` |
| Re-enable its Kuma monitor | Kuma → *Open WebUI (health)* → **Resume** | it was **paused** to avoid false alarms |
| Open it | SSH tunnel `-L 8300:127.0.0.1:8300` → `http://localhost:8300` | |

- **EN:** Restart policy is `unless-stopped`, so a container stopped by hand is not started by Docker after a reboot (Docker's documented behaviour; **not tested by rebooting**). The nightly backup **no longer restarts it** (it only restarts stacks that were running before the backup; verified on the NUC).
- **EN:** Never run `docker compose down -v` or `docker volume rm` on it — that deletes the chat data.
- **JA:** 再起動方針は `unless-stopped`。手動で止めたコンテナは、再起動後も Docker は起動しません（Docker の仕様。**再起動での実証はしていません**）。夜間バックアップは、バックアップ前に動いていたスタックしか再起動しません（実機で確認）。`down -v` や `docker volume rm` は、チャットデータが消えるので使わないこと。
- Cost of keeping it: **disk** — the image (~4 GB, part of Docker's 5.33 GB of images) stays; **RAM** is freed (see §2). Removing the image is possible later but was **not done** (it needs your approval and would slow a restart).

## 2. Resource baseline (measured) / 資源の基準値（実測）

| | Before (Open WebUI running, 2026-10-15 22:15 UTC) | After (stopped) |
|---|---|---|
| Host memory used | 1.7 GiB of 30 GiB | **1.5 GiB** |
| Open WebUI | 294 MiB (limit 2 GiB) | – |
| n8n | 385 MiB (limit 1 GiB) | 364–486 MiB (varies after restarts) |
| Uptime Kuma | 121 MiB (limit 512 MiB) | 111–122 MiB |
| MCP server | 33 MiB (limit 128 MiB) | 16–33 MiB |
| python-jobs | 32 MiB (limit 256 MiB) | 16–21 MiB |
| CPU (all containers) | < 1 % each (n8n 35 % right after a restart) | same |
| Disk `/` | 17 G of 98 G used (18 %) | **17 G (unchanged: image and volume kept)** |
| Docker images | 5.33 GB | 5.33 GB |
| Docker volumes | 9.1 MB | 9.1 MB + `jobs-state` |
| Encrypted backups | 24 MB (4 files) | grows ~9 MB per backup; 7 kept (~65 MB) |
| Container logs | < 130 KB each | same |
| journald | 53.6 MB | same |

- **EN:** Plenty of headroom (30 GiB RAM, 77 G free). The only meaningful saving from stopping Open WebUI is ~0.3 GiB RAM.
- **JA:** 余裕は十分（RAM 30GiB、空き 77G）。Open WebUI 停止で実質的に減るのは RAM 約 0.3GiB です。
- Re-measure any time: `bash ~/ops-status.sh [label]` (saves `~/ops-status-<label>-<time>.txt`, contains no secrets).

## 3. Logs and storage / ログとストレージ

| What | Rotation | Checked |
|---|---|---|
| Container logs (json-file) | 10 MB × 3 per container (set in every compose file) | ✅ sizes are KB-level |
| MCP audit log | 5 MB × 5 (`/var/log/mcp/audit.jsonl`) | ✅ restore-tested |
| GitHub reports / snapshots | newest 60 / 30 | ✅ tested (fake API) |
| Backups | newest 7 (`KEEP`) | ✅ |
| systemd journal | Ubuntu defaults | 53.6 MB |

Rule of thumb: act if `/` passes 70 %, or any container log exceeds ~30 MB. `bash ~/ops-status.sh` shows both.
目安：`/` が 70% を超える、またはコンテナログが約30MBを超えたら対処。`ops-status.sh` で両方確認できます。

## 4. Updates without surprises / 予期しない停止を避ける更新

| Layer | Policy | State |
|---|---|---|
| Ubuntu security updates | `unattended-upgrades` (daily lists + security origins) | enabled (daily package-list update + unattended security upgrades); the dry run printed no output, so nothing was pending or it could not be shown — **not otherwise verified** |
| Automatic reboot | **off** (no `Automatic-Reboot` line is active) | ✅ — check `ls /var/run/reboot-required`; reboot yourself in a quiet moment |
| Container images | **pinned tags**, never auto-updated (no Watchtower) | ✅ |
| Kernel/Docker upgrades | manual | after a *backup*; then `bash ~/ops-status.sh` |

Manual update routine / 手動更新の手順: ① `sudo /usr/local/sbin/home-ai-lab-backup` ② `sudo apt update && sudo apt upgrade` ③ if `reboot-required` exists, reboot ④ confirm Kuma is green and `bash ~/ops-status.sh`. Containers come back by themselves (`restart: unless-stopped`). A reboot test on 2026-10-15 proved this for Kuma and the services of that time; n8n/MCP/python-jobs in their current form have **not** been rebooted since.

## 5. Manual recovery / 手動復旧

| Symptom | Do |
|---|---|
| A container is unhealthy | `sudo docker logs --tail 50 <name>` → `cd ~/home-ai-lab/<stack> && sudo docker compose up -d` (stacks: `uptime-kuma`, `n8n`, `mcp`, `open-webui`) |
| n8n workflow did not run | n8n → *Executions*; run manually; check the Kuma push monitor and `docker logs python-jobs` |
| GitHub report says PARTIAL | Rate limit; add a read-only token or re-run after the hour ([github-monitoring.md](github-monitoring.md)) |
| Lost an SSH tunnel after a reboot | re-run the `ssh -N -L …` command on your PC |
| Disk almost full | `sudo docker system df`; old backups are pruned automatically; do **not** delete volumes |
| NUC does not boot / disk dead | Reinstall Ubuntu + Docker (`scripts/phase2a-docker.sh`), restore from a backup: [backup-restore.md](backup-restore.md) — **needs the private key you keep off the NUC; and an off-device copy, which does not exist yet** ([offsite-backup-options.md](offsite-backup-options.md)) |

## 6. Rollback of the changes made in this phase / 今回の変更のロールバック

| Change | Rollback |
|---|---|
| Open WebUI stopped | `bash ~/ops-open-webui.sh start`, resume its Kuma monitor |
| GitHub collector + workflow | deactivate the workflow in n8n; `jobs-admin.sh remove-*`; the job is harmless unused |
| `python-jobs` on `monitor-net`, new `jobs-state` volume | revert `stacks/n8n/compose.yaml` and `docker compose up -d`; the volume can stay |
| Fixed backup script | previous version is in Git history (it restarted every stack, including Open WebUI) |
| Kuma monitors (retries 2, push monitor, paused one) | edit/delete in the Kuma UI |
| Heartbeat | `heartbeat-admin.sh disable` (never enabled so far) |
