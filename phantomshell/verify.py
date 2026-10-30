"""Deterministic evidence and verbatim quote verification."""

from __future__ import annotations

import re
from typing import Any


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def verify_conclusion(result: dict[str, Any], evidence: dict[str, str]) -> dict[str, Any]:
    """Remove missing or forged citations and downgrade unsupported conclusions."""
    verified: list[dict[str, str]] = []
    unverified: list[dict[str, str]] = []
    for item in result.get("supporting", []):
        content = evidence.get(item.get("evidence_id", ""))
        if content is not None and item.get("quote") and _norm(item["quote"]) in _norm(content):
            verified.append(item)
        else:
            unverified.append(item)
    verdict = result.get("verdict", "inconclusive")
    if verdict == "supported" and not verified:
        verdict = "inconclusive"
    cause = result.get("cause", "")
    narrative = result.get("narrative", "")
    if verdict == "inconclusive":
        cause = "Insufficient verified evidence to support a cause."
        narrative = ""
    if any(re.search(r"(?:[A-Za-z]:)?[/\\][\w./\\-]+|\b\d+\b|\b[0-9a-f]{7,40}\b", narrative, re.IGNORECASE) and
           match.group(0) not in " ".join(evidence.values()) for match in re.finditer(r"(?:[A-Za-z]:)?[/\\][\w./\\-]+|\b\d+\b|\b[0-9a-f]{7,40}\b", narrative, re.IGNORECASE)):
        narrative = ""
    return {**result, "verdict": verdict, "cause": cause, "supporting": verified, "unverified": unverified, "narrative": narrative}
