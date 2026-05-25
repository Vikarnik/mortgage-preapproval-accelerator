"""
Automated Underwriting System (AUS) Connector
================================================

Simulates submission to Fannie Mae Desktop Underwriter (DU) and
Freddie Mac Loan Product Advisor (LPA) — the two primary automated
underwriting engines used in conventional mortgage origination.

In production this connector would:
  - Marshal application data into MISMO 3.4 XML format
  - Submit via secure B2B gateway to DU or LPA
  - Parse the MISMO XML response into structured findings
  - Return risk assessment, eligibility determination, and conditions

Decision logic (simplified):
  - FICO >= 720 AND DTI <= 43%  →  Approve/Eligible
  - FICO 660-719 OR DTI 43-50%  →  Approve/Ineligible (with conditions)
  - FICO < 660 OR DTI > 50%     →  Refer (manual underwriting required)

Includes conditions lists, risk factors, and appraisal waiver eligibility.
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIMULATED_LATENCY_S = 0.4
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

Recommendation = Literal[
    "Approve/Eligible",
    "Approve/Ineligible",
    "Refer",
    "Refer with Caution",
    "Out of Scope",
]


def _maybe_fail(operation: str) -> None:
    if random.random() < ERROR_RATE:
        logger.error("aus_service.%s — simulated AUS gateway failure", operation)
        raise ConnectionError(
            f"AUS gateway returned HTTP 503 (simulated). Operation: {operation}"
        )


def _calculate_dti(application: dict[str, Any]) -> float:
    """Calculate debt-to-income ratio from application data."""
    monthly_income = application.get("monthly_income", 0)
    if monthly_income <= 0:
        return 999.0
    monthly_debts = application.get("monthly_debts", 0)
    proposed_payment = application.get("proposed_monthly_payment", 0)
    return round((monthly_debts + proposed_payment) / monthly_income * 100, 2)


def _calculate_ltv(application: dict[str, Any]) -> float:
    """Calculate loan-to-value ratio."""
    loan_amount = application.get("loan_amount", 0)
    property_value = application.get("property_value", 0)
    if property_value <= 0:
        return 999.0
    return round(loan_amount / property_value * 100, 2)


def _assess(
    fico: int,
    dti: float,
    ltv: float,
    application: dict[str, Any],
) -> tuple[Recommendation, list[str], list[str], bool]:
    """Core underwriting logic returning (recommendation, conditions, risk_factors, appraisal_waiver)."""
    conditions: list[str] = []
    risk_factors: list[str] = []
    appraisal_waiver = False

    # Bankruptcy check
    has_bankruptcy = application.get("has_bankruptcy", False)
    bankruptcy_discharge_date = application.get("bankruptcy_discharge_date")

    if has_bankruptcy:
        risk_factors.append(
            f"Chapter 7 bankruptcy discharged {bankruptcy_discharge_date}. "
            "Minimum 4-year seasoning required for conventional."
        )

    # Self-employment check
    is_self_employed = application.get("is_self_employed", False)
    if is_self_employed:
        conditions.append(
            "Provide 2 years of federal tax returns (personal + business) "
            "with all schedules."
        )
        conditions.append(
            "CPA letter or year-to-date profit & loss statement required."
        )
        risk_factors.append("Self-employment income — requires income stability analysis.")

    # Late payments
    derogatory_count = application.get("derogatory_count", 0)
    if derogatory_count > 0:
        risk_factors.append(
            f"{derogatory_count} derogatory tradeline event(s) in credit history."
        )

    # High utilization
    revolving_utilization = application.get("revolving_utilization", 0)
    if revolving_utilization > 0.50:
        risk_factors.append(
            f"Revolving utilization at {revolving_utilization:.0%} — "
            "elevated credit risk indicator."
        )

    # Decision matrix
    if fico < 620:
        recommendation: Recommendation = "Refer with Caution"
        risk_factors.append(f"Representative FICO {fico} below minimum threshold of 620.")
        conditions.append("Manual underwriting required — DU/LP cannot approve.")
    elif fico < 660 or dti > 50.0 or has_bankruptcy:
        recommendation = "Refer"
        if dti > 50.0:
            risk_factors.append(f"DTI ratio {dti:.1f}% exceeds maximum of 50%.")
        if fico < 660:
            risk_factors.append(f"Representative FICO {fico} below preferred threshold.")
        conditions.append("Submit to manual underwriting for review.")
    elif fico < 720 or (43.0 < dti <= 50.0):
        recommendation = "Approve/Ineligible"
        if dti > 43.0:
            conditions.append(
                f"DTI of {dti:.1f}% exceeds standard 43% guideline — "
                "compensating factors required."
            )
        if ltv > 80.0:
            conditions.append(
                f"LTV of {ltv:.1f}% requires private mortgage insurance (PMI)."
            )
        conditions.append("Verify employment within 10 business days of closing.")
        conditions.append("Verify assets — 2 months bank statements required.")
    else:
        recommendation = "Approve/Eligible"
        if ltv > 80.0:
            conditions.append(
                f"LTV of {ltv:.1f}% requires private mortgage insurance (PMI)."
            )
        conditions.append("Standard verification of employment required.")
        # Appraisal waiver for low-risk
        if ltv <= 80.0 and fico >= 740:
            appraisal_waiver = True

    return recommendation, conditions, risk_factors, appraisal_waiver


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def submit_to_du(application_data: dict[str, Any]) -> dict[str, Any]:
    """Submit a loan application to Fannie Mae Desktop Underwriter (DU).

    Args:
        application_data: Dict containing at minimum:
            - ``fico`` (int): Representative FICO score
            - ``monthly_income`` (float): Gross monthly income
            - ``monthly_debts`` (float): Total monthly debt obligations
            - ``proposed_monthly_payment`` (float): Proposed PITI payment
            - ``loan_amount`` (float): Requested loan amount
            - ``property_value`` (float): Appraised / estimated value
            - ``loan_purpose`` (str): ``"Purchase"`` or ``"Refinance"``
            - ``property_type`` (str): ``"SFR"``, ``"Condo"``, ``"Townhouse"``
            - Optional: ``has_bankruptcy``, ``bankruptcy_discharge_date``,
              ``is_self_employed``, ``derogatory_count``, ``revolving_utilization``

    Returns:
        DU findings dict with recommendation, conditions, risk factors,
        appraisal waiver eligibility, and MISMO-style metadata.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("submit_to_du")

    fico = application_data.get("fico", 0)
    dti = _calculate_dti(application_data)
    ltv = _calculate_ltv(application_data)

    recommendation, conditions, risk_factors, appraisal_waiver = _assess(
        fico, dti, ltv, application_data
    )

    logger.info(
        "aus_service.submit_to_du | fico=%d dti=%.1f%% ltv=%.1f%% → %s",
        fico, dti, ltv, recommendation,
    )

    return {
        "system": "Desktop Underwriter (DU)",
        "version": "11.2",
        "case_id": f"DU-{random.randint(1000000, 9999999)}",
        "submission_date": datetime.utcnow().isoformat(),
        "mismo_version": "3.4",
        "recommendation": recommendation,
        "risk_classification": (
            "Accept" if "Approve" in recommendation else "Caution"
        ),
        "key_ratios": {
            "front_end_dti": round(dti * 0.6, 2),  # housing ratio approx
            "back_end_dti": dti,
            "ltv": ltv,
            "cltv": ltv,  # no subordinate financing in mock
        },
        "credit_risk_assessment": {
            "representative_fico": fico,
            "credit_risk_grade": (
                "A+" if fico >= 760 else
                "A" if fico >= 720 else
                "B" if fico >= 680 else
                "C" if fico >= 640 else "D"
            ),
        },
        "conditions": conditions,
        "risk_factors": risk_factors,
        "appraisal_waiver_eligible": appraisal_waiver,
        "appraisal_waiver_message": (
            "Property Inspection Waiver (PIW) offered. Full appraisal not required."
            if appraisal_waiver
            else "Full appraisal required."
        ),
        "eligible_products": (
            ["30-Year Fixed", "15-Year Fixed", "7/1 ARM", "5/1 ARM"]
            if "Approve" in recommendation
            else ["30-Year Fixed (manual UW only)"]
        ),
        "message_codes": [
            {"code": "0001", "text": "Submission accepted and processed."},
            {"code": "1120", "text": f"Representative credit score: {fico}."},
            {"code": "2040", "text": f"Total DTI ratio: {dti:.1f}%."},
        ],
    }


