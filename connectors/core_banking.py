"""
Core Banking System Connector
==============================

Simulates integration with a core banking / Customer Information System (CIS)
such as FIS Profile, Jack Henry Silverlake, or Fiserv DNA.

In production this connector would:
  - Query the CIS via secure API or mainframe screen-scrape adapter
  - Return customer master data, existing product relationships, and
    aggregate lending exposure for cross-sell / risk assessment

Mock data includes three test customers with varying relationship depth.
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIMULATED_LATENCY_S = 0.15
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

# ---------------------------------------------------------------------------
# Mock customer database
# ---------------------------------------------------------------------------
_CUSTOMERS: dict[str, dict[str, Any]] = {
    # Key = (ssn_last4, dob) tuple stored as string for lookup
    "4521_1988-03-15": {
        "customer_id": "CUS-100482",
        "first_name": "Sarah",
        "last_name": "Chen",
        "ssn_last4": "4521",
        "date_of_birth": "1988-03-15",
        "email": "sarah.chen@email.com",
        "phone": "+1-415-555-0173",
        "address": {
            "street": "742 Evergreen Terrace",
            "city": "San Mateo",
            "state": "CA",
            "zip": "94401",
        },
        "relationship_since": "2016-09-01",
        "segment": "Premier",
        "risk_rating": "Low",
        "kyc_status": "Verified",
        "kyc_last_refreshed": "2025-11-10",
        "existing_customer": True,
    },
    "7834_1990-07-22": {
        "customer_id": "CUS-203910",
        "first_name": "Marcus",
        "last_name": "Johnson",
        "ssn_last4": "7834",
        "date_of_birth": "1990-07-22",
        "email": "marcus.j@email.com",
        "phone": "+1-312-555-0298",
        "address": {
            "street": "1100 S Michigan Ave Apt 4B",
            "city": "Chicago",
            "state": "IL",
            "zip": "60605",
        },
        "relationship_since": "2022-03-15",
        "segment": "Standard",
        "risk_rating": "Medium",
        "kyc_status": "Verified",
        "kyc_last_refreshed": "2025-06-20",
        "existing_customer": True,
    },
    "9156_1985-11-03": {
        "customer_id": None,  # new-to-bank
        "first_name": "Elena",
        "last_name": "Rodriguez",
        "ssn_last4": "9156",
        "date_of_birth": "1985-11-03",
        "existing_customer": False,
    },
}

_PRODUCTS: dict[str, list[dict[str, Any]]] = {
    "CUS-100482": [
        {
            "product_type": "Checking",
            "account_number_masked": "****3847",
            "status": "Active",
            "opened_date": "2016-09-01",
            "current_balance": 24_850.33,
        },
        {
            "product_type": "Savings",
            "account_number_masked": "****3848",
            "status": "Active",
            "opened_date": "2016-09-01",
            "current_balance": 112_400.00,
        },
        {
            "product_type": "Credit Card",
            "account_number_masked": "****9012",
            "status": "Active",
            "opened_date": "2019-02-14",
            "credit_limit": 25_000.00,
            "current_balance": 3_241.67,
        },
    ],
    "CUS-203910": [
        {
            "product_type": "Checking",
            "account_number_masked": "****6201",
            "status": "Active",
            "opened_date": "2022-03-15",
            "current_balance": 4_312.89,
        },
    ],
}


def _maybe_fail(operation: str) -> None:
    """Simulate random transient failures."""
    if random.random() < ERROR_RATE:
        logger.error("core_banking.%s — simulated transient failure", operation)
        raise ConnectionError(
            f"Core banking system unavailable (simulated). Operation: {operation}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_customer(ssn_last4: str, dob: str) -> dict[str, Any]:
    """Look up a customer by SSN last-4 and date of birth.

    Args:
        ssn_last4: Last four digits of SSN (e.g. ``"4521"``).
        dob: Date of birth as ISO-8601 string ``YYYY-MM-DD``.

    Returns:
        Dict with customer master data, or a slim dict with
        ``existing_customer=False`` if no match is found.

    Raises:
        ConnectionError: On simulated transient failure.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("lookup_customer")

    key = f"{ssn_last4}_{dob}"
    logger.info(
        "core_banking.lookup_customer | ssn_last4=%s dob=%s | match=%s",
        ssn_last4,
        dob,
        key in _CUSTOMERS,
    )

    if key in _CUSTOMERS:
        return {
            "status": "found",
            "timestamp": datetime.utcnow().isoformat(),
            "customer": _CUSTOMERS[key],
        }

    return {
        "status": "not_found",
        "timestamp": datetime.utcnow().isoformat(),
        "customer": {"existing_customer": False},
    }


def get_existing_products(customer_id: str) -> dict[str, Any]:
    """Retrieve all products held by an existing customer.

    Args:
        customer_id: Internal CIS customer identifier (e.g. ``"CUS-100482"``).

    Returns:
        Dict containing a list of product records.

    Raises:
        ConnectionError: On simulated transient failure.
        ValueError: If *customer_id* is ``None`` (new-to-bank customer).
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("get_existing_products")

    if customer_id is None:
        raise ValueError("Cannot retrieve products for a new-to-bank customer.")

    products = _PRODUCTS.get(customer_id, [])
    logger.info(
        "core_banking.get_existing_products | customer_id=%s | count=%d",
        customer_id,
        len(products),
    )
    return {
        "customer_id": customer_id,
        "timestamp": datetime.utcnow().isoformat(),
        "products": products,
        "total_relationship_value": sum(
            p.get("current_balance", 0) for p in products
        ),
    }


def get_lending_footprint() -> dict[str, Any]:
    """Return aggregate lending exposure across the mock portfolio.

    This would typically be used by the underwriting engine to assess
    concentration risk and portfolio-level limits.

    Returns:
        Summary dict with total outstanding balances by product type.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("get_lending_footprint")

    logger.info("core_banking.get_lending_footprint | called")
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_mortgage_exposure": 42_500_000.00,
        "total_heloc_exposure": 8_200_000.00,
        "total_auto_exposure": 12_100_000.00,
        "total_unsecured_exposure": 6_750_000.00,
        "portfolio_delinquency_rate_30d": 0.018,
        "portfolio_delinquency_rate_60d": 0.007,
        "portfolio_delinquency_rate_90d": 0.003,
    }
