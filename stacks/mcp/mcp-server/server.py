#!/usr/bin/env python3
"""Minimal read-only MCP server (Streamable HTTP, JSON responses only). stdlib only.

Security model
- Reachable only on an internal Docker network (no published ports, no egress) - see compose.yaml.
- Bearer token per client; each client has a tool allowlist (policy.json). Constant-time token compare.
- Per-client rate limit, request body cap, per-tool timeout, Origin header rejected (DNS-rebinding guard).
- Every request is audited as one JSON line (no tokens, no argument values - only sha256 + size).
- All tools are read-only; file access is confined to a read-only mounted report directory.
"""
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVER_INFO = {"name": "home-ai-lab-mcp", "version": "0.1.0"}
PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_BODY = 64 * 1024
TOOL_TIMEOUT = float(os.environ.get("MCP_TOOL_TIMEOUT", "5"))
REPORT_DIR = os.environ.get("REPORT_DIR", "/data/reports")
AUDIT_DIR = os.environ.get("AUDIT_DIR", "/var/log/mcp")
POLICY_PATH = os.environ.get("MCP_POLICY", "/app/policy.json")
ENABLE_TEST_TOOLS = os.environ.get("MCP_ENABLE_TEST_TOOLS", "") == "true"   # never enable in production
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,199}\.md$")


