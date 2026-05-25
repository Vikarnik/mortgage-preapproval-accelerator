"""
KYC / AML Screening Connector
================================

Simulates integration with sanctions screening and identity verification
services used for Bank Secrecy Act (BSA) / Anti-Money Laundering (AML)
compliance in mortgage origination.

In production this would connect to:
  - OFAC SDN (Specially Designated Nationals) list screening
  - FinCEN advisories and 314(a) requests
  - PEP (Politically Exposed Persons) databases
  - CIP (Customer Identification Program) verification services
  - Third-party providers like LexisNexis, Dow Jones, World-Check

Mock scenarios:
  - Clear:          No matches on any watchlist
  - Potential match: Fuzzy name match requiring manual review
  - Confirmed hit:  Exact match on SDN list (demo only)

Also includes CIP identity verification via document cross-referencing.
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIMULATED_LATENCY_S = 0.2
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

# ---------------------------------------------------------------------------
# Mock OFAC SDN entries (fictional — for demo only)
# ---------------------------------------------------------------------------
_MOCK_SDN_LIST: list[dict[str, Any]] = [
    {
        "entry_id": "SDN-88421",
        "name": "Elena Maria RODRIGUEZ VEGA",
        "aliases": ["Elena Rodriguez", "E.M. Rodriguez Vega"],
        "date_of_birth": "1984-05-12",
        "nationality": "Venezuela",
        "program": "SDNTK",
        "list_type": "SDN",
        "remarks": "DOB approx.; alt DOB 12 May 1985",
    },
    {
        "entry_id": "SDN-91034",
        "name": "Marcus Andre JOHNSON",
        "aliases": [],
        "date_of_birth": "1978-03-09",
        "nationality": "Nigeria",
        "program": "SDGT",
        "list_type": "SDN",
        "remarks": "Linked to designated entity XYZ Corp.",
    },
]

_PEP_DATABASE: list[dict[str, Any]] = [
    {
        "name": "Sarah Chen Wei",
        "country": "Singapore",
        "position": "Deputy Minister of Finance",
        "level": "National",
        "status": "Current",
    },
]


def _maybe_fail(operation: str) -> None:
    if random.random() < ERROR_RATE:
        logger.error("kyc_aml_screening.%s — simulated service failure", operation)
        raise ConnectionError(
            f"Screening service unavailable (simulated). Operation: {operation}"
        )


def _fuzzy_match_score(name1: str, name2: str) -> float:
    """Simplistic fuzzy name matching for demo purposes."""
    n1 = set(name1.lower().split())
    n2 = set(name2.lower().split())
    if not n1 or not n2:
        return 0.0
    intersection = n1 & n2
    union = n1 | n2
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def screen_individual(
    full_name: str,
    dob: str,
    ssn: str,
    citizenship: str = "US",
    *,
    screening_type: str = "mortgage_origination",
) -> dict[str, Any]:
    """Screen an individual against OFAC SDN list and other sanctions lists.

    Args:
        full_name: Full legal name of the applicant.
        dob: Date of birth ``YYYY-MM-DD``.
        ssn: SSN (used for logging reference only — not transmitted to OFAC).
        citizenship: Country of citizenship (ISO 2-letter code).
        screening_type: Context for the screening request.

    Returns:
        Screening result dict with disposition, matched entries (if any),
        match scores, and recommended actions.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("screen_individual")

    logger.info(
        "kyc_aml_screening.screen_individual | name=%s dob=%s citizenship=%s",
        full_name,
        dob,
        citizenship,
    )

    matches: list[dict[str, Any]] = []
    for entry in _MOCK_SDN_LIST:
        # Check primary name and aliases
        names_to_check = [entry["name"]] + entry.get("aliases", [])
        best_score = max(_fuzzy_match_score(full_name, n) for n in names_to_check)

        if best_score >= 0.3:
            match_type = "exact" if best_score >= 0.85 else "fuzzy"
            matches.append({
                "entry_id": entry["entry_id"],
                "matched_name": entry["name"],
                "match_score": round(best_score, 3),
                "match_type": match_type,
                "list_type": entry["list_type"],
                "program": entry["program"],
                "sdn_dob": entry["date_of_birth"],
                "applicant_dob": dob,
                "dob_match": entry["date_of_birth"] == dob,
                "nationality": entry["nationality"],
                "remarks": entry["remarks"],
            })

    # Determine disposition
    if not matches:
        disposition = "CLEAR"
        risk_level = "Low"
        recommended_action = "No further action required. Proceed with application."
    elif any(m["match_type"] == "exact" and m["dob_match"] for m in matches):
        disposition = "CONFIRMED_HIT"
        risk_level = "Critical"
        recommended_action = (
            "STOP — Do not proceed. Escalate to BSA/AML officer immediately. "
            "File SAR if warranted. Do not inform applicant of match."
        )
    else:
        disposition = "POTENTIAL_MATCH"
        risk_level = "High"
        recommended_action = (
            "Manual review required. Compare applicant documentation against "
            "SDN entry details. Verify DOB, nationality, and physical address. "
            "Escalate to compliance if match cannot be ruled out within 24 hours."
        )

    return {
        "screening_id": f"SCR-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "applicant": {
            "name": full_name,
            "dob": dob,
            "citizenship": citizenship,
        },
        "screening_type": screening_type,
        "lists_checked": [
            "OFAC SDN",
            "OFAC Consolidated Non-SDN",
            "UN Security Council",
            "EU Consolidated Sanctions",
            "FinCEN 314(a)",
        ],
        "disposition": disposition,
        "risk_level": risk_level,
        "matches": matches,
        "recommended_action": recommended_action,
        "review_deadline": None if disposition == "CLEAR" else "24 hours",
    }


