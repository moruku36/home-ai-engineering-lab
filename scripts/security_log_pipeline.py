#!/usr/bin/env python3
"""Offline-capable security log preprocessor, deterministic rule detector,
and strict validation pipeline for local AI security log analysis.

Stdlib only. Zero third-party dependencies.
Never executes external OS commands; never modifies system files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

# Patterns for secret and PII redaction
TOKEN_PATTERNS = [
    # High-entropy API tokens / passwords / bearer strings
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password|passwd|pwd|secret|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{6,}['\"]?", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"ssh-(?:ed25519|rsa)\s+AAAA[0-9A-Za-z+/]{20,}", re.IGNORECASE), "[REDACTED_SSH_KEY]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
    # Private IP addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x) - preserving loopback and doc IPs
    (re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})\b"), "[REDACTED_PRIVATE_IP]"),
]

# Prompt injection heuristic detection patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"(?:you\s+are\s+now|act\s+as)\s+(?:an?\s+)?(?:admin|root|system|evaluator|developer\s+mode)", re.IGNORECASE),
    re.compile(r"(?:set\s+severity\s+to|output\s+severity\s*:?\s*)[\'\"]?(?:info|low)[\'\"]?", re.IGNORECASE),
    re.compile(r"(?:system\s+override|maintenance\s+override|sudo\s+mode)", re.IGNORECASE),
]

# SSH brute force detection regex
SSH_FAILED_RE = re.compile(
    r"Failed\s+(?:password|publickey)\s+for\s+(?:invalid\s+user\s+)?([A-Za-z0-9._-]+)\s+from\s+([^\s]+)\s+port\s+(\d+)",
    re.IGNORECASE
)
SUDO_FAILURE_RE = re.compile(
    r"sudo:\s+([A-Za-z0-9._-]+)\s*:\s*(?:incorrect password|authentication failure|\d+\s+incorrect password attempts)",
    re.IGNORECASE
)


class SecurityPipelineError(Exception):
    """Base error for security pipeline operations."""
    pass


class EvidenceValidationError(SecurityPipelineError):
    """Raised when LLM finding references non-existent or hallucinated evidence."""
    pass


def normalize_utc(timestamp_str: str, default_year: int = 2026) -> str:
    """Normalize various log timestamp formats (syslog BSD, ISO 8601, Docker) to ISO 8601 UTC string.
    
    Returns standard string like '2026-10-19T03:14:00Z'.
    """
    cleaned = timestamp_str.strip()
    
    # 1. ISO 8601 format (e.g., 2026-10-19T03:14:00.123456Z or +09:00)
    if "T" in cleaned:
        iso_candidate = cleaned.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    # 2. Syslog BSD format: 'Oct 19 03:14:00'
    syslog_pattern = r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})"
    match = re.match(syslog_pattern, cleaned)
    if match:
        month_str, day_str, time_str = match.groups()
        try:
            full_str = f"{default_year} {month_str} {int(day_str):02d} {time_str}"
            dt = datetime.strptime(full_str, "%Y %b %d %H:%M:%S").replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    # 3. YYYY-MM-DD HH:MM:SS format
    try:
        dt = datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass

    # Fallback to deterministic timestamp representation
    return f"{default_year}-01-01T00:00:00Z"


def redact_sensitive_data(text: str) -> str:
    """Mask tokens, secrets, private IP ranges, passwords, and private keys."""
    redacted = text
    for pattern, replacement in TOKEN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def parse_and_preprocess_logs(raw_lines: List[str], source: str = "syslog") -> List[Dict[str, Any]]:
    """Parse raw log lines, normalize timestamps, redact secrets, and compute stable 8-char hashes."""
    preprocessed = []
    for idx, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        
        redacted = redact_sensitive_data(line)
        line_hash = hashlib.sha256(redacted.encode("utf-8")).hexdigest()[:8]
        
        # Extract timestamp prefix if present
        first_token = line.split()[0] if line.split() else ""
        if len(line.split()) >= 3 and line[:3] in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
            ts_str = " ".join(line.split()[:3])
            norm_ts = normalize_utc(ts_str)
        elif "T" in first_token:
            norm_ts = normalize_utc(first_token)
        else:
            norm_ts = normalize_utc("2026-10-19T00:00:00Z")

        preprocessed.append({
            "line_no": idx,
            "raw_hash": line_hash,
            "timestamp": norm_ts,
            "source": source,
            "content": redacted
        })
    return preprocessed


def detect_deterministic_rules(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute signature and rule-based anomaly detection before any LLM is called.
    
    Guarantees deterministic, reproducible detection of high-risk patterns.
    """
    findings: List[Dict[str, Any]] = []
    
    # 1. SSH Auth Failures
    ssh_failures: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        m = SSH_FAILED_RE.search(entry["content"])
        if m:
            user, ip, port = m.groups()
            ssh_failures.setdefault(ip, []).append(entry)

    for ip, fails in ssh_failures.items():
        if len(fails) >= 3:
            refs = [
                {"line_no": f["line_no"], "raw_hash": f["raw_hash"], "log_excerpt": f["content"][:200]}
                for f in fails[:5]
            ]
            content_sig = f"ssh_bruteforce_{ip}_{fails[0]['timestamp']}_{len(fails)}"
            event_id = "rule-ssh-bruteforce-" + hashlib.sha256(content_sig.encode()).hexdigest()[:8]
            findings.append({
                "event_id": event_id,
                "source": "sshd",
                "timestamp": fails[-1]["timestamp"],
                "event_type": "auth_bruteforce",
                "severity": "high",
                "summary": f"Detected {len(fails)} repeated SSH authentication failures from host/IP {ip}",
                "evidence_refs": refs,
                "suspected_cause": f"Potential brute-force or credential stuffing against user accounts from source {ip}",
                "recommended_actions": [
                    f"Check UFW firewall rules to ensure port 22 is restricted to trusted LAN only",
                    f"Confirm SSH public key only authentication is enforced (PasswordAuthentication no)",
                    f"Inspect auth.log for further activity"
                ],
                "needs_human_review": True
            })

    # 2. Sudo Authentication Failures
    for entry in entries:
        m = SUDO_FAILURE_RE.search(entry["content"])
        if m:
            user = m.group(1)
            event_id = "rule-sudo-failure-" + hashlib.sha256(f"sudo_{user}_{entry['raw_hash']}".encode()).hexdigest()[:8]
            findings.append({
                "event_id": event_id,
                "source": "auth",
                "timestamp": entry["timestamp"],
                "event_type": "sudo_failure",
                "severity": "medium",
                "summary": f"Authentication failure for sudo command invocation by user '{user}'",
                "evidence_refs": [{
                    "line_no": entry["line_no"],
                    "raw_hash": entry["raw_hash"],
                    "log_excerpt": entry["content"][:200]
                }],
                "suspected_cause": f"User '{user}' entered incorrect credentials or attempted unauthorized privilege escalation",
                "recommended_actions": [
                    f"Verify whether user '{user}' is authorized in sudoers",
                    f"Review preceding terminal sessions or SSH logs"
                ],
                "needs_human_review": True
            })

    # 3. Adversarial Prompt Injection in Logs
    for entry in entries:
        content = entry["content"]
        for p in PROMPT_INJECTION_PATTERNS:
            if p.search(content):
                event_id = "rule-prompt-injection-" + hashlib.sha256(f"prompt_inj_{entry['raw_hash']}".encode()).hexdigest()[:8]
                findings.append({
                    "event_id": event_id,
                    "source": entry["source"],
                    "timestamp": entry["timestamp"],
                    "event_type": "prompt_injection_attempt",
                    "severity": "high",
                    "summary": f"Detected potential adversarial prompt injection payload embedded inside log stream",
                    "evidence_refs": [{
                        "line_no": entry["line_no"],
                        "raw_hash": entry["raw_hash"],
                        "log_excerpt": entry["content"][:200]
                    }],
                    "suspected_cause": "Adversary attempting to manipulate downstream LLM analyzer by injecting instructions into log text",
                    "recommended_actions": [
                        "Treat log message strictly as untrusted data",
                        "Quarantine external input channel generating this log entry",
                        "Ensure LLM analyzer does not possess OS execution permissions"
                    ],
                    "needs_human_review": True
                })
                break

    return findings


