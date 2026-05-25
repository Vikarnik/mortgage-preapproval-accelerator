"""
Mortgage Pre-Approval Accelerator — Connector Package

This package provides mock connector stubs that simulate the external integrations
required for automated mortgage pre-approval decisioning. Each connector mirrors
a real-world system used in production mortgage origination pipelines.

Connectors included:
    - core_banking:          Core banking / CIS customer lookup (e.g., FIS, Jack Henry)
    - credit_bureau:         Tri-merge credit report via SOAP-to-REST adapter
    - document_ocr:          Document OCR extraction service (e.g., Ocrolus, Blend)
    - kyc_aml_screening:     OFAC / sanctions / PEP screening (e.g., LexisNexis)
    - aus_service:           Automated Underwriting (DU / LP simulator)
    - employer_verification: VOIE / The Work Number employment verification
    - property_valuation:    AVM automated valuation model (e.g., CoreLogic, HouseCanary)
"""

from .core_banking import lookup_customer, get_existing_products, get_lending_footprint
from .credit_bureau import pull_credit_report
from .document_ocr import extract_document
from .kyc_aml_screening import screen_individual, verify_identity, check_pep_status
from .aus_service import submit_to_du, submit_to_lpa
from .employer_verification import verify_employment
from .property_valuation import get_avm_estimate

__all__ = [
    "lookup_customer",
    "get_existing_products",
    "get_lending_footprint",
    "pull_credit_report",
    "extract_document",
    "screen_individual",
    "verify_identity",
    "check_pep_status",
    "submit_to_du",
    "submit_to_lpa",
    "verify_employment",
    "get_avm_estimate",
]