def verify_identity(
    id_document_data: dict[str, Any],
) -> dict[str, Any]:
    """Verify identity for CIP (Customer Identification Program) compliance.

    Cross-references ID document data against public records and credit
    header data to validate the applicant's identity.

    Args:
        id_document_data: Dict containing at minimum ``full_name``, ``dob``,
            ``ssn_last4``, ``address``, and ``id_type`` (e.g., ``"drivers_license"``).

    Returns:
        Identity verification result with field-level match indicators
        and overall verification status.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("verify_identity")

    full_name = id_document_data.get("full_name", "Unknown")
    logger.info("kyc_aml_screening.verify_identity | name=%s", full_name)

    # Simulate verification — all mock applicants pass CIP
    return {
        "verification_id": f"CIP-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "applicant_name": full_name,
        "id_type": id_document_data.get("id_type", "drivers_license"),
        "verification_status": "VERIFIED",
        "field_matches": {
            "name": {"match": True, "confidence": 0.98},
            "date_of_birth": {"match": True, "confidence": 0.99},
            "ssn": {"match": True, "confidence": 1.0},
            "address": {
                "match": True,
                "confidence": 0.92,
                "note": "Address matched to credit header within 24 months",
            },
        },
        "identity_score": 95,
        "risk_indicators": [],
        "cip_compliant": True,
        "documentary_verification": True,
        "non_documentary_verification": True,
    }


def check_pep_status(
    full_name: str,
    country: str = "US",
) -> dict[str, Any]:
    """Check if an individual is a Politically Exposed Person (PEP).

    Args:
        full_name: Full legal name to screen.
        country: Country of residence or citizenship.

    Returns:
        PEP screening result with match details if applicable.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("check_pep_status")

    logger.info(
        "kyc_aml_screening.check_pep_status | name=%s country=%s",
        full_name,
        country,
    )

    matches = []
    for pep in _PEP_DATABASE:
        score = _fuzzy_match_score(full_name, pep["name"])
        if score >= 0.3:
            matches.append({
                "matched_name": pep["name"],
                "match_score": round(score, 3),
                "country": pep["country"],
                "position": pep["position"],
                "level": pep["level"],
                "status": pep["status"],
            })

    return {
        "screening_id": f"PEP-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "applicant_name": full_name,
        "country_screened": country,
        "is_pep": len(matches) > 0,
        "matches": matches,
        "enhanced_due_diligence_required": len(matches) > 0,
    }
