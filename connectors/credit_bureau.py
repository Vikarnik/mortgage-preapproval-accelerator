"""
Tri-Merge Credit Bureau Connector
===================================

Simulates a legacy SOAP-to-REST adapter that aggregates credit data from all
three major bureaus (Equifax, Experian, TransUnion) into a single tri-merge
credit report — the standard format used in mortgage origination.

In production this would connect to:
  - A credit reporting agency aggregator (e.g., CoreLogic Credco, MeridianLink)
  - Via a SOAP-to-REST translation layer (many bureaus still expose SOAP endpoints)
  - Using MISMO-compliant XML payloads under the hood

This mock includes:
  - Realistic tradeline data (mortgage, auto, credit cards, student loans)
  - Payment history arrays (24-month rolling)
  - Public records (bankruptcies, liens, judgments)
  - Hard inquiry history
  - Simulated latency, retry logic, and error scenarios

Three credit profiles are provided:
  - Excellent (780+ FICO, clean history)
  - Fair     (680 FICO, some late payments)
  - Poor     (580 FICO, prior bankruptcy)
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_LATENCY_S = 0.35          # credit pulls are slow in real life
MAX_RETRIES = 3
RETRY_BACKOFF_S = 0.2
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))
TIMEOUT_RATE = float(os.environ.get("CREDIT_TIMEOUT_RATE", "0.03"))

# ---------------------------------------------------------------------------
# Mock credit profiles keyed by encrypted-SSN stub
# ---------------------------------------------------------------------------

_PROFILES: dict[str, dict[str, Any]] = {
    # ---- Excellent --------------------------------------------------------
    "enc_ssn_sarah_chen": {
        "borrower": {
            "name": "Sarah Chen",
            "ssn_masked": "XXX-XX-4521",
            "dob": "1988-03-15",
            "current_address": "742 Evergreen Terrace, San Mateo, CA 94401",
            "prior_address": "220 Pacific Ave Apt 3, San Francisco, CA 94115",
        },
        "scores": {
            "equifax": {"model": "FICO Score 5", "score": 788},
            "experian": {"model": "FICO Score 2", "score": 792},
            "transunion": {"model": "FICO Score 4", "score": 785},
            "representative_score": 788,  # middle score
        },
        "tradelines": [
            {
                "creditor": "Chase Home Finance",
                "account_type": "Mortgage",
                "account_number_masked": "****3920",
                "date_opened": "2019-06-15",
                "credit_limit_or_original_amount": 320_000,
                "current_balance": 278_450,
                "monthly_payment": 1_685,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,  # C=Current
                "high_balance": 320_000,
                "terms_months": 360,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Toyota Motor Credit",
                "account_type": "Auto Loan",
                "account_number_masked": "****7712",
                "date_opened": "2022-01-10",
                "credit_limit_or_original_amount": 28_500,
                "current_balance": 14_320,
                "monthly_payment": 485,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 28_500,
                "terms_months": 60,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Citi Cards",
                "account_type": "Revolving",
                "account_number_masked": "****9012",
                "date_opened": "2017-04-22",
                "credit_limit_or_original_amount": 25_000,
                "current_balance": 3_241,
                "monthly_payment": 150,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 8_400,
                "terms_months": None,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Discover Financial",
                "account_type": "Revolving",
                "account_number_masked": "****2208",
                "date_opened": "2015-08-30",
                "credit_limit_or_original_amount": 15_000,
                "current_balance": 0,
                "monthly_payment": 0,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 4_500,
                "terms_months": None,
                "reporting_bureau": ["EQ", "TU"],
            },
        ],
        "public_records": [],
        "collections": [],
        "inquiries": [
            {
                "creditor": "Toyota Motor Credit",
                "date": "2022-01-05",
                "type": "Hard",
                "bureau": "EX",
            },
        ],
        "summary": {
            "total_accounts": 4,
            "open_accounts": 4,
            "closed_accounts": 0,
            "total_balance": 296_011,
            "total_monthly_payments": 2_320,
            "revolving_utilization": 0.081,
            "derogatory_count": 0,
            "oldest_account_age_months": 130,
            "average_account_age_months": 68,
        },
    },

    # ---- Fair -------------------------------------------------------------
    "enc_ssn_marcus_johnson": {
        "borrower": {
            "name": "Marcus Johnson",
            "ssn_masked": "XXX-XX-7834",
            "dob": "1990-07-22",
            "current_address": "1100 S Michigan Ave Apt 4B, Chicago, IL 60605",
            "prior_address": "550 W Adams St Apt 12, Chicago, IL 60661",
        },
        "scores": {
            "equifax": {"model": "FICO Score 5", "score": 692},
            "experian": {"model": "FICO Score 2", "score": 698},
            "transunion": {"model": "FICO Score 4", "score": 688},
            "representative_score": 692,
        },
        "tradelines": [
            {
                "creditor": "Wells Fargo Auto",
                "account_type": "Auto Loan",
                "account_number_masked": "****4401",
                "date_opened": "2021-09-20",
                "credit_limit_or_original_amount": 22_000,
                "current_balance": 11_200,
                "monthly_payment": 415,
                "payment_status": "Current",
                "payment_history_24m": [
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "C",
                    "C", "C", "C", "C", "30", "C", "C", "C", "30", "C",
                    "C", "C", "C", "C",
                ],
                "high_balance": 22_000,
                "terms_months": 72,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Capital One",
                "account_type": "Revolving",
                "account_number_masked": "****8815",
                "date_opened": "2020-03-10",
                "credit_limit_or_original_amount": 8_000,
                "current_balance": 5_640,
                "monthly_payment": 175,
                "payment_status": "Current",
                "payment_history_24m": [
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "C",
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "C",
                    "C", "C", "C", "C",
                ],
                "high_balance": 7_200,
                "terms_months": None,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "FedLoan Servicing",
                "account_type": "Student Loan",
                "account_number_masked": "****3309",
                "date_opened": "2014-08-15",
                "credit_limit_or_original_amount": 45_000,
                "current_balance": 28_700,
                "monthly_payment": 380,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 45_000,
                "terms_months": 120,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Best Buy / Citibank",
                "account_type": "Revolving",
                "account_number_masked": "****1120",
                "date_opened": "2023-01-05",
                "credit_limit_or_original_amount": 3_500,
                "current_balance": 1_890,
                "monthly_payment": 75,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 2_800,
                "terms_months": None,
                "reporting_bureau": ["EX", "TU"],
            },
        ],
        "public_records": [],
        "collections": [],
        "inquiries": [
            {"creditor": "Best Buy / Citibank", "date": "2023-01-02", "type": "Hard", "bureau": "EX"},
            {"creditor": "Rocket Mortgage", "date": "2025-12-10", "type": "Hard", "bureau": "EQ"},
            {"creditor": "Rocket Mortgage", "date": "2025-12-10", "type": "Hard", "bureau": "EX"},
            {"creditor": "Rocket Mortgage", "date": "2025-12-10", "type": "Hard", "bureau": "TU"},
        ],
        "summary": {
            "total_accounts": 4,
            "open_accounts": 4,
            "closed_accounts": 0,
            "total_balance": 47_430,
            "total_monthly_payments": 1_045,
            "revolving_utilization": 0.655,
            "derogatory_count": 2,
            "oldest_account_age_months": 142,
            "average_account_age_months": 58,
        },
    },

    # ---- Poor -------------------------------------------------------------
    "enc_ssn_elena_rodriguez": {
        "borrower": {
            "name": "Elena Rodriguez",
            "ssn_masked": "XXX-XX-9156",
            "dob": "1985-11-03",
            "current_address": "4200 W Pico Blvd Unit 7, Los Angeles, CA 90019",
            "prior_address": "890 S Figueroa St, Los Angeles, CA 90017",
        },
        "scores": {
            "equifax": {"model": "FICO Score 5", "score": 648},
            "experian": {"model": "FICO Score 2", "score": 655},
            "transunion": {"model": "FICO Score 4", "score": 644},
            "representative_score": 648,
        },
        "tradelines": [
            {
                "creditor": "Bank of America",
                "account_type": "Revolving",
                "account_number_masked": "****5590",
                "date_opened": "2018-06-01",
                "credit_limit_or_original_amount": 10_000,
                "current_balance": 7_820,
                "monthly_payment": 220,
                "payment_status": "Current",
                "payment_history_24m": [
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "30",
                    "30", "C", "C", "C", "C", "C", "C", "60", "30", "C",
                    "C", "C", "C", "C",
                ],
                "high_balance": 9_800,
                "terms_months": None,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Honda Financial Services",
                "account_type": "Auto Loan",
                "account_number_masked": "****2214",
                "date_opened": "2023-03-20",
                "credit_limit_or_original_amount": 18_500,
                "current_balance": 12_100,
                "monthly_payment": 365,
                "payment_status": "Current",
                "payment_history_24m": [
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "C",
                    "C", "C", "C", "C", "C", "C", "C", "C", "C", "C",
                    "C", "C", "C", "C",
                ],
                "high_balance": 18_500,
                "terms_months": 60,
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
            {
                "creditor": "Synchrony / Amazon",
                "account_type": "Revolving",
                "account_number_masked": "****0073",
                "date_opened": "2020-11-15",
                "credit_limit_or_original_amount": 5_000,
                "current_balance": 3_450,
                "monthly_payment": 100,
                "payment_status": "Current",
                "payment_history_24m": ["C"] * 24,
                "high_balance": 4_800,
                "terms_months": None,
                "reporting_bureau": ["EX", "TU"],
            },
        ],
        "public_records": [
            {
                "type": "Bankruptcy",
                "chapter": "Chapter 7",
                "filed_date": "2022-02-10",
                "discharged_date": "2022-06-15",
                "court": "US Bankruptcy Court, Central District of California",
                "case_number": "2:22-bk-12345",
                "status": "Discharged",
                "reporting_bureau": ["EQ", "EX", "TU"],
            },
        ],
        "collections": [
            {
                "creditor": "Pacific Medical Group",
                "original_amount": 2_400,
                "balance": 0,
                "status": "Paid in Full",
                "date_reported": "2021-08-20",
                "date_paid": "2022-09-01",
                "reporting_bureau": ["EQ"],
            },
        ],
        "inquiries": [
            {"creditor": "Honda Financial Services", "date": "2023-03-15", "type": "Hard", "bureau": "EX"},
            {"creditor": "First National Mortgage", "date": "2026-01-05", "type": "Hard", "bureau": "EQ"},
            {"creditor": "First National Mortgage", "date": "2026-01-05", "type": "Hard", "bureau": "EX"},
            {"creditor": "First National Mortgage", "date": "2026-01-05", "type": "Hard", "bureau": "TU"},
        ],
        "summary": {
            "total_accounts": 3,
            "open_accounts": 3,
            "closed_accounts": 0,
            "total_balance": 23_370,
            "total_monthly_payments": 685,
            "revolving_utilization": 0.752,
            "derogatory_count": 5,
            "oldest_account_age_months": 95,
            "average_account_age_months": 52,
            "bankruptcy_on_file": True,
            "bankruptcy_discharge_date": "2022-06-15",
        },
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _simulate_soap_latency() -> None:
    """Simulate the latency of a SOAP-to-REST translation layer."""
    jitter = random.uniform(0.1, 0.25)
    time.sleep(BASE_LATENCY_S + jitter)


def _maybe_fail() -> None:
    if random.random() < TIMEOUT_RATE:
        logger.warning("credit_bureau — simulated bureau timeout")
        raise TimeoutError(
            "Credit bureau request timed out after 30 s (simulated). "
            "Retry with exponential backoff."
        )
    if random.random() < ERROR_RATE:
        logger.error("credit_bureau — simulated bureau unavailable")
        raise ConnectionError(
            "Bureau service returned HTTP 503 Service Unavailable (simulated)."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pull_credit_report(
    ssn_encrypted: str,
    full_name: str,
    dob: str,
    address: str,
    *,
    permissible_purpose: str = "mortgage_origination",
) -> dict[str, Any]:
    """Pull a tri-merge credit report for a mortgage applicant.

    Simulates a SOAP-to-REST adapter call to a credit reporting aggregator.
    Includes automatic retry with exponential backoff on transient failures.

    Args:
        ssn_encrypted: Encrypted SSN token (maps to mock profile key).
        full_name: Borrower full name for soft-match verification.
        dob: Date of birth ``YYYY-MM-DD``.
        address: Current street address for address matching.
        permissible_purpose: FCRA permissible purpose code.

    Returns:
        Comprehensive tri-merge credit report dict containing scores,
        tradelines, public records, collections, inquiries, and summary.

    Raises:
        TimeoutError: If the bureau does not respond within threshold.
        ConnectionError: If the bureau service is unavailable.
        KeyError: If no mock profile matches the encrypted SSN token.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "credit_bureau.pull_credit_report | attempt=%d/%d | "
                "ssn_token=%s name=%s purpose=%s",
                attempt,
                MAX_RETRIES,
                ssn_encrypted[:16] + "...",
                full_name,
                permissible_purpose,
            )

            _simulate_soap_latency()
            _maybe_fail()

            if ssn_encrypted not in _PROFILES:
                raise KeyError(
                    f"No credit profile found for token '{ssn_encrypted}'. "
                    "Verify the SSN encryption and try again."
                )

            profile = _PROFILES[ssn_encrypted]

            return {
                "status": "success",
                "report_id": f"CR-{random.randint(100000, 999999)}",
                "report_date": datetime.utcnow().isoformat(),
                "permissible_purpose": permissible_purpose,
                "mismo_version": "3.4",
                "borrower": profile["borrower"],
                "credit_scores": profile["scores"],
                "tradelines": profile["tradelines"],
                "public_records": profile["public_records"],
                "collections": profile.get("collections", []),
                "inquiries": profile["inquiries"],
                "credit_summary": profile["summary"],
                "fraud_alerts": [],
                "consumer_statement": None,
                "freeze_status": {"equifax": False, "experian": False, "transunion": False},
            }

        except (TimeoutError, ConnectionError) as exc:
            last_error = exc
            logger.warning(
                "credit_bureau.pull_credit_report | attempt %d failed: %s",
                attempt,
                exc,
            )
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_S * (2 ** (attempt - 1))
                time.sleep(backoff)

    # All retries exhausted
    logger.error(
        "credit_bureau.pull_credit_report | all %d attempts failed", MAX_RETRIES
    )
    raise last_error  # type: ignore[misc]
