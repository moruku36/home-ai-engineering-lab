# Off-device backup options / NUC外バックアップの選択肢

English first, Japanese below. **This document compares options only. No destination has been chosen, no account was created and no credential was requested.** / 英語が先、日本語が後。**選択肢の比較のみです。保存先は未決定で、アカウント作成も認証情報の要求もしていません。**

## Where we are / 現状

- **EN:** A daily encrypted backup (timer 03:30 **UTC = 12:30 JST** + up to 10 min random delay) is written to `/var/backups/home-ai-lab` on the NUC (7 generations, ~9 MB each today, 24 MB for 4 files). It is encrypted with `age` to a **public key**; the private key is kept by you outside the NUC. Restore tests pass. **If the NUC's disk dies or the NUC is stolen, the backups are lost with it.**
- **JA:** 毎晩（03:30 UTC ＝ 日本時間 12:30）、暗号化バックアップを NUC 内の `/var/backups/home-ai-lab` に保存（7世代、1回あたり約9MB）。`age` の**公開鍵**で暗号化され、秘密鍵はあなたが NUC の外で保管。復元試験は合格。**NUC のディスク故障・盗難では、バックアップも一緒に失われます。**

Because the archives are already encrypted, **the provider never sees plaintext** — the choice is about availability, cost and the credential you must put on the NUC.
アーカイブは暗号化済みなので、**保存先に平文は渡りません**。選択の観点は、可用性・費用・NUC に置く認証情報です。

## Comparison / 比較

| Option | Extra cost | Credential stored on the NUC | Restore effort | Notes |
|---|---|---|---|---|
| **A. USB disk / second PC at home** (`scp`/`rsync` over SSH) | 0 if you already own the hardware | An SSH key limited to one directory | easy | Survives disk failure, **not** fire/theft/flood at home. Disk must stay attached/online. |
| **B. Existing cloud storage via `rclone`** (e.g. a personal Google Drive / OneDrive you already pay for) | 0 | An OAuth token for that account (can be scoped to one folder where the provider supports it) | easy | Uses a subscription you already have; offsite. A leaked token exposes that storage — scope it. |
| **C. Free tier of an object-storage service** (e.g. Backblaze B2, a free quota) | 0 within the free quota (**verify current limits before use — not checked in this work**) | An application key restricted to one bucket (write-only is possible) | medium | Cleanest least-privilege option (write-only key). Needs a new account → your decision. |
| **D. A private GitHub repository** | 0 | A write token — **conflicts with the project rule "no GitHub write access"** | easy | Not recommended: size/ToS limits for large binaries and a write credential on the NUC. |
| **E. Manual copy** (you pull the newest `*.tar.age` to your PC weekly with `scp`) | 0 | none on the NUC | manual | No automation, but no new credential; depends on you remembering. |

**Suggested order of preference (not a decision) / 推奨の順（決定ではない）:** C with a write-only key, or A if you have spare hardware; B if you would rather reuse a subscription; E as a stop-gap. D is not recommended. / 書き込み専用キーの C、予備ハードがあれば A、既存サブスクを使うなら B、つなぎとして E。D は非推奨。

## What I need from you to proceed / 進めるために必要なこと

1. Choose A–E (or another). / A〜E のどれにするか。
2. Create the account/credential yourself with the narrowest scope. The credential is entered **on the NUC at a hidden prompt** (same pattern as `jobs-admin.sh`) — never in chat or Git. / 認証情報は最小権限で自分で作成し、**NUC 上の非表示入力**で登録（チャット・Git には入れない）。
3. I then add a transfer step after the nightly backup, a retention rule for the remote side, and a restore test **from the remote copy**. / その後、バックアップ後の転送、保存先側の保持ルール、**保存先のコピーからの復元試験**を追加します。

## Manual stop-gap today (option E) / 今日できる手動のつなぎ（E）

`/var/backups` is root-only, so first make a user-readable copy on the NUC, then fetch it with `scp` (a plain file copy keeps the binary intact; do **not** pipe `ssh -t` output into a file):
`/var/backups` は root 専用なので、NUC 上でまず自分用のコピーを作り、`scp` で取得します（`ssh -t` の出力をファイルへパイプすると壊れるので避ける）。

```bash
# on the NUC (sudo password prompt):
f=$(sudo ls -t /var/backups/home-ai-lab/*.tar.age | head -1)
sudo cp "$f" "$f.sha256" ~/ && sudo chown "$USER": ~/"$(basename "$f")" ~/"$(basename "$f").sha256"
# on your PC:
scp <user>@<nuc>:'~/home-ai-lab-*.tar.age*' .
# verify, then (later) delete the copies on the NUC:   sha256sum -c home-ai-lab-<ts>.tar.age.sha256
```
The private key (kept off the NUC) is needed to open it: `age -d -i <your-key> <file>.tar.age | tar -tf -`. / 復号には NUC 外に保管した秘密鍵が必要です。