# ---------------------------------------------------------------- audit
def _make_audit():
    lg = logging.getLogger("audit")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    fmt = logging.Formatter("%(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    lg.addHandler(sh)
    try:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(os.path.join(AUDIT_DIR, "audit.jsonl"), maxBytes=5 * 1024 * 1024, backupCount=5)
        fh.setFormatter(fmt)
        lg.addHandler(fh)
    except OSError as e:
        print(json.dumps({"level": "error", "msg": "audit file unavailable", "error": type(e).__name__}), flush=True)
    return lg


AUDIT = _make_audit()


def audit(**kw):
    kw["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUDIT.info(json.dumps(kw, separators=(",", ":")))


# ---------------------------------------------------------------- policy / clients
def load_clients():
    with open(POLICY_PATH, encoding="utf-8") as f:
        pol = json.load(f)
    clients = {}
    for name, c in pol["clients"].items():
        tok = os.environ.get(c["token_env"], "")
        if len(tok) < 32:
            raise SystemExit(f"token for client '{name}' missing or shorter than 32 chars ({c['token_env']})")
        clients[name] = {"token": tok, "tools": set(c["tools"]), "rate": int(c.get("rate_per_min", 60)), "hits": []}
    return clients


CLIENTS = {}
RATE_LOCK = threading.Lock()


def authenticate(header):
    if not header.startswith("Bearer "):
        return None
    given = header[7:].encode()
    found = None
    for name, c in CLIENTS.items():          # no early exit: compare against every token
        if hmac.compare_digest(given, c["token"].encode()):
            found = name
    return found


def rate_ok(client):
    c = CLIENTS[client]
    now = time.time()
    with RATE_LOCK:
        c["hits"] = [t for t in c["hits"] if now - t < 60]
        if len(c["hits"]) >= c["rate"]:
            return False
        c["hits"].append(now)
    return True


# ---------------------------------------------------------------- tools (read-only)
class ToolError(Exception):
    pass


def t_echo(a):
    text = a.get("text")
    if not isinstance(text, str) or len(text) > 500:
        raise ToolError("text must be a string up to 500 chars")
    return text


def t_server_time(a):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def t_list_reports(a):
    try:
        names = sorted(n for n in os.listdir(REPORT_DIR) if NAME_RE.match(n))
    except FileNotFoundError:
        names = []
    return json.dumps(names)


def t_read_report(a):
    name = a.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ToolError("invalid report name")
    base = os.path.realpath(REPORT_DIR)
    path = os.path.realpath(os.path.join(base, name))
    if os.path.dirname(path) != base or not os.path.isfile(path):
        raise ToolError("report not found")
    with open(path, "rb") as f:
        data = f.read(64 * 1024 + 1)
    if len(data) > 64 * 1024:
        raise ToolError("report too large")
    return data.decode("utf-8", "replace")


def t_selftest_sleep(a):
    time.sleep(float(a.get("seconds", 1)))
    return "slept"


def _schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


TOOLS = {
    "echo": ("Return the given text unchanged (connectivity test).", _schema({"text": {"type": "string", "maxLength": 500}}, ["text"]), t_echo),
    "server_time": ("Current server time in UTC.", _schema({}), t_server_time),
    "list_reports": ("List available Markdown reports (read-only).", _schema({}), t_list_reports),
    "read_report": ("Read one Markdown report by file name (read-only, max 64 KiB).", _schema({"name": {"type": "string"}}, ["name"]), t_read_report),
}
if ENABLE_TEST_TOOLS:
    TOOLS["selftest_sleep"] = ("TEST ONLY: sleep.", _schema({"seconds": {"type": "number"}}), t_selftest_sleep)


def tool_descriptor(name):
    desc, schema, _ = TOOLS[name]
    return {"name": name, "description": desc, "inputSchema": schema,
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}}


def unexpected_arguments(schema, args):
    """Argument names the advertised inputSchema forbids (additionalProperties: false).
    Checked before the tool runs, so a call the schema rejects never executes."""
    if schema.get("additionalProperties") is not False:
        return []
    allowed = schema.get("properties", {})
    return sorted(k for k in args if k not in allowed)


def unexpected_arguments_message(keys):
    shown = ", ".join(json.dumps(k[:40]) for k in keys[:5])       # bounded echo of the client's own key names
    more = f" (+{len(keys) - 5} more)" if len(keys) > 5 else ""
    return f"unexpected argument(s) not allowed by input schema: {shown}{more}"


def run_with_timeout(fn, args):
    box = {}

    def target():
        try:
            box["ok"] = fn(args)
        except ToolError as e:
            box["tool_error"] = str(e)
        except Exception as e:  # noqa: BLE001
            box["crash"] = type(e).__name__

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(TOOL_TIMEOUT)
    if th.is_alive():
        return "timeout", None
    if "ok" in box:
        return "ok", box["ok"]
    if "tool_error" in box:
        return "tool_error", box["tool_error"]
    return "crash", box.get("crash")


# ---------------------------------------------------------------- HTTP
def rpc_error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


class Handler(BaseHTTPRequestHandler):
    timeout = 10
    server_version = "mcp/0.1"

    def log_message(self, *a):
        pass

    def _send(self, status, obj=None, headers=None):
        body = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(status)
        if obj is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        self._send(405 if self.path == "/mcp" else 404, {"error": "not allowed"}, {"Allow": "POST"} if self.path == "/mcp" else None)

    do_DELETE = do_GET

    def do_POST(self):
        t0 = time.time()
        ip = self.client_address[0]
        ev = {"ip": ip, "client": None, "method": None, "tool": None, "status": "error", "http": 500}
        try:
            if self.path != "/mcp":
                ev["http"] = 404
                return self._send(404, {"error": "not found"})
            if self.headers.get("Origin"):
                ev.update(status="denied_origin", http=403)
                return self._send(403, {"error": "origin not allowed"})
            client = authenticate(self.headers.get("Authorization", ""))
            if client is None:
                ev.update(status="auth_fail", http=401)
                return self._send(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
            ev["client"] = client
            if not rate_ok(client):
                ev.update(status="rate_limited", http=429)
                return self._send(429, {"error": "rate limit"}, {"Retry-After": "30"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = -1
            if n < 0 or n > MAX_BODY:
                ev.update(status="too_large", http=413)
                return self._send(413, {"error": "body too large"})
            raw = self.rfile.read(n)
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                ev.update(status="parse_error", http=200)
                return self._send(200, rpc_error(None, -32700, "parse error"))
            if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
                ev.update(status="invalid_request", http=200)
                return self._send(200, rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request (batches unsupported)"))
            method, rid = msg["method"], msg.get("id")
            params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
            ev["method"] = method
            if rid is None:                       # notification
                ev.update(status="ok", http=202)
                return self._send(202)
            if method == "initialize":
                want = params.get("protocolVersion")
                ver = want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
                res = {"protocolVersion": ver, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO}
            elif method == "ping":
                res = {}
            elif method == "tools/list":
                res = {"tools": [tool_descriptor(t) for t in TOOLS if t in CLIENTS[client]["tools"]]}
            elif method == "tools/call":
                name = params.get("name")
                raw_args = params.get("arguments") if "arguments" in params else {}   # omitted -> {}
                args_is_object = isinstance(raw_args, dict)    # present but not an object (list/str/number/null) is rejected below
                args = raw_args if args_is_object else {}
                ev["tool"] = name if isinstance(name, str) and len(name) < 64 else "?"
                ev["args_sha256"] = hashlib.sha256(json.dumps(raw_args, sort_keys=True).encode()).hexdigest()[:16]
                ev["args_bytes"] = len(json.dumps(raw_args))
                if name not in TOOLS:
                    ev.update(status="unknown_tool", http=200)
                    return self._send(200, rpc_error(rid, -32602, "unknown tool"))
                if name not in CLIENTS[client]["tools"]:
                    ev.update(status="denied_tool", http=200)
                    return self._send(200, rpc_error(rid, -32003, "tool not permitted for this client"))
                if not args_is_object:                         # malformed request params -> JSON-RPC error
                    ev.update(status="invalid_params", http=200)
                    return self._send(200, rpc_error(rid, -32602, "invalid params: arguments must be an object"))
                extra = unexpected_arguments(TOOLS[name][1], args)
                if extra:                                      # schema violation -> tool result with isError, tool not run
                    state, out = "tool_error", unexpected_arguments_message(extra)
                    ev["status"] = "invalid_arguments"
                else:
                    state, out = run_with_timeout(TOOLS[name][2], args)
                    ev["status"] = state
                if state == "timeout":
                    return self._send(200, rpc_error(rid, -32002, "tool timed out"))
                if state == "crash":
                    return self._send(200, rpc_error(rid, -32603, "internal error"))
                res = {"content": [{"type": "text", "text": out}], "isError": state == "tool_error"}
            else:
                ev.update(status="unknown_method", http=200)
                return self._send(200, rpc_error(rid, -32601, "method not found"))
            if ev["status"] == "error":
                ev["status"] = "ok"
            ev["http"] = 200
            self._send(200, {"jsonrpc": "2.0", "id": rid, "result": res})
        except Exception as e:  # noqa: BLE001
            ev["status"] = "crash:" + type(e).__name__
            try:
                self._send(500, {"error": "internal error"})
            except Exception:  # noqa: BLE001
                pass
        finally:
            ev["ms"] = int((time.time() - t0) * 1000)
            audit(**ev)


def main():
    CLIENTS.update(load_clients())
    audit(event="start", clients=sorted(CLIENTS), tools=sorted(TOOLS), test_tools=ENABLE_TEST_TOOLS)
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
