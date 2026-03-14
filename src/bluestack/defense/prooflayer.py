"""Simplified ProofLayer detection engine for MCP tool call scanning.

Adapted from prooflayer-runtime's DetectionEngine. Uses inline detection rules
covering 8 threat categories (prompt injection, jailbreaks, command injection,
data exfiltration, role manipulation, tool poisoning, SSRF/XXE, SQL injection).

This is a self-contained version that avoids the full prooflayer dependency tree.
"""

import re
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_REGEX_TIMEOUT = 0.1  # 100ms per pattern
_CIRCUIT_BREAKER_THRESHOLD = 3


@dataclass
class DetectionRule:
    id: str
    severity: str
    message: str
    pattern: str
    score: int
    category: str
    compiled_pattern: re.Pattern | None = None

    def __post_init__(self):
        try:
            self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE | re.DOTALL)
        except re.error as e:
            logger.warning("Failed to compile pattern for rule %s: %s", self.id, e)
            self.compiled_pattern = None


@dataclass
class ScanResult:
    score: int
    level: str  # SAFE, SUSPICIOUS, THREAT
    action: str  # ALLOW, WARN, BLOCK
    matched_rules: list = field(default_factory=list)
    tool_name: str = ""
    latency_ms: float = 0.0

    @property
    def is_blocked(self) -> bool:
        return self.action in ("BLOCK", "KILL")


# Shell metacharacters for additional scoring
_DANGEROUS_CHARS = [";", "|", "&&", "||", "`", "$", ">", "<"]


