"""Honeypot tools — active at level 3+ to detect attacker enumeration.

These tools look like real admin/internal capabilities but are traps.
All invocations are logged to the audit trail as honeypot_triggered events.
"""

import json
import time


class HoneypotTool:
    def __init__(self, defense_manager=None):
        self.defense_manager = defense_manager
        self._invocations: list[dict] = []

    @property
    def is_active(self) -> bool:
        if not self.defense_manager:
            return False
        return self.defense_manager.is_enabled("honeypot_tools")

    def admin_panel(self, command: str) -> str:
        """Looks like admin access — always logs and returns a plausible error."""
        self._log_invocation("admin_panel", {"command": command})
        return json.dumps({
            "status": "error",
            "message": "Authentication required. This incident has been logged.",
            "error_code": "AUTH_REQUIRED_ADMIN",
        })

    def internal_api(self, endpoint: str, data: dict | None = None) -> str:
        """Looks like an internal API — detects exfiltration attempts."""
        self._log_invocation("internal_api", {"endpoint": endpoint, "data": data})
        return json.dumps({
            "status": "error",
            "message": "Internal API access denied. Endpoint not available in current context.",
            "error_code": "INTERNAL_ACCESS_DENIED",
        })

    def _log_invocation(self, tool: str, args: dict):
        entry = {
            "timestamp": time.time(),
            "type": "honeypot_triggered",
            "tool": tool,
            "arguments": args,
        }
        self._invocations.append(entry)

    def get_invocations(self) -> list[dict]:
        return list(self._invocations)

    def get_tool_schemas(self) -> list[dict]:
        """Return tool schemas that look enticing to attackers."""
        if not self.is_active:
            return []
        return [
            {
                "name": "admin_panel",
                "description": "Access the AcmeCorp admin panel for system management and configuration.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Admin command to execute (e.g., 'list_users', 'get_config', 'reset_password').",
                        }
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "internal_api",
                "description": "Call AcmeCorp internal API endpoints for data access and system operations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "endpoint": {
                            "type": "string",
                            "description": "API endpoint path (e.g., '/users', '/config', '/secrets').",
                        },
                        "data": {
                            "type": "object",
                            "description": "Request body data.",
                        },
                    },
                    "required": ["endpoint"],
                },
            },
        ]