def deduplicate_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and aggregate events based on type and fingerprint."""
    seen: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        eid = ev["event_id"]
        if eid not in seen:
            seen[eid] = ev
        else:
            # Aggregate evidence refs without duplicates
            existing_lines = {ref["line_no"] for ref in seen[eid]["evidence_refs"]}
            for ref in ev["evidence_refs"]:
                if ref["line_no"] not in existing_lines:
                    seen[eid]["evidence_refs"].append(ref)
                    existing_lines.add(ref["line_no"])
    return list(seen.values())


def chunk_log_entries(entries: List[Dict[str, Any]], max_lines: int = 100, max_chars: int = 8000) -> List[List[Dict[str, Any]]]:
    """Split preprocessed log entries into bounded chunks to respect LLM context limits."""
    chunks: List[List[Dict[str, Any]]] = []
    current_chunk: List[Dict[str, Any]] = []
    current_chars = 0
    
    for entry in entries:
        line_len = len(entry["content"])
        if len(current_chunk) >= max_lines or (current_chars + line_len > max_chars and current_chunk):
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0
        current_chunk.append(entry)
        current_chars += line_len
        
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def validate_evidence(event: Dict[str, Any], entries_by_line: Dict[int, Dict[str, Any]]) -> bool:
    """Strictly verify that every evidence reference in the event maps to real preprocessed log entries.
    
    Rejects hallucinated or invented evidence citations.
    """
    refs = event.get("evidence_refs", [])
    if not refs:
        raise EvidenceValidationError(f"Event {event.get('event_id')} has empty evidence_refs")

    for ref in refs:
        line_no = ref.get("line_no")
        raw_hash = ref.get("raw_hash")
        log_excerpt = ref.get("log_excerpt", "")
        
        if line_no not in entries_by_line:
            raise EvidenceValidationError(
                f"Evidence citation failure: line {line_no} does not exist in input log chunk"
            )
        
        real_entry = entries_by_line[line_no]
        if real_entry["raw_hash"] != raw_hash:
            raise EvidenceValidationError(
                f"Evidence hash mismatch at line {line_no}: cited {raw_hash}, expected {real_entry['raw_hash']}"
            )
        
        # Verify excerpt is a substring of the preprocessed line
        if log_excerpt and log_excerpt not in real_entry["content"]:
            raise EvidenceValidationError(
                f"Evidence excerpt at line {line_no} not found in actual preprocessed line content"
            )
            
    return True


def validate_schema(event: Dict[str, Any]) -> None:
    """Validate event against required schema properties, enums, and lengths."""
    required = [
        "event_id", "source", "timestamp", "event_type", "severity",
        "summary", "evidence_refs", "suspected_cause", "recommended_actions",
        "needs_human_review"
    ]
    for req in required:
        if req not in event:
            raise ValueError(f"Schema violation: missing required property '{req}'")

    valid_sources = {"syslog", "docker", "sshd", "n8n", "ufw", "auth", "synthetic_test"}
    if event["source"] not in valid_sources:
        raise ValueError(f"Schema violation: invalid source '{event['source']}'")

    valid_types = {
        "auth_bruteforce", "sudo_failure", "privilege_escalation_attempt",
        "unauthorized_access", "container_anomaly", "prompt_injection_attempt",
        "network_scan", "generic_anomaly"
    }
    if event["event_type"] not in valid_types:
        raise ValueError(f"Schema violation: invalid event_type '{event['event_type']}'")

    valid_severities = {"info", "low", "medium", "high", "critical"}
    if event["severity"] not in valid_severities:
        raise ValueError(f"Schema violation: invalid severity '{event['severity']}'")

    if not (10 <= len(event["summary"]) <= 300):
        raise ValueError(f"Schema violation: summary length {len(event['summary'])} out of bounds (10-300)")

    if not isinstance(event["needs_human_review"], bool):
        raise ValueError("Schema violation: needs_human_review must be boolean")

    if not isinstance(event["recommended_actions"], list) or len(event["recommended_actions"]) == 0:
        raise ValueError("Schema violation: recommended_actions must be non-empty array")


def process_pipeline(
    raw_log_lines: List[str],
    source: str = "syslog",
    llm_invoker: Optional[Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]] = None
) -> Dict[str, Any]:
    """Execute complete processing pipeline:
    1. Parse & Preprocess (UTC norm, Redaction, Hashes)
    2. Deterministic Rule Detection (SSH, Sudo, Injection)
    3. Deduplication
    4. Optional LLM invocation with graceful degradation if offline
    5. Strict Evidence & Schema Validation
    6. Aggregation
    """
    entries = parse_and_preprocess_logs(raw_log_lines, source=source)
    entries_by_line = {e["line_no"]: e for e in entries}

    # Deterministic findings (guaranteed baseline)
    deterministic_findings = detect_deterministic_rules(entries)
    for f in deterministic_findings:
        validate_schema(f)
        validate_evidence(f, entries_by_line)

    llm_status = "NOT_REQUESTED"
    llm_findings: List[Dict[str, Any]] = []

    if llm_invoker is not None:
        try:
            chunks = chunk_log_entries(entries)
            for chunk in chunks:
                raw_llm_results = llm_invoker(chunk)
                for res in raw_llm_results:
                    try:
                        validate_schema(res)
                        validate_evidence(res, entries_by_line)
                        llm_findings.append(res)
                    except (ValueError, EvidenceValidationError) as err:
                        # Log and reject hallucinated/invalid model finding
                        print(f"[WARN] Rejected invalid LLM finding: {err}")
            llm_status = "SUCCESS"
        except Exception as e:
            # Graceful degradation: Windows Ollama offline / timeout
            llm_status = f"DEFERRED_LLM ({type(e).__name__})"

    all_findings = deduplicate_events(deterministic_findings + llm_findings)

    return {
        "status": "COMPLETED",
        "llm_status": llm_status,
        "source": source,
        "total_lines_processed": len(entries),
        "total_findings": len(all_findings),
        "findings": all_findings,
        "processed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }


def render_markdown_report(result: Dict[str, Any]) -> str:
    """Format pipeline results into clean, human-readable Markdown for ops review."""
    lines = [
        "# Security Log Analysis Report",
        "",
        f"- **Processed At (UTC):** {result.get('processed_at_utc', 'N/A')}",
        f"- **Source:** `{result.get('source', 'syslog')}`",
        f"- **Total Lines Ingested:** {result.get('total_lines_processed', 0)}",
        f"- **Findings Count:** {result.get('total_findings', 0)}",
        f"- **LLM Stage Status:** `{result.get('llm_status', 'N/A')}`",
        "",
        "## Detected Security Events",
        ""
    ]
    
    findings = result.get("findings", [])
    if not findings:
        lines.append("No security anomalies or rule violations detected.")
        lines.append("")
        return "\n".join(lines)

    for idx, f in enumerate(findings, start=1):
        sev_badge = {
            "critical": "[CRITICAL]",
            "high": "[HIGH]",
            "medium": "[MEDIUM]",
            "low": "[LOW]",
            "info": "[INFO]"
        }.get(f.get("severity", "info"), "[UNKNOWN]")

        lines.extend([
            f"### {idx}. {sev_badge} {f.get('summary', 'Security Finding')}",
            f"- **Event ID:** `{f.get('event_id')}`",
            f"- **Event Type:** `{f.get('event_type')}`",
            f"- **Timestamp (UTC):** `{f.get('timestamp')}`",
            f"- **Needs Human Review:** `{f.get('needs_human_review', True)}`",
            f"- **Suspected Cause:** {f.get('suspected_cause')}",
            "",
            "#### Evidence References",
            "| Line | SHA-256 (8) | Redacted Log Excerpt |",
            "|---|---|---|"
        ])
        for ref in f.get("evidence_refs", []):
            lines.append(f"| {ref.get('line_no')} | `{ref.get('raw_hash')}` | `{ref.get('log_excerpt')}` |")
        lines.append("")
        lines.append("#### Recommended Actions (No Automatic Execution)")
        for act in f.get("recommended_actions", []):
            lines.append(f"- {act}")
        lines.append("")

    return "\n".join(lines)
