#!/usr/bin/env python3
"""Offline HTML view of a manual inventory and an AdGuard /control/querylog export.

No network requests. Input files and output contain private metadata: use ignored data/.
Inventory does NOT discover devices or claim that they are currently connected.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024


def load(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("input exceeds 5 MiB; export a smaller time window")
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(querylog, allowed_clients, now):
    if not allowed_clients:
        raise ValueError("explicit consenting client allowlist is required")
    domains = Counter()
    count = 0
    excluded = 0
    for row in querylog["data"]:
        stamp = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("query timestamps must include a timezone")
        if row["client"] not in allowed_clients or not now - timedelta(hours=24) <= stamp <= now:
            excluded += 1
            continue
        domain = row["question"]["name"].rstrip(".").lower()
        if not domain or len(domain) > 253:
            raise ValueError("invalid DNS name")
        domains[domain] += 1
        count += 1
    return {"queries": count, "excluded": excluded, "domains": domains.most_common(50)}


def render(inventory, summary):
    def cell(value):
        return escape(str(value), quote=True)
    rows = []
    for device in inventory["devices"]:
        if device.get("consent") is not True:
            continue
        rows.append("<tr>" + "".join(f"<td>{cell(device.get(key, ''))}</td>"
                    for key in ("label", "role", "source", "last_verified")) + "</tr>")
    domain_rows = "".join(f"<tr><td>{cell(domain)}</td><td>{count}</td></tr>"
                          for domain, count in summary["domains"])
    return f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Network visibility — local report</title>
<style>body{{font:16px system-ui;max-width:960px;margin:3rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #aaa;padding:.6rem;text-align:left}}</style>
<h1>家庭ネットワーク可視化 — ローカルレポート</h1>
<p>手動台帳です。自動探索・現在の接続状態を表すものではありません。</p>
<table><caption>本人が記録を許可した端末</caption><tr><th>名前</th><th>役割</th><th>出典</th><th>確認日</th></tr>{''.join(rows)}</table>
<h2>直近24時間以内のDNS問い合わせ（読み込んだ範囲のみ）</h2>
<p>{summary['queries']} 件、対象外・時間外 {summary['excluded']} 件を除外。上位50ドメイン。</p>
<p>DNS問い合わせは接続成功・全通信量・HTTPS本文の証拠ではありません。キャッシュやDoH等は見えません。</p>
<table><tr><th>問い合わせ名</th><th>回数</th></tr>{domain_rows}</table>
<p>ページ・入力ログは私的データです。共有・Git登録せず、試験後に削除してください。</p></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--querylog", type=Path, required=True)
    parser.add_argument("--allow-client", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(load(args.querylog), set(args.allow_client), datetime.now(timezone.utc))
    content = render(load(args.inventory), result)
    # Private output: no server is started, no raw client IP is rendered in the DNS table.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        os.chmod(args.output, 0o600)
        stream.write(content)
    print("Local report written. Delete inputs and output after the trial.")


if __name__ == "__main__":
    main()
