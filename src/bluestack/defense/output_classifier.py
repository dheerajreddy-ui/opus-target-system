"""Output classifier — scans agent responses for PII, canaries, prompt fragments.

Level 3: logs warnings to audit trail.
Level 4: redacts PII or blocks response entirely.
"""

import re
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# PII patterns for redaction
_PII_PATTERNS = {
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
    "credit_card": (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CC REDACTED]"),
    "email_addr": (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), None),  # log only, don't redact
}

# Internal path patterns
_INTERNAL_PATTERNS = [
    re.compile(r"/etc/(passwd|shadow|hosts)"),
    re.compile(r"\.env\b"),
    re.compile(r"credentials?\.(json|yaml|yml|env)"),
    re.compile(r"/internal/|/system/|system_config"),
]

_CANARY_PATTERN = re.compile(r"CANARY-[A-Z]+-[A-Z0-9]+")


class OutputClassifier:
    def __init__(self, project_root: Path, defense_manager=None):
        self.defense_manager = defense_manager
        self._prompt_fragments: list[str] = []

        # Load prompt fragments for system prompt detection
        agents_yaml = project_root / "config" / "agents.yaml"
        if agents_yaml.exists():
            with open(agents_yaml) as f:
                cfg = yaml.safe_load(f) or {}
            for agent_cfg in cfg.values():
                prompt = agent_cfg.get("system_prompt", "")
                for sentence in re.split(r"[.\n]", prompt):
                    s = sentence.strip()
                    if len(s) > 30:
                        self._prompt_fragments.append(s)

    def classify(self, text: str) -> dict:
        """Classify an agent response for policy violations.

        Returns:
            dict with keys: has_pii, has_canary, has_prompt_leak, has_internal_paths,
                           findings (list of dicts), redacted_text (if level 4)
        """
        findings = []

        # Check PII
        for pii_type, (pattern, _) in _PII_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({"type": "pii", "subtype": pii_type, "value": match.group()})

        # Check canary tokens
        for match in _CANARY_PATTERN.finditer(text):
            findings.append({"type": "canary", "value": match.group()})

        # Check internal paths
        for pattern in _INTERNAL_PATTERNS:
            for match in pattern.finditer(text):
                findings.append({"type": "internal_path", "value": match.group()})

        # Check system prompt fragments
        prompt_hits = sum(1 for f in self._prompt_fragments if f in text)
        has_prompt_leak = prompt_hits >= 2

        if has_prompt_leak:
            findings.append({"type": "prompt_leak", "fragments_matched": prompt_hits})

        result = {
            "has_pii": any(f["type"] == "pii" for f in findings),
            "has_canary": any(f["type"] == "canary" for f in findings),
            "has_prompt_leak": has_prompt_leak,
            "has_internal_paths": any(f["type"] == "internal_path" for f in findings),
            "findings": findings,
        }

        # Level 4: produce redacted text
        if self.defense_manager and self.defense_manager.level >= 4:
            redacted = text
            for pii_type, (pattern, replacement) in _PII_PATTERNS.items():
                if replacement:
                    redacted = pattern.sub(replacement, redacted)
            # Redact canary tokens
            redacted = _CANARY_PATTERN.sub("[REDACTED]", redacted)
            result["redacted_text"] = redacted

        return result

    def should_block(self, classification: dict) -> bool:
        """At level 4, block if canaries or prompt leaks detected."""
        if not self.defense_manager:
            return False
        if self.defense_manager.level >= 4:
            return classification["has_canary"] or classification["has_prompt_leak"]
        return False
