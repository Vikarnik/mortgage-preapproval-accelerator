"""
Document OCR Extraction Connector
====================================

Simulates integration with a document OCR / intelligent document processing
(IDP) service such as Ocrolus, Blend Doc AI, or AWS Textract.

In production this connector would:
  - Accept uploaded PDF / image documents
  - Submit them to an OCR pipeline for field-level extraction
  - Return structured data with per-field confidence scores
  - Flag low-confidence fields for manual review

Supported document types:
  - W-2 (Wage and Tax Statement)
  - Paystub
  - Bank Statement
  - Tax Return (Form 1040)

Mock data includes a low-confidence scenario where some fields fall below
the 0.85 threshold requiring human-in-the-loop verification.
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
SIMULATED_LATENCY_S = 0.3
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

DocType = Literal["w2", "paystub", "bank_statement", "tax_return"]

# ---------------------------------------------------------------------------
# Mock extraction results
# ---------------------------------------------------------------------------

_W2_EXTRACTIONS: dict[str, dict[str, Any]] = {
    "sarah_chen": {
        "document_type": "W-2",
        "tax_year": 2025,
        "employer": {
            "ein": "94-3204178",
            "name": "Horizon Analytics Inc.",
            "address": "500 Terry A Francois Blvd, San Francisco, CA 94158",
            "confidence": 0.97,
        },
        "employee": {
            "ssn_masked": "XXX-XX-4521",
            "name": "Sarah L Chen",
            "address": "742 Evergreen Terrace, San Mateo, CA 94401",
            "confidence": 0.98,
        },
        "fields": {
            "box_1_wages_tips": {"value": 145_200.00, "confidence": 0.99},
            "box_2_federal_tax_withheld": {"value": 31_844.00, "confidence": 0.98},
            "box_3_social_security_wages": {"value": 145_200.00, "confidence": 0.97},
            "box_4_social_security_tax": {"value": 9_002.40, "confidence": 0.96},
            "box_5_medicare_wages": {"value": 145_200.00, "confidence": 0.97},
            "box_6_medicare_tax": {"value": 2_105.40, "confidence": 0.96},
            "box_12a_code": {"value": "D", "confidence": 0.95},
            "box_12a_amount": {"value": 22_500.00, "confidence": 0.94},
            "box_15_state": {"value": "CA", "confidence": 0.99},
            "box_16_state_wages": {"value": 145_200.00, "confidence": 0.97},
            "box_17_state_tax": {"value": 13_068.00, "confidence": 0.96},
        },
        "quality_score": 0.97,
        "needs_review": False,
    },
    "marcus_johnson": {
        "document_type": "W-2",
        "tax_year": 2025,
        "employer": {
            "ein": "36-7891024",
            "name": "Midwest Supply Chain Corp.",
            "address": "200 W Adams St Ste 1400, Chicago, IL 60606",
            "confidence": 0.95,
        },
        "employee": {
            "ssn_masked": "XXX-XX-7834",
            "name": "Marcus D Johnson",
            "address": "1100 S Michigan Ave Apt 4B, Chicago, IL 60605",
            "confidence": 0.96,
        },
        "fields": {
            "box_1_wages_tips": {"value": 82_400.00, "confidence": 0.98},
            "box_2_federal_tax_withheld": {"value": 14_832.00, "confidence": 0.97},
            "box_3_social_security_wages": {"value": 82_400.00, "confidence": 0.96},
            "box_4_social_security_tax": {"value": 5_108.80, "confidence": 0.95},
            "box_5_medicare_wages": {"value": 82_400.00, "confidence": 0.96},
            "box_6_medicare_tax": {"value": 1_194.80, "confidence": 0.95},
            "box_12a_code": {"value": "D", "confidence": 0.93},
            "box_12a_amount": {"value": 8_000.00, "confidence": 0.91},
            "box_15_state": {"value": "IL", "confidence": 0.99},
            "box_16_state_wages": {"value": 82_400.00, "confidence": 0.97},
            "box_17_state_tax": {"value": 4_039.60, "confidence": 0.96},
        },
        "quality_score": 0.95,
        "needs_review": False,
    },
    # Low-confidence extraction (blurry scan)
    "elena_rodriguez": {
        "document_type": "W-2",
        "tax_year": 2025,
        "employer": {
            "ein": "95-6120483",
            "name": "Rodriguez Design Consulting LLC",
            "address": "4200 W Pico Blvd Unit 7, Los Angeles, CA 90019",
            "confidence": 0.82,  # self-employed — OCR struggles with handwritten EIN
        },
        "employee": {
            "ssn_masked": "XXX-XX-9156",
            "name": "Elena M Rodriguez",
            "address": "4200 W Pico Blvd Unit 7, Los Angeles, CA 90019",
            "confidence": 0.88,
        },
        "fields": {
            "box_1_wages_tips": {"value": 110_500.00, "confidence": 0.79},  # low
            "box_2_federal_tax_withheld": {"value": 18_200.00, "confidence": 0.83},
            "box_3_social_security_wages": {"value": 110_500.00, "confidence": 0.78},  # low
            "box_4_social_security_tax": {"value": 6_851.00, "confidence": 0.76},  # low
            "box_5_medicare_wages": {"value": 110_500.00, "confidence": 0.80},
            "box_6_medicare_tax": {"value": 1_602.25, "confidence": 0.81},
            "box_15_state": {"value": "CA", "confidence": 0.95},
            "box_16_state_wages": {"value": 110_500.00, "confidence": 0.74},  # low
            "box_17_state_tax": {"value": 9_945.00, "confidence": 0.72},  # low
        },
        "quality_score": 0.80,
        "needs_review": True,
        "review_flags": [
            "Low confidence on box_1_wages_tips (0.79) — verify against paystub YTD",
            "Low confidence on box_4_social_security_tax (0.76) — verify manually",
            "Low confidence on box_16/17 state fields — possible smudge/crease on document",
            "Employer EIN confidence below threshold — verify against IRS records",
        ],
    },
}

_PAYSTUB_EXTRACTIONS: dict[str, dict[str, Any]] = {
    "sarah_chen": {
        "document_type": "Paystub",
        "employer_name": "Horizon Analytics Inc.",
        "employee_name": "Sarah L Chen",
        "pay_period": {"start": "2026-04-16", "end": "2026-04-30"},
        "pay_date": "2026-05-05",
        "fields": {
            "gross_pay": {"value": 6_050.00, "confidence": 0.98},
            "ytd_gross": {"value": 54_450.00, "confidence": 0.97},
            "federal_tax": {"value": 1_327.00, "confidence": 0.96},
            "state_tax": {"value": 544.50, "confidence": 0.95},
            "social_security": {"value": 375.10, "confidence": 0.97},
            "medicare": {"value": 87.73, "confidence": 0.96},
            "health_insurance": {"value": 245.00, "confidence": 0.94},
            "dental_insurance": {"value": 32.00, "confidence": 0.93},
            "401k_contribution": {"value": 937.50, "confidence": 0.95},
            "net_pay": {"value": 3_501.17, "confidence": 0.98},
            "ytd_net": {"value": 31_510.53, "confidence": 0.96},
        },
        "pay_frequency": "Semi-Monthly",
        "quality_score": 0.96,
        "needs_review": False,
    },
    "marcus_johnson": {
        "document_type": "Paystub",
        "employer_name": "Midwest Supply Chain Corp.",
        "employee_name": "Marcus D Johnson",
        "pay_period": {"start": "2026-04-01", "end": "2026-04-15"},
        "pay_date": "2026-04-18",
        "fields": {
            "gross_pay": {"value": 3_169.23, "confidence": 0.97},
            "ytd_gross": {"value": 22_184.61, "confidence": 0.95},
            "federal_tax": {"value": 570.46, "confidence": 0.94},
            "state_tax": {"value": 155.29, "confidence": 0.93},
            "social_security": {"value": 196.49, "confidence": 0.96},
            "medicare": {"value": 45.95, "confidence": 0.95},
            "health_insurance": {"value": 189.00, "confidence": 0.92},
            "401k_contribution": {"value": 253.54, "confidence": 0.93},
            "net_pay": {"value": 1_758.50, "confidence": 0.97},
            "ytd_net": {"value": 12_309.50, "confidence": 0.94},
        },
        "pay_frequency": "Bi-Weekly",
        "quality_score": 0.95,
        "needs_review": False,
    },
}

_BANK_STATEMENT_EXTRACTIONS: dict[str, dict[str, Any]] = {
    "sarah_chen": {
        "document_type": "Bank Statement",
        "institution": "JPMorgan Chase",
        "account_number_masked": "****3847",
        "account_type": "Checking",
        "statement_period": {"start": "2026-04-01", "end": "2026-04-30"},
        "fields": {
            "beginning_balance": {"value": 22_415.67, "confidence": 0.98},
            "ending_balance": {"value": 24_850.33, "confidence": 0.99},
            "total_deposits": {"value": 12_100.00, "confidence": 0.97},
            "total_withdrawals": {"value": 9_665.34, "confidence": 0.96},
            "average_daily_balance": {"value": 23_210.44, "confidence": 0.95},
            "lowest_balance": {"value": 18_900.12, "confidence": 0.94},
        },
        "large_deposits": [
            {
                "date": "2026-04-05",
                "amount": 6_050.00,
                "description": "HORIZON ANALYTICS PAYROLL",
                "confidence": 0.97,
            },
            {
                "date": "2026-04-20",
                "amount": 6_050.00,
                "description": "HORIZON ANALYTICS PAYROLL",
                "confidence": 0.98,
            },
        ],
        "nsf_count": 0,
        "overdraft_count": 0,
        "quality_score": 0.97,
        "needs_review": False,
    },
    "marcus_johnson": {
        "document_type": "Bank Statement",
        "institution": "BMO Harris Bank",
        "account_number_masked": "****6201",
        "account_type": "Checking",
        "statement_period": {"start": "2026-04-01", "end": "2026-04-30"},
        "fields": {
            "beginning_balance": {"value": 3_890.22, "confidence": 0.97},
            "ending_balance": {"value": 4_312.89, "confidence": 0.98},
            "total_deposits": {"value": 6_338.46, "confidence": 0.96},
            "total_withdrawals": {"value": 5_915.79, "confidence": 0.95},
            "average_daily_balance": {"value": 3_650.18, "confidence": 0.93},
            "lowest_balance": {"value": 1_204.33, "confidence": 0.91},
        },
        "large_deposits": [
            {
                "date": "2026-04-04",
                "amount": 3_169.23,
                "description": "MIDWEST SUPPLY CHAIN PAYROLL",
                "confidence": 0.96,
            },
            {
                "date": "2026-04-18",
                "amount": 3_169.23,
                "description": "MIDWEST SUPPLY CHAIN PAYROLL",
                "confidence": 0.97,
            },
        ],
        "nsf_count": 0,
        "overdraft_count": 1,
        "quality_score": 0.95,
        "needs_review": False,
    },
    "elena_rodriguez": {
        "document_type": "Bank Statement",
        "institution": "Wells Fargo",
        "account_number_masked": "****8234",
        "account_type": "Checking",
        "statement_period": {"start": "2026-04-01", "end": "2026-04-30"},
        "fields": {
            "beginning_balance": {"value": 8_712.40, "confidence": 0.96},
            "ending_balance": {"value": 11_204.55, "confidence": 0.97},
            "total_deposits": {"value": 14_800.00, "confidence": 0.94},
            "total_withdrawals": {"value": 12_307.85, "confidence": 0.93},
            "average_daily_balance": {"value": 9_450.22, "confidence": 0.91},
            "lowest_balance": {"value": 4_102.30, "confidence": 0.89},
        },
        "large_deposits": [
            {
                "date": "2026-04-03",
                "amount": 8_500.00,
                "description": "ZELLE FROM ACME CORP",
                "confidence": 0.94,
                "flag": "Non-payroll large deposit — verify source",
            },
            {
                "date": "2026-04-15",
                "amount": 4_200.00,
                "description": "VENMO TRANSFER",
                "confidence": 0.92,
                "flag": "Non-payroll large deposit — verify source",
            },
            {
                "date": "2026-04-28",
                "amount": 2_100.00,
                "description": "CHECK DEPOSIT",
                "confidence": 0.88,
                "flag": "Check deposit — verify source for self-employed income",
            },
        ],
        "nsf_count": 0,
        "overdraft_count": 0,
        "quality_score": 0.92,
        "needs_review": True,
        "review_flags": [
            "Multiple non-payroll large deposits — verify income source for self-employed borrower",
            "Irregular deposit pattern — not consistent with stated pay frequency",
        ],
    },
}

_TAX_RETURN_EXTRACTIONS: dict[str, dict[str, Any]] = {
    "elena_rodriguez": {
        "document_type": "Tax Return (Form 1040)",
        "tax_year": 2025,
        "filing_status": "Single",
        "fields": {
            "total_income_line_9": {"value": 118_200.00, "confidence": 0.93},
            "adjusted_gross_income_line_11": {"value": 110_500.00, "confidence": 0.91},
            "schedule_c_gross_receipts": {"value": 142_000.00, "confidence": 0.88},
            "schedule_c_net_profit": {"value": 110_500.00, "confidence": 0.87},
            "schedule_c_expenses": {"value": 31_500.00, "confidence": 0.85},
            "self_employment_tax": {"value": 15_616.00, "confidence": 0.90},
            "total_tax": {"value": 24_850.00, "confidence": 0.92},
            "total_payments": {"value": 26_200.00, "confidence": 0.91},
            "refund_amount": {"value": 1_350.00, "confidence": 0.94},
        },
        "schedules_present": ["Schedule C", "Schedule SE", "Schedule 1"],
        "quality_score": 0.90,
        "needs_review": True,
        "review_flags": [
            "Self-employment income — requires 2-year history for qualification",
            "Schedule C net profit used for qualifying income — verify with tax transcripts",
        ],
    },
}

# Map all extractions by type
_EXTRACTIONS: dict[str, dict[str, dict[str, Any]]] = {
    "w2": _W2_EXTRACTIONS,
    "paystub": _PAYSTUB_EXTRACTIONS,
    "bank_statement": _BANK_STATEMENT_EXTRACTIONS,
    "tax_return": _TAX_RETURN_EXTRACTIONS,
}


def _maybe_fail(operation: str) -> None:
    if random.random() < ERROR_RATE:
        logger.error("document_ocr.%s — simulated OCR service failure", operation)
        raise ConnectionError(
            f"OCR service returned HTTP 502 (simulated). Operation: {operation}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_document(
    doc_type: DocType,
    file_path: str,
    *,
    applicant_key: str = "sarah_chen",
) -> dict[str, Any]:
    """Extract structured data from a mortgage-related document.

    Args:
        doc_type: One of ``"w2"``, ``"paystub"``, ``"bank_statement"``,
                  ``"tax_return"``.
        file_path: Path to the uploaded document (used for logging only
                   in this mock).
        applicant_key: Mock data selector — one of ``"sarah_chen"``,
                       ``"marcus_johnson"``, ``"elena_rodriguez"``.

    Returns:
        Dict with extracted fields, per-field confidence scores, overall
        quality score, and review flags if any field falls below threshold.

    Raises:
        ValueError: If *doc_type* is not recognized.
        KeyError: If no mock data exists for the given *applicant_key* and
                  *doc_type* combination.
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("extract_document")

    if doc_type not in _EXTRACTIONS:
        raise ValueError(
            f"Unsupported document type '{doc_type}'. "
            f"Must be one of: {list(_EXTRACTIONS.keys())}"
        )

    type_data = _EXTRACTIONS[doc_type]
    if applicant_key not in type_data:
        raise KeyError(
            f"No mock extraction for applicant '{applicant_key}' "
            f"and doc_type '{doc_type}'. "
            f"Available: {list(type_data.keys())}"
        )

    result = type_data[applicant_key]

    logger.info(
        "document_ocr.extract_document | doc_type=%s file=%s applicant=%s "
        "quality=%.2f needs_review=%s",
        doc_type,
        file_path,
        applicant_key,
        result["quality_score"],
        result.get("needs_review", False),
    )

    return {
        "status": "success",
        "extraction_id": f"EXT-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "file_path": file_path,
        **result,
    }