def _get_inline_rules() -> list[DetectionRule]:
    """71 inline detection rules across 8 categories."""
    return [
        # Direct Injection (12 rules)
        DetectionRule("direct-ignore-previous", "critical", "Direct injection: 'ignore previous instructions'",
                      r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?|commands?)", 30, "direct_injection"),
        DetectionRule("direct-disregard-system", "critical", "Direct injection: 'disregard system prompt'",
                      r"(disregard|forget|override)\s+(system|original)\s+(prompt|instructions?)", 30, "direct_injection"),
        DetectionRule("direct-new-instructions", "high", "Direct injection: 'new instructions'",
                      r"(new|updated|revised)\s+instructions?", 20, "direct_injection"),
        DetectionRule("direct-you-are-actually", "high", "Direct injection: 'you are actually'",
                      r"you\s+are\s+actually\s+(a|an|not)", 25, "direct_injection"),
        DetectionRule("direct-system-prompt-is", "critical", "Direct injection: 'your system prompt is'",
                      r"your\s+(system\s+)?prompt\s+is", 20, "direct_injection"),
        DetectionRule("direct-reveal-instructions", "high", "Direct injection: reveal instructions",
                      r"(reveal|show|display|output|print)\s+(your\s+)?(system\s+)?(prompt|instructions)", 25, "direct_injection"),
        DetectionRule("direct-begin-with", "high", "Direct injection: 'begin your response with'",
                      r"begin\s+(your\s+)?response\s+with", 20, "direct_injection"),
        DetectionRule("direct-important-override", "high", "Direct injection: IMPORTANT override",
                      r"IMPORTANT:\s*(ignore|disregard|override|forget)", 30, "direct_injection"),
        DetectionRule("direct-system-message", "critical", "Direct injection: fake system message",
                      r"\[?(system|admin)\s*(message|notice|alert)\]?:", 25, "direct_injection"),
        DetectionRule("direct-roleplay", "high", "Direct injection: roleplay prompt",
                      r"(let'?s|we'?re)\s+(play|do)\s+(a\s+)?(roleplay|game|exercise)", 15, "direct_injection"),
        DetectionRule("direct-hypothetical", "medium", "Direct injection: hypothetical scenario",
                      r"(hypothetically|in\s+theory|imagine\s+if)\s+.{5,}(system|prompt|instructions)", 15, "direct_injection"),
        DetectionRule("direct-repeat-after-me", "high", "Direct injection: repeat after me",
                      r"repeat\s+(after\s+me|the\s+following|back)", 20, "direct_injection"),

        # Jailbreaks (8 rules)
        DetectionRule("jailbreak-dan-mode", "critical", "Jailbreak: DAN mode", r"\b(DAN|do anything now)\b", 30, "jailbreak"),
        DetectionRule("jailbreak-developer-mode", "critical", "Jailbreak: developer mode",
                      r"(enable|activate|enter)\s+(developer|dev|debug)\s+mode", 30, "jailbreak"),
        DetectionRule("jailbreak-act-as", "high", "Jailbreak: 'act as' role manipulation",
                      r"(act|pretend|behave)\s+as\s+(if|though|a)", 20, "jailbreak"),
        DetectionRule("jailbreak-no-restrictions", "critical", "Jailbreak: no restrictions",
                      r"(without|no|remove)\s+(any\s+)?(restrictions?|limitations?|filters?|safeguards?)", 25, "jailbreak"),
        DetectionRule("jailbreak-uncensored", "critical", "Jailbreak: uncensored mode",
                      r"(uncensored|unfiltered|unrestricted)\s+(mode|version|response)", 25, "jailbreak"),
        DetectionRule("jailbreak-evil-mode", "critical", "Jailbreak: evil/chaos mode",
                      r"(evil|chaos|villain|dark)\s+(mode|personality)", 25, "jailbreak"),
        DetectionRule("jailbreak-bypass-safety", "critical", "Jailbreak: bypass safety",
                      r"bypass\s+(safety|content|ethical)\s+(filter|check|guard)", 30, "jailbreak"),
        DetectionRule("jailbreak-opposite-day", "medium", "Jailbreak: opposite day",
                      r"(opposite|backwards?)\s+day", 15, "jailbreak"),

        # Command Injection (15 rules)
        DetectionRule("cmd-inject-semicolon", "critical", "Command injection: ';'", r";[\s]*[a-zA-Z/.$]", 20, "command_injection"),
        DetectionRule("cmd-inject-pipe", "critical", "Command injection: '|'", r"\|[\s]*[a-zA-Z/.$]", 20, "command_injection"),
        DetectionRule("cmd-inject-ampersand", "critical", "Command injection: '&&'", r"&&[\s]*[a-zA-Z/.$]", 15, "command_injection"),
        DetectionRule("cmd-inject-curl", "critical", "Command injection: curl", r"\bcurl\s+", 25, "command_injection"),
        DetectionRule("cmd-inject-wget", "critical", "Command injection: wget", r"\bwget\s+", 25, "command_injection"),
        DetectionRule("cmd-inject-bash", "critical", "Command injection: bash -c", r"\b(bash|sh|zsh)\s+-c", 30, "command_injection"),
        DetectionRule("cmd-inject-nc", "critical", "Command injection: netcat", r"\b(nc|netcat)\s+", 30, "command_injection"),
        DetectionRule("cmd-inject-rm", "critical", "Command injection: rm", r"\brm\s+(-[rRf]+\s+)?/", 30, "command_injection"),
        DetectionRule("cmd-inject-cat-etc", "critical", "Command injection: cat /etc/", r"\bcat\s+/etc/", 25, "command_injection"),
        DetectionRule("cmd-inject-python", "high", "Command injection: python -c", r"\bpython[3]?\s+-c", 25, "command_injection"),
        DetectionRule("cmd-inject-eval", "critical", "Command injection: eval()", r"\beval\s*\(", 20, "command_injection"),
        DetectionRule("cmd-inject-exec", "critical", "Command injection: exec()", r"\bexec\s*\(", 20, "command_injection"),
        DetectionRule("cmd-inject-import-os", "critical", "Command injection: import os", r"\bimport\s+os\b", 25, "command_injection"),
        DetectionRule("cmd-inject-subprocess", "critical", "Command injection: subprocess", r"\bsubprocess\.", 25, "command_injection"),
        DetectionRule("cmd-inject-backtick", "high", "Command injection: backtick execution", r"`[^`]+`", 15, "command_injection"),

        # Data Exfiltration (10 rules)
        DetectionRule("exfil-send-to-url", "critical", "Data exfiltration: send to URL",
                      r"(send|post|upload)\s+(to|at)\s+https?://", 25, "data_exfiltration"),
        DetectionRule("exfil-base64-encode", "high", "Data exfiltration: base64 encoding",
                      r"base64\s+(encode|--encode|-e)", 15, "data_exfiltration"),
        DetectionRule("exfil-file-read", "critical", "Data exfiltration: sensitive file access",
                      r"(/etc/(passwd|shadow)|\.ssh/|\.env|credentials)", 30, "data_exfiltration"),
        DetectionRule("exfil-email-data", "high", "Data exfiltration: email data out",
                      r"(email|send|forward)\s+.{0,30}(data|results?|output|contents?)\s+(to|at)", 20, "data_exfiltration"),
        DetectionRule("exfil-webhook", "critical", "Data exfiltration: webhook/callback URL",
                      r"(webhook|callback|ngrok|burp|requestbin)", 25, "data_exfiltration"),
        DetectionRule("exfil-dump-all", "high", "Data exfiltration: dump all records",
                      r"(dump|export|extract)\s+(all|every|entire)\s+(record|data|table|customer)", 20, "data_exfiltration"),
        DetectionRule("exfil-list-tables", "medium", "Data exfiltration: schema enumeration",
                      r"(list|show|describe)\s+(all\s+)?(tables?|schema|columns?|databases?)", 15, "data_exfiltration"),
        DetectionRule("exfil-select-star", "medium", "Data exfiltration: SELECT * FROM",
                      r"SELECT\s+\*\s+FROM", 10, "data_exfiltration"),
        DetectionRule("exfil-system-config", "high", "Data exfiltration: system config access",
                      r"system_config|internal_notes|admin_settings", 20, "data_exfiltration"),
        DetectionRule("exfil-canary-probe", "high", "Data exfiltration: canary token probing",
                      r"CANARY-|canary.?token|secret.?key|api.?key", 20, "data_exfiltration"),

        # Role Manipulation (8 rules)
        DetectionRule("role-you-are-now", "critical", "Role manipulation: 'you are now'",
                      r"you are now\s+(a |an |the )?(unrestricted|unfiltered|evil|malicious|hacked|compromised)", 20, "role_manipulation"),
        DetectionRule("role-pretend-to-be", "high", "Role manipulation: 'pretend to be'",
                      r"pretend\s+to\s+be\s+(a |an )?(hacker|admin|root|unrestricted|evil|malicious)", 20, "role_manipulation"),
        DetectionRule("role-act-as-root", "critical", "Role manipulation: 'act as root/admin'",
                      r"(act|behave|function)\s+as\s+(root|admin|superuser|sudo)", 25, "role_manipulation"),
        DetectionRule("role-become-unrestricted", "critical", "Role manipulation: 'become unrestricted'",
                      r"become\s+(an?\s+)?(unrestricted|unfiltered|uncensored|unlimited)", 30, "role_manipulation"),
        DetectionRule("role-switch-persona", "high", "Role manipulation: switch persona",
                      r"switch\s+(to|into)\s+(a\s+)?(different|new|evil|hacker)", 20, "role_manipulation"),
        DetectionRule("role-from-now-on", "high", "Role manipulation: from now on",
                      r"from\s+now\s+on,?\s+(you|your)\s+(are|will|must|should)", 20, "role_manipulation"),
        DetectionRule("role-true-purpose", "high", "Role manipulation: true purpose",
                      r"your\s+(true|real|actual)\s+(purpose|role|identity|function)", 20, "role_manipulation"),
        DetectionRule("role-real-name", "medium", "Role manipulation: what is your real name",
                      r"what\s+is\s+your\s+(real|true|actual)\s+(name|identity)", 10, "role_manipulation"),

        # Tool Poisoning (6 rules)
        DetectionRule("poison-when-called", "critical", "Tool poisoning: hidden execution in description",
                      r"when\s+(this\s+tool\s+is\s+)?called,?\s+(execute|run|perform)", 30, "tool_poisoning"),
        DetectionRule("poison-silently-run", "critical", "Tool poisoning: silent execution",
                      r"silently\s+(run|execute|perform|send|upload)", 30, "tool_poisoning"),
        DetectionRule("poison-hidden-tags", "critical", "Tool poisoning: hidden instruction tags",
                      r"<\s*(hidden|invisible|secret)\s*>", 25, "tool_poisoning"),
        DetectionRule("poison-pre-post-exec", "critical", "Tool poisoning: pre/post execution injection",
                      r"(before|after)\s+respond(ing)?,?\s+(first\s+)?(run|execute|call|send)", 30, "tool_poisoning"),
        DetectionRule("poison-tool-override", "critical", "Tool poisoning: tool description override",
                      r"(override|replace|modify)\s+(this\s+)?tool'?s?\s+(description|behavior)", 25, "tool_poisoning"),
        DetectionRule("poison-inject-output", "high", "Tool poisoning: inject into output",
                      r"(inject|insert|add)\s+.{0,20}(into|to)\s+(the\s+)?(output|response|result)", 20, "tool_poisoning"),

        # SSRF/XXE (6 rules)
        DetectionRule("ssrf-cloud-metadata", "critical", "SSRF: cloud metadata endpoint",
                      r"169\.254\.169\.254|metadata\.google|169\.254\.170\.2", 30, "ssrf_xxe"),
        DetectionRule("ssrf-internal-ip", "high", "SSRF: internal/private IP",
                      r"(https?://)(127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)", 25, "ssrf_xxe"),
        DetectionRule("ssrf-file-scheme", "high", "SSRF: file:// scheme", r"file://", 25, "ssrf_xxe"),
        DetectionRule("xxe-doctype", "critical", "XXE: DOCTYPE/ENTITY declaration",
                      r"<!\s*(DOCTYPE|ENTITY)", 30, "ssrf_xxe"),
        DetectionRule("xxe-system-entity", "critical", "XXE: SYSTEM entity reference",
                      r"SYSTEM\s+['\"]", 30, "ssrf_xxe"),
        DetectionRule("ssrf-gopher", "high", "SSRF: gopher:// scheme", r"gopher://", 25, "ssrf_xxe"),

        # SQL Injection (6 rules)
        DetectionRule("sql-union-select", "critical", "SQL injection: UNION SELECT",
                      r"\bunion\s+(all\s+)?select\b", 25, "sql_injection"),
        DetectionRule("sql-drop-table", "critical", "SQL injection: DROP TABLE",
                      r"\bdrop\s+(table|database)\b", 30, "sql_injection"),
        DetectionRule("sql-or-tautology", "high", "SQL injection: OR tautology",
                      r"'\s*(or|and)\s+['\d]+\s*=\s*['\d]", 20, "sql_injection"),
        DetectionRule("sql-comment-bypass", "medium", "SQL injection: comment bypass",
                      r"--\s*$|/\*.*\*/", 15, "sql_injection"),
        DetectionRule("sql-sleep-benchmark", "critical", "SQL injection: time-based injection",
                      r"\b(sleep|benchmark|waitfor)\s*\(", 25, "sql_injection"),
        DetectionRule("sql-info-schema", "high", "SQL injection: information_schema access",
                      r"information_schema\.|sys\.", 20, "sql_injection"),
    ]


