"""
Maps attack types to MITRE ATLAS (Adversarial Threat Landscape for
Artificial-Intelligence Systems) technique identifiers.

Reference: https://atlas.mitre.org/techniques
"""

from typing import Optional

# -----------------------------------------------------------------------
# Core mapping: normalised attack type -> ATLAS technique ID
# -----------------------------------------------------------------------

ATLAS_MAPPING: dict[str, str] = {
    "prompt_injection": "AML.T0051",
    "indirect_prompt_injection": "AML.T0051.001",
    "jailbreak": "AML.T0054",
    "data_exfiltration": "AML.T0024",
    "model_extraction": "AML.T0044",
    "training_data_extraction": "AML.T0037",
    "evasion": "AML.T0015",
    "sql_injection": "AML.T0051",       # via prompt injection vector
    "path_traversal": "AML.T0051",      # via prompt injection vector
    "social_engineering": "AML.T0052",
    "system_prompt_extraction": "AML.T0051.002",
    "model_inversion": "AML.T0024",
    "membership_inference": "AML.T0025",
    "poisoning": "AML.T0020",
    "supply_chain": "AML.T0010",
}

# Human-readable descriptions for reporting
ATLAS_DESCRIPTIONS: dict[str, str] = {
    "AML.T0051": "LLM Prompt Injection",
    "AML.T0051.001": "LLM Prompt Injection: Indirect",
    "AML.T0051.002": "LLM Prompt Injection: System Prompt Extraction",
    "AML.T0054": "LLM Jailbreak",
    "AML.T0024": "Exfiltration via ML Inference API",
    "AML.T0044": "Full ML Model Access / Extraction",
    "AML.T0037": "Data from Information Repositories",
    "AML.T0015": "Evade ML Model",
    "AML.T0052": "Phishing / Social Engineering",
    "AML.T0025": "Membership Inference",
    "AML.T0020": "Poison Training Data",
    "AML.T0010": "ML Supply Chain Compromise",
    "AML.T0000": "Unknown / Unmapped Technique",
}


def map_attack_to_atlas(
    attack_type: str, details: Optional[dict] = None
) -> list[str]:
    """
    Map an attack type string to one or more MITRE ATLAS technique IDs.

    Args:
        attack_type: Free-text attack type (e.g. "prompt-injection",
                     "Jailbreak", "data exfiltration").
        details: Optional dict with boolean flags that may trigger
                 additional technique mappings.

    Returns:
        De-duplicated list of ATLAS technique IDs.  Falls back to
        ``["AML.T0000"]`` if no mapping is found.
    """
    techniques: list[str] = []

    # Normalise the attack type string
    normalised = attack_type.lower().replace("-", "_").replace(" ", "_")

    if normalised in ATLAS_MAPPING:
        techniques.append(ATLAS_MAPPING[normalised])

    # Check for compound / contextual attacks via details dict
    if details:
        if details.get("uses_indirect_injection"):
            techniques.append("AML.T0051.001")
        if details.get("targets_training_data"):
            techniques.append("AML.T0037")
        if details.get("attempts_model_extraction"):
            techniques.append("AML.T0044")
        if details.get("social_engineering_component"):
            techniques.append("AML.T0052")

    return list(set(techniques)) or ["AML.T0000"]


def describe_technique(technique_id: str) -> str:
    """Return a human-readable description for an ATLAS technique ID."""
    return ATLAS_DESCRIPTIONS.get(technique_id, f"Unknown technique ({technique_id})")


def get_all_mapped_techniques() -> dict[str, str]:
    """Return the full mapping of attack types to ATLAS IDs."""
    return dict(ATLAS_MAPPING)
