"""
Employer Verification (VOIE) Connector
=========================================

Simulates integration with The Work Number (Equifax Workforce Solutions)
and similar Verification of Income and Employment (VOIE) services.

In production this connector would:
  - Submit verification requests via The Work Number API
  - Retrieve employment history, income, and tenure data directly
    from employer payroll systems
  - Bypass the need for manual VOE letters in many cases

Mock scenarios:
  - Currently employed, stable tenure (Sarah Chen)
  - Recently changed jobs with employment gap (Marcus Johnson)
  - Self-employed / 1099 contractor (Elena Rodriguez — requires add'l docs)
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
SIMULATED_LATENCY_S = 0.25
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

EmploymentStatus = Literal[
    "Currently Employed",
    "Terminated",
    "On Leave",
    "Contractor/Self-Employed",
    "Unable to Verify",
]

# ---------------------------------------------------------------------------
# Mock employment records
# ---------------------------------------------------------------------------

_EMPLOYMENT_RECORDS: dict[str, dict[str, Any]] = {
    # ---- Stable employment ------------------------------------------------
    "enc_ssn_sarah_chen__horizon_analytics": {
        "verification_status": "VERIFIED",
        "employment_status": "Currently Employed",
        "employer": {
            "name": "Horizon Analytics Inc.",
            "ein": "94-3204178",
            "address": "500 Terry A Francois Blvd, San Francisco, CA 94158",
            "industry": "Technology — Data Analytics",
            "employee_count_range": "500-999",
            "work_number_employer_code": "23847",
        },
        "employee": {
            "name": "Sarah L Chen",
            "employee_id": "HA-10482",
            "hire_date": "2019-01-14",
            "current_title": "Senior Data Engineer",
            "department": "Engineering",
            "employment_type": "Full-Time",
            "status": "Active",
        },
        "income": {
            "base_salary_annual": 145_200.00,
            "pay_frequency": "Semi-Monthly",
            "base_pay_per_period": 6_050.00,
            "most_recent_pay_date": "2026-05-05",
            "ytd_gross_income": 60_500.00,
            "prior_year_w2_income": 142_800.00,
            "two_years_prior_w2_income": 135_000.00,
            "overtime_eligible": False,
            "bonus_eligible": True,
            "bonus_last_year": 18_000.00,
            "commission": 0.00,
        },
        "employment_history": [
            {
                "employer": "Horizon Analytics Inc.",
                "title": "Senior Data Engineer",
                "start_date": "2021-06-01",
                "end_date": None,
                "salary": 145_200.00,
            },
            {
                "employer": "Horizon Analytics Inc.",
                "title": "Data Engineer",
                "start_date": "2019-01-14",
                "end_date": "2021-05-31",
                "salary": 120_000.00,
            },
        ],
        "probability_of_continued_employment": 0.95,
    },

    # ---- Recent job change with gap ----------------------------------------
    "enc_ssn_marcus_johnson__midwest_supply_chain": {
        "verification_status": "VERIFIED",
        "employment_status": "Currently Employed",
        "employer": {
            "name": "Midwest Supply Chain Corp.",
            "ein": "36-7891024",
            "address": "200 W Adams St Ste 1400, Chicago, IL 60606",
            "industry": "Logistics & Supply Chain",
            "employee_count_range": "1000-4999",
            "work_number_employer_code": "41023",
        },
        "employee": {
            "name": "Marcus D Johnson",
            "employee_id": "MSC-30291",
            "hire_date": "2025-09-08",
            "current_title": "Supply Chain Analyst",
            "department": "Operations",
            "employment_type": "Full-Time",
            "status": "Active",
        },
        "income": {
            "base_salary_annual": 82_400.00,
            "pay_frequency": "Bi-Weekly",
            "base_pay_per_period": 3_169.23,
            "most_recent_pay_date": "2026-04-18",
            "ytd_gross_income": 25_353.84,
            "prior_year_w2_income": 26_773.33,  # partial year at new job
            "two_years_prior_w2_income": 68_500.00,  # full year at prior job
            "overtime_eligible": False,
            "bonus_eligible": False,
            "bonus_last_year": 0.00,
            "commission": 0.00,
        },
        "employment_history": [
            {
                "employer": "Midwest Supply Chain Corp.",
                "title": "Supply Chain Analyst",
                "start_date": "2025-09-08",
                "end_date": None,
                "salary": 82_400.00,
            },
            {
                "employer": "LogiTrak Solutions",
                "title": "Logistics Coordinator",
                "start_date": "2021-03-15",
                "end_date": "2025-06-30",
                "salary": 68_500.00,
            },
        ],
        "employment_gap": {
            "from_date": "2025-07-01",
            "to_date": "2025-09-07",
            "duration_days": 69,
            "explanation_required": True,
            "flag": "Employment gap of 69 days between prior and current employer. "
                    "Borrower must provide written explanation per FNMA B3-3.1-09.",
        },
        "probability_of_continued_employment": 0.82,
    },

    # ---- Self-employed / 1099 contractor -----------------------------------
    "enc_ssn_elena_rodriguez__self_employed": {
        "verification_status": "UNABLE_TO_VERIFY",
        "employment_status": "Contractor/Self-Employed",
        "employer": {
            "name": "Rodriguez Design Consulting LLC",
            "ein": "95-6120483",
            "address": "4200 W Pico Blvd Unit 7, Los Angeles, CA 90019",
            "industry": "Professional Services — Design Consulting",
            "employee_count_range": "1-4",
            "work_number_employer_code": None,  # not enrolled
        },
        "employee": {
            "name": "Elena M Rodriguez",
            "employee_id": None,
            "hire_date": "2020-04-01",
            "current_title": "Owner / Principal Consultant",
            "department": None,
            "employment_type": "Self-Employed",
            "status": "Active",
        },
        "income": {
            "base_salary_annual": None,
            "pay_frequency": "Irregular",
            "base_pay_per_period": None,
            "most_recent_pay_date": None,
            "ytd_gross_income": None,
            "prior_year_schedule_c_net": 110_500.00,
            "two_years_prior_schedule_c_net": 94_200.00,
            "average_monthly_se_income": 8_529.17,
            "overtime_eligible": False,
            "bonus_eligible": False,
            "commission": None,
        },
        "additional_docs_required": [
            "2 years of personal federal tax returns with all schedules",
            "2 years of business federal tax returns (if applicable)",
            "Year-to-date profit & loss statement",
            "Business bank statements (most recent 3 months)",
            "CPA / tax preparer letter confirming business is active",
            "Business license or articles of organization",
        ],
        "self_employment_notes": (
            "The Work Number does not have payroll records for this employer. "
            "Self-employment income must be documented via tax returns. "
            "Per FNMA B3-3.2-01, use the lesser of the 2-year average or the "
            "most recent year's net income."
        ),
        "calculated_qualifying_income": {
            "method": "2-year average of Schedule C net profit",
            "year_1_net": 94_200.00,
            "year_2_net": 110_500.00,
            "average": 102_350.00,
            "monthly_qualifying": 8_529.17,
            "used_for_dti": 8_529.17,
        },
        "probability_of_continued_employment": 0.70,
    },
}


def _maybe_fail(operation: str) -> None:
    if random.random() < ERROR_RATE:
        logger.error(
            "employer_verification.%s — simulated service failure", operation
        )
        raise ConnectionError(
            f"The Work Number service unavailable (simulated). Operation: {operation}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_employment(
    ssn_encrypted: str,
    employer_name: str,
) -> dict[str, Any]:
    """Verify employment and income via The Work Number / VOIE.

    Args:
        ssn_encrypted: Encrypted SSN token (maps to mock record key).
        employer_name: Employer name for cross-referencing (used for
                       constructing the lookup key in mock data).

    Returns:
        Employment verification result including employment status,
        income data, employment history, and any flags/conditions.

    Raises:
        ConnectionError: On simulated transient failure.
        KeyError: If no mock record matches the lookup key.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("verify_employment")

    # Build lookup key
    employer_slug = employer_name.lower().replace(" ", "_").replace(".", "")
    # Try direct key first, then partial match
    key = f"{ssn_encrypted}__{employer_slug}"

    matched_key = None
    for record_key in _EMPLOYMENT_RECORDS:
        if key == record_key or ssn_encrypted in record_key:
            matched_key = record_key
            break

    if matched_key is None:
        raise KeyError(
            f"No employment record found for ssn_token='{ssn_encrypted}', "
            f"employer='{employer_name}'. "
            f"Available keys: {list(_EMPLOYMENT_RECORDS.keys())}"
        )

    record = _EMPLOYMENT_RECORDS[matched_key]

    logger.info(
        "employer_verification.verify_employment | ssn_token=%s employer=%s "
        "status=%s verified=%s",
        ssn_encrypted[:16] + "...",
        employer_name,
        record["employment_status"],
        record["verification_status"],
    )

    return {
        "verification_id": f"VOIE-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "source": "The Work Number / Equifax Workforce Solutions",
        **record,
    }