def submit_to_lpa(application_data: dict[str, Any]) -> dict[str, Any]:
    """Submit a loan application to Freddie Mac Loan Product Advisor (LPA).

    Args:
        application_data: Same schema as :func:`submit_to_du`.

    Returns:
        LPA findings dict — structurally similar to DU but with
        Freddie Mac-specific terminology and product eligibility.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("submit_to_lpa")

    fico = application_data.get("fico", 0)
    dti = _calculate_dti(application_data)
    ltv = _calculate_ltv(application_data)

    recommendation, conditions, risk_factors, appraisal_waiver = _assess(
        fico, dti, ltv, application_data
    )

    # Map DU terminology to LPA equivalents
    lpa_recommendation_map: dict[str, str] = {
        "Approve/Eligible": "Accept",
        "Approve/Ineligible": "Accept (with conditions)",
        "Refer": "Caution — Refer to underwriter",
        "Refer with Caution": "Caution — Not recommended",
        "Out of Scope": "Ineligible",
    }

    lpa_rec = lpa_recommendation_map.get(recommendation, recommendation)

    logger.info(
        "aus_service.submit_to_lpa | fico=%d dti=%.1f%% ltv=%.1f%% → %s",
        fico, dti, ltv, lpa_rec,
    )

    # LPA-specific: ACE (Automated Collateral Evaluation) waiver
    ace_eligible = appraisal_waiver and ltv <= 75.0

    return {
        "system": "Loan Product Advisor (LPA)",
        "version": "5.0",
        "case_id": f"LP-{random.randint(1000000, 9999999)}",
        "submission_date": datetime.utcnow().isoformat(),
        "mismo_version": "3.4",
        "recommendation": lpa_rec,
        "feedback_certificate_id": f"FC-{random.randint(100000, 999999)}",
        "key_ratios": {
            "housing_expense_ratio": round(dti * 0.6, 2),
            "total_debt_ratio": dti,
            "ltv": ltv,
            "tltv": ltv,
        },
        "credit_assessment": {
            "indicator_score": fico,
            "lp_risk_class": (
                "Minimal" if fico >= 740 else
                "Low" if fico >= 700 else
                "Moderate" if fico >= 660 else "High"
            ),
        },
        "purchase_eligibility_conditions": conditions,
        "risk_factors": risk_factors,
        "ace_eligible": ace_eligible,
        "ace_message": (
            "ACE appraisal waiver approved — automated collateral evaluation accepted."
            if ace_eligible
            else "ACE not available — standard appraisal required."
        ),
        "eligible_offerings": (
            ["Super Conforming 30-Year", "Super Conforming 15-Year",
             "5/1 ARM", "Home Possible (if eligible)"]
            if "Accept" in lpa_rec
            else ["Manual underwriting pathway only"]
        ),
        "feedback_messages": [
            {"code": "LP001", "text": "Feedback certificate issued."},
            {"code": "LP210", "text": f"Credit indicator score: {fico}."},
            {"code": "LP305", "text": f"Debt ratio: {dti:.1f}%."},
        ],
    }
