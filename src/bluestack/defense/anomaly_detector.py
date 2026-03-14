"""Behavioral anomaly detector — tracks per-session tool call patterns.

Flags suspicious behaviors:
- Honeypot tool access
- Sudden topic pivots (e.g., order queries -> system config queries)
- Rapid tool enumeration
- Unusual tool call frequency
"""

import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Tools that are suspicious to call
_SENSITIVE_TOOLS = {"admin_panel", "internal_api", "query_database"}
_HONEYPOT_TOOLS = {"admin_panel", "internal_api"}

# Patterns that indicate topic pivot in query args
_RECON_KEYWORDS = {"system_config", "internal_notes", "information_schema", "sqlite_master",
                   "CANARY", "api_key", "password", "secret", "credential"}


class AnomalyDetector:
    def __init__(self, defense_manager=None):
        self.defense_manager = defense_manager
        self._sessions: dict[str, list[dict]] = defaultdict(list)

    def record_tool_call(self, session_id: str, agent: str, tool: str, args: dict):
        """Record a tool call for anomaly analysis."""
        self._sessions[session_id].append({
            "timestamp": time.time(),
            "agent": agent,
            "tool": tool,
            "args_preview": str(args)[:500],
        })

    def check_anomalies(self, session_id: str) -> list[dict]:
        """Check for anomalies in the session's tool call history."""
        calls = self._sessions.get(session_id, [])
        if not calls:
            return []

        anomalies = []

        # 1. Honeypot tool access
        for call in calls:
            if call["tool"] in _HONEYPOT_TOOLS:
                anomalies.append({
                    "type": "honeypot_access",
                    "severity": "critical",
                    "tool": call["tool"],
                    "message": f"Honeypot tool '{call['tool']}' was invoked",
                })

        # 2. Rapid tool enumeration (5+ distinct tools in 60 seconds)
        if len(calls) >= 5:
            window = [c for c in calls if time.time() - c["timestamp"] < 60]
            distinct_tools = {c["tool"] for c in window}
            if len(distinct_tools) >= 5:
                anomalies.append({
                    "type": "tool_enumeration",
                    "severity": "high",
                    "tools": list(distinct_tools),
                    "message": f"Rapid tool enumeration detected: {len(distinct_tools)} distinct tools in 60s",
                })

        # 3. Topic pivot detection
        for call in calls:
            args_str = call.get("args_preview", "").lower()
            hits = [kw for kw in _RECON_KEYWORDS if kw.lower() in args_str]
            if hits:
                anomalies.append({
                    "type": "recon_keywords",
                    "severity": "high",
                    "keywords": hits,
                    "tool": call["tool"],
                    "message": f"Reconnaissance keywords detected in {call['tool']}: {hits}",
                })

        # 4. High frequency (10+ calls in 30 seconds)
        recent = [c for c in calls if time.time() - c["timestamp"] < 30]
        if len(recent) >= 10:
            anomalies.append({
                "type": "high_frequency",
                "severity": "medium",
                "count": len(recent),
                "message": f"High tool call frequency: {len(recent)} calls in 30s",
            })

        return anomalies

    def should_block(self, session_id: str) -> tuple[bool, str]:
        """At level 4, block if critical anomalies detected."""
        if not self.defense_manager:
            return False, ""
        anomalies = self.check_anomalies(session_id)
        if self.defense_manager.level >= 4:
            critical = [a for a in anomalies if a["severity"] == "critical"]
            if critical:
                return True, critical[0]["message"]
        return False, ""

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)