class ProofLayerScanner:
    """Simplified detection engine adapted from prooflayer-runtime.

    Scans MCP tool call arguments for threats using 71 regex-based detection rules.
    Used at defense level 3+ to gate tool execution.
    """

    def __init__(self):
        self.rules = _get_inline_rules()
        self._lock = threading.Lock()
        self._consecutive_timeouts = 0
        logger.info("ProofLayer scanner initialized with %d rules", len(self.rules))

    def scan(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ScanResult:
        """Scan a tool call for threats. Returns ScanResult."""
        start = time.perf_counter()
        arguments = arguments or {}

        # Build searchable text from tool name + all argument values
        parts = [tool_name.lower()]
        for key, val in arguments.items():
            parts.append(f"{key}={self._flatten(val).lower()}")
        search_text = " ".join(parts)

        matched = []
        pattern_score = 0

        for rule in self.rules:
            if not rule.compiled_pattern:
                continue
            try:
                hit = self._match_with_timeout(rule, search_text)
            except TimeoutError:
                with self._lock:
                    self._consecutive_timeouts += 1
                    if self._consecutive_timeouts >= _CIRCUIT_BREAKER_THRESHOLD:
                        return ScanResult(
                            score=100, level="THREAT", action="BLOCK",
                            matched_rules=[{"id": "circuit-breaker", "message": "ReDoS circuit breaker tripped"}],
                            tool_name=tool_name,
                            latency_ms=(time.perf_counter() - start) * 1000,
                        )
                continue

            with self._lock:
                self._consecutive_timeouts = 0

            if hit:
                matched.append({"id": rule.id, "message": rule.message, "category": rule.category, "score": rule.score})
                pattern_score += rule.score

        # Metacharacter scoring
        metachar_score = sum(10 for c in _DANGEROUS_CHARS if c in search_text)
        total = min(pattern_score + metachar_score, 100)

        if total <= 29:
            level, action = "SAFE", "ALLOW"
        elif total <= 69:
            level, action = "SUSPICIOUS", "WARN"
        else:
            level, action = "THREAT", "BLOCK"

        return ScanResult(
            score=total, level=level, action=action, matched_rules=matched,
            tool_name=tool_name,
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def _match_with_timeout(self, rule: DetectionRule, text: str) -> bool:
        """Match a single rule with ReDoS timeout protection."""
        result = [None]

        def _search():
            result[0] = rule.compiled_pattern.search(text) is not None

        t = threading.Thread(target=_search, daemon=True)
        t.start()
        t.join(timeout=_REGEX_TIMEOUT)

        if t.is_alive():
            raise TimeoutError(f"Regex timeout for rule {rule.id}")

        return bool(result[0])

    def _flatten(self, val: Any) -> str:
        """Flatten a value to a string for scanning."""
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return " ".join(self._flatten(v) for v in val.values())
        if isinstance(val, (list, tuple)):
            return " ".join(self._flatten(v) for v in val)
        return str(val) if val is not None else ""
