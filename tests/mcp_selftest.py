#!/usr/bin/env python3
"""Local self-test for stacks/mcp/mcp-server/server.py (no Docker). Run: python tests/mcp_selftest.py
Starts the server on a throwaway port with temp report/audit dirs and a test policy."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "stacks", "mcp", "mcp-server", "server.py")
PORT = 18090
BASE = f"http://127.0.0.1:{PORT}"
TOK_A = "a" * 40
TOK_B = "b" * 40
SECRET_ARG = "SUPER-SECRET-ARGUMENT-VALUE"
SECRET_EXTRA = "SUPER-SECRET-EXTRA-KEY-VALUE"
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        fails.append(name)


def http(method, path, body=None, token=None, headers=None, raw=None):
    h = dict(headers or {})
    if token:
        h["Authorization"] = "Bearer " + token
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None:
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt


def rpc(method, params=None, token=TOK_A, rid=1):
    return http("POST", "/mcp", {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, token)


def call(tool, args=None, token=TOK_A):
    return rpc("tools/call", {"name": tool, "arguments": args or {}}, token)


def main():
    tmp = tempfile.mkdtemp()
    reports, audit_dir = os.path.join(tmp, "reports"), os.path.join(tmp, "audit")
    os.makedirs(reports)
    open(os.path.join(reports, "demo__repo.md"), "w").write("# demo\n- ok\n")
    open(os.path.join(tmp, "outside.md"), "w").write("SHOULD NOT BE READABLE")
    policy = os.path.join(tmp, "policy.json")
    json.dump({"clients": {
        "alpha": {"token_env": "TA", "tools": ["echo", "server_time", "list_reports", "read_report", "selftest_sleep"], "rate_per_min": 1000},
        "beta": {"token_env": "TB", "tools": ["echo", "list_reports"], "rate_per_min": 5},
    }}, open(policy, "w"))
    env = dict(os.environ, TA=TOK_A, TB=TOK_B, MCP_POLICY=policy, REPORT_DIR=reports, AUDIT_DIR=audit_dir,
               PORT=str(PORT), MCP_TOOL_TIMEOUT="1", MCP_ENABLE_TEST_TOOLS="true")
    p = subprocess.Popen([sys.executable, SERVER], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                if http("GET", "/healthz")[0] == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        check("healthz is open and minimal", http("GET", "/healthz") == (200, {"ok": True}))
        check("no token -> 401", http("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401)
        check("bad token -> 401", http("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="x" * 40)[0] == 401)
        check("Origin header -> 403", http("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, TOK_A, {"Origin": "http://evil.example"})[0] == 403)
        check("GET /mcp -> 405", http("GET", "/mcp")[0] == 405)
        s, r = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        check("initialize negotiates version", s == 200 and r["result"]["protocolVersion"] == "2025-03-26")
        s, r = rpc("initialize", {"protocolVersion": "1999-01-01"})
        check("initialize falls back to supported version", r["result"]["protocolVersion"] == "2025-06-18")
        check("notification -> 202", http("POST", "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"}, TOK_A)[0] == 202)
        s, r = rpc("tools/list")
        names = sorted(t["name"] for t in r["result"]["tools"])
        check("alpha sees its 5 tools", names == ["echo", "list_reports", "read_report", "selftest_sleep", "server_time"], names)
        check("all tools advertise readOnlyHint", all(t["annotations"]["readOnlyHint"] for t in r["result"]["tools"]))
        s, r = rpc("tools/list", token=TOK_B)
        check("beta sees only its allowlist", sorted(t["name"] for t in r["result"]["tools"]) == ["echo", "list_reports"])
        s, r = call("echo", {"text": SECRET_ARG})
        check("echo works", r["result"]["content"][0]["text"] == SECRET_ARG)
        s, r = call("read_report", {"name": "demo__repo.md"})
        check("alpha reads a report", "# demo" in r["result"]["content"][0]["text"])
        s, r = call("read_report", {"name": "demo__repo.md"}, TOK_B)
        check("beta denied read_report (-32003)", r.get("error", {}).get("code") == -32003)
        for bad in ["../outside.md", "..%2foutside.md", "a/b.md", ".hidden.md", "x.txt", "/etc/passwd", "outside.md\x00.md"]:
            s, r = call("read_report", {"name": bad})
            check(f"read_report rejects {bad!r}", r["result"]["isError"] is True)
        s, r = call("list_reports")
        check("list_reports lists only .md in dir", json.loads(r["result"]["content"][0]["text"]) == ["demo__repo.md"])
        check("unknown tool -> -32602", call("rm_rf")[1]["error"]["code"] == -32602)
        check("unknown method -> -32601", rpc("resources/list")[1]["error"]["code"] == -32601)
        check("invalid JSON -> -32700", http("POST", "/mcp", raw=b"{nope", token=TOK_A)[1]["error"]["code"] == -32700)
        check("batch rejected -> -32600", http("POST", "/mcp", [{"jsonrpc": "2.0", "id": 1, "method": "ping"}], TOK_A)[1]["error"]["code"] == -32600)
        check("oversize body -> 413", http("POST", "/mcp", raw=b"x" * (70 * 1024), token=TOK_A)[0] == 413)

        # ---- argument validation: inputSchema additionalProperties:false is enforced before the tool runs.
        # Shapes: extra key / schema violation -> result.isError:true (model-correctable tool input error, as the
        # official SDK does); non-object `arguments` -> JSON-RPC -32602 (malformed request params);
        # omitted `arguments` -> treated as {} (the tool's own required/type checks then apply).
        def tres(r):
            return r["result"]["content"][0]["text"], r["result"]["isError"]

        ok_cases = {"echo": {"text": "ok"}, "server_time": {}, "list_reports": {},
                    "read_report": {"name": "demo__repo.md"}, "selftest_sleep": {"seconds": 0}}
        for tool, good in ok_cases.items():
            s, r = call(tool, good)
            check(f"{tool}: declared arguments still succeed", s == 200 and "result" in r and tres(r)[1] is False, r)
            s, r = call(tool, dict(good, unexpected=True, note=SECRET_EXTRA))
            txt = tres(r)[0] if "result" in r else ""
            check(f"{tool}: extra keys -> result.isError, not a JSON-RPC error", s == 200 and "error" not in r and tres(r)[1] is True, r)
            check(f"{tool}: extra-key rejection comes from the validator, tool output not returned", txt.startswith("unexpected argument(s)") and '"unexpected"' in txt, txt)
        s, r = call("echo", {"unexpected": True})
        check("echo: extra key without required text -> unexpected-argument error", tres(r)[1] is True and tres(r)[0].startswith("unexpected argument(s)"), r)
        s, r = call("server_time", {f"k{i}": i for i in range(20)})
        check("many extra keys -> bounded message", tres(r)[1] is True and len(tres(r)[0]) <= 300 and "+15 more" in tres(r)[0], r)
        t0 = time.time()
        s, r = call("selftest_sleep", {"seconds": 4, "unexpected": True})
        check("selftest_sleep + extra key is rejected before running (no -32002 timeout)", "result" in r and tres(r)[1] is True and time.time() - t0 < 0.8, f"{time.time()-t0:.1f}s")

        for bad in [[], [1], "x", 123, True, None]:
            for tool in ("echo", "server_time"):
                s, r = rpc("tools/call", {"name": tool, "arguments": bad})
                check(f"{tool}: non-object arguments {bad!r} -> -32602", s == 200 and r.get("error", {}).get("code") == -32602 and "result" not in r, r)
        s, r = rpc("tools/call", {"name": "server_time"})
        check("server_time: omitted arguments is accepted", "result" in r and tres(r)[1] is False, r)
        s, r = rpc("tools/call", {"name": "list_reports"})
        check("list_reports: omitted arguments is accepted", "result" in r and tres(r)[1] is False, r)
        s, r = rpc("tools/call", {"name": "echo"})
        s2, r2 = call("echo", {})
        check("echo: omitted arguments -> isError (required text), same as {}", "result" in r and tres(r)[1] is True and tres(r) == tres(r2) and "text must be a string" in tres(r)[0], r)
        s, r = rpc("tools/call", {"name": "read_report"})
        check("read_report: omitted arguments -> isError (required name)", "result" in r and tres(r)[1] is True and "invalid report name" in tres(r)[0], r)

        # existing required / type / size validation is unchanged
        check("echo: non-string text -> isError", tres(call("echo", {"text": 123})[1])[1] is True)
        check("echo: 500 chars ok / 501 chars -> isError", tres(call("echo", {"text": "x" * 500})[1])[1] is False and tres(call("echo", {"text": "x" * 501})[1])[1] is True)
        check("read_report: non-string name -> isError", tres(call("read_report", {"name": 123})[1])[1] is True)
        for size, expect_err in ((64 * 1024, False), (64 * 1024 + 1, True)):
            big = os.path.join(reports, "big.md")
            open(big, "wb").write(b"a" * size)
            s, r = call("read_report", {"name": "big.md"})
            check(f"read_report: {size} byte report -> isError={expect_err}", tres(r)[1] is expect_err and (not expect_err or "too large" in tres(r)[0]), r)
            os.remove(big)

        # auth / allowlist / unknown-tool still win over argument validation (no schema detail leaks to a denied client)
        s, r = call("read_report", {"name": "demo__repo.md", "unexpected": True}, TOK_B)
        check("beta + read_report + extra key -> -32003 (allowlist first)", r.get("error", {}).get("code") == -32003, r)
        s, r = rpc("tools/call", {"name": "read_report", "arguments": []}, TOK_B)
        check("beta + read_report + non-object arguments -> -32003 (allowlist first)", r.get("error", {}).get("code") == -32003, r)
        s, r = call("rm_rf", {"unexpected": True})
        check("unknown tool + extra key -> -32602 unknown tool", r.get("error", {}).get("code") == -32602 and r["error"]["message"] == "unknown tool", r)
        check("extra key without a token -> 401", http("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "ok", "unexpected": True}}})[0] == 401)

        t0 = time.time()
        s, r = call("selftest_sleep", {"seconds": 4})
        check("tool timeout -> -32002 within ~1s", r.get("error", {}).get("code") == -32002 and time.time() - t0 < 3, f"{time.time()-t0:.1f}s")
        codes = [rpc("ping", token=TOK_B)[0] for _ in range(8)]   # beta already used several calls
        check("rate limit -> 429", 429 in codes, codes)

        time.sleep(0.3)
        log = open(os.path.join(audit_dir, "audit.jsonl")).read()
        lines = [json.loads(x) for x in log.splitlines() if x.strip()]
        check("audit log written", len(lines) > 20)
        check("audit has no tokens", TOK_A not in log and TOK_B not in log)
        check("audit has no raw argument values", SECRET_ARG not in log)
        check("audit records denials", any(x.get("status") == "denied_tool" for x in lines) and any(x.get("status") == "auth_fail" for x in lines))
        check("audit records tool + client + hash", any(x.get("tool") == "echo" and x.get("client") == "alpha" and x.get("args_sha256") for x in lines))
        check("audit has no extra-argument values or key names", SECRET_EXTRA not in log and '"unexpected"' not in log)
        check("audit records invalid_arguments with tool + hash + size only",
              any(x.get("status") == "invalid_arguments" and x.get("tool") == "echo" and x.get("args_sha256") and x.get("args_bytes") for x in lines))
        check("audit records invalid_params (non-object arguments)", any(x.get("status") == "invalid_params" and x.get("args_sha256") for x in lines))
    finally:
        p.terminate()
    print(f"\n{len(fails)} failure(s)" if fails else "\nALL PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
