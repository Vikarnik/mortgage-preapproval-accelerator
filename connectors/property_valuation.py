"""
Property Valuation (AVM) Connector
=====================================

Simulates integration with an Automated Valuation Model (AVM) service
such as CoreLogic, HouseCanary, ATTOM, or Black Knight's AVM products.

In production this connector would:
  - Accept a property address and return an estimated market value
  - Provide a confidence interval and valuation quality score
  - Include comparable recent sales (comps) within a radius
  - Return property details (bed/bath, sqft, lot size, year built)
  - Flag properties that cannot be reliably valued (rural, unique, etc.)

Mock properties at three price points:
  - $450K suburban SFR (San Mateo, CA)
  - $320K urban condo (Chicago, IL)
  - $380K metro SFR (Los Angeles, CA)
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIMULATED_LATENCY_S = 0.2
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

# ---------------------------------------------------------------------------
# Mock property database
# ---------------------------------------------------------------------------

_PROPERTIES: dict[str, dict[str, Any]] = {
    "742 evergreen terrace, san mateo, ca 94401": {
        "property_address": {
            "street": "742 Evergreen Terrace",
            "city": "San Mateo",
            "state": "CA",
            "zip": "94401",
            "county": "San Mateo",
            "fips": "06081",
        },
        "avm_estimate": {
            "estimated_value": 458_000,
            "low_estimate": 435_100,
            "high_estimate": 480_900,
            "confidence_score": 0.89,
            "forecast_standard_deviation": 0.05,
            "valuation_date": "2026-05-20",
            "model_version": "AVM-7.3.1",
        },
        "property_details": {
            "property_type": "Single Family Residence",
            "bedrooms": 3,
            "bathrooms": 2.0,
            "living_area_sqft": 1_650,
            "lot_size_sqft": 6_200,
            "year_built": 1978,
            "stories": 1,
            "garage": "2-car attached",
            "pool": False,
            "condition": "Average",
            "last_sale_date": "2019-06-15",
            "last_sale_price": 382_000,
        },
        "comparable_sales": [
            {
                "address": "718 Evergreen Terrace, San Mateo, CA 94401",
                "sale_date": "2026-03-12",
                "sale_price": 462_000,
                "sqft": 1_720,
                "price_per_sqft": 268.60,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "distance_miles": 0.1,
                "similarity_score": 0.94,
            },
            {
                "address": "805 Palm Ave, San Mateo, CA 94401",
                "sale_date": "2026-02-28",
                "sale_price": 445_000,
                "sqft": 1_580,
                "price_per_sqft": 281.65,
                "bedrooms": 3,
                "bathrooms": 1.5,
                "distance_miles": 0.3,
                "similarity_score": 0.88,
            },
            {
                "address": "1120 Oak St, San Mateo, CA 94401",
                "sale_date": "2026-01-15",
                "sale_price": 475_000,
                "sqft": 1_800,
                "price_per_sqft": 263.89,
                "bedrooms": 4,
                "bathrooms": 2.5,
                "distance_miles": 0.5,
                "similarity_score": 0.82,
            },
        ],
        "market_trends": {
            "median_price_zip": 465_000,
            "yoy_appreciation": 0.041,
            "median_dom": 18,
            "inventory_months": 2.1,
            "market_temperature": "Warm",
        },
        "flood_zone": "X (Minimal Risk)",
        "hazard_flags": [],
    },

    "1100 s michigan ave apt 4b, chicago, il 60605": {
        "property_address": {
            "street": "1100 S Michigan Ave Apt 4B",
            "city": "Chicago",
            "state": "IL",
            "zip": "60605",
            "county": "Cook",
            "fips": "17031",
        },
        "avm_estimate": {
            "estimated_value": 325_000,
            "low_estimate": 305_500,
            "high_estimate": 344_500,
            "confidence_score": 0.85,
            "forecast_standard_deviation": 0.06,
            "valuation_date": "2026-05-20",
            "model_version": "AVM-7.3.1",
        },
        "property_details": {
            "property_type": "Condominium",
            "bedrooms": 2,
            "bathrooms": 2.0,
            "living_area_sqft": 1_150,
            "lot_size_sqft": None,
            "year_built": 2008,
            "stories": None,
            "floor": 4,
            "parking": "1 assigned space — indoor garage",
            "pool": False,
            "condition": "Good",
            "hoa_monthly": 385.00,
            "last_sale_date": "2022-03-15",
            "last_sale_price": 298_000,
        },
        "comparable_sales": [
            {
                "address": "1100 S Michigan Ave Apt 6A, Chicago, IL 60605",
                "sale_date": "2026-04-02",
                "sale_price": 330_000,
                "sqft": 1_180,
                "price_per_sqft": 279.66,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "distance_miles": 0.0,
                "similarity_score": 0.96,
            },
            {
                "address": "1212 S Michigan Ave Unit 510, Chicago, IL 60605",
                "sale_date": "2026-03-18",
                "sale_price": 315_000,
                "sqft": 1_100,
                "price_per_sqft": 286.36,
                "bedrooms": 2,
                "bathrooms": 1.5,
                "distance_miles": 0.1,
                "similarity_score": 0.90,
            },
            {
                "address": "900 S Wabash Ave Unit 302, Chicago, IL 60605",
                "sale_date": "2026-02-05",
                "sale_price": 340_000,
                "sqft": 1_250,
                "price_per_sqft": 272.00,
                "bedrooms": 2,
                "bathrooms": 2.0,
                "distance_miles": 0.3,
                "similarity_score": 0.85,
            },
        ],
        "market_trends": {
            "median_price_zip": 335_000,
            "yoy_appreciation": 0.028,
            "median_dom": 32,
            "inventory_months": 3.8,
            "market_temperature": "Neutral",
        },
        "flood_zone": "X (Minimal Risk)",
        "hazard_flags": [],
        "condo_project": {
            "project_name": "Michigan Avenue Lofts",
            "total_units": 120,
            "owner_occupied_pct": 0.72,
            "hoa_reserve_funded_pct": 0.68,
            "pending_litigation": False,
            "fnma_project_approval": "Full Review — Approved",
        },
    },

    "4200 w pico blvd unit 7, los angeles, ca 90019": {
        "property_address": {
            "street": "4200 W Pico Blvd Unit 7",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90019",
            "county": "Los Angeles",
            "fips": "06037",
        },
        "avm_estimate": {
            "estimated_value": 385_000,
            "low_estimate": 358_050,
            "high_estimate": 411_950,
            "confidence_score": 0.82,
            "forecast_standard_deviation": 0.07,
            "valuation_date": "2026-05-20",
            "model_version": "AVM-7.3.1",
        },
        "property_details": {
            "property_type": "Single Family Residence",
            "bedrooms": 2,
            "bathrooms": 1.5,
            "living_area_sqft": 1_280,
            "lot_size_sqft": 4_800,
            "year_built": 1952,
            "stories": 1,
            "garage": "1-car detached",
            "pool": False,
            "condition": "Fair",
            "last_sale_date": "2015-09-22",
            "last_sale_price": 265_000,
        },
        "comparable_sales": [
            {
                "address": "4150 W Pico Blvd, Los Angeles, CA 90019",
                "sale_date": "2026-04-10",
                "sale_price": 392_000,
                "sqft": 1_350,
                "price_per_sqft": 290.37,
                "bedrooms": 3,
                "bathrooms": 1.5,
                "distance_miles": 0.1,
                "similarity_score": 0.87,
            },
            {
                "address": "1425 S Redondo Blvd, Los Angeles, CA 90019",
                "sale_date": "2026-03-05",
                "sale_price": 370_000,
                "sqft": 1_200,
                "price_per_sqft": 308.33,
                "bedrooms": 2,
                "bathrooms": 1.0,
                "distance_miles": 0.4,
                "similarity_score": 0.83,
            },
            {
                "address": "4320 W Washington Blvd, Los Angeles, CA 90016",
                "sale_date": "2026-01-22",
                "sale_price": 398_000,
                "sqft": 1_400,
                "price_per_sqft": 284.29,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "distance_miles": 0.6,
                "similarity_score": 0.78,
            },
        ],
        "market_trends": {
            "median_price_zip": 395_000,
            "yoy_appreciation": 0.035,
            "median_dom": 24,
            "inventory_months": 2.6,
            "market_temperature": "Warm",
        },
        "flood_zone": "X (Minimal Risk)",
        "hazard_flags": [
            "Earthquake Zone — California Seismic Hazard Zone",
        ],
    },
}


def _maybe_fail(operation: str) -> None:
    if random.random() < ERROR_RATE:
        logger.error("property_valuation.%s — simulated AVM service failure", operation)
        raise ConnectionError(
            f"AVM service unavailable (simulated). Operation: {operation}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_avm_estimate(property_address: str) -> dict[str, Any]:
    """Get an automated valuation model (AVM) estimate for a property.

    Args:
        property_address: Full street address including unit, city, state,
            and ZIP (e.g. ``"742 Evergreen Terrace, San Mateo, CA 94401"``).

    Returns:
        Comprehensive valuation dict with estimated value, confidence
        interval, comparable sales, property details, and market trends.

    Raises:
        ConnectionError: On simulated transient failure.
        KeyError: If no mock property matches the address.
    """
    time.sleep(SIMULATED_LATENCY_S)
    _maybe_fail("get_avm_estimate")

    normalized = property_address.strip().lower()

    # Find best match
    matched_key = None
    for key in _PROPERTIES:
        if key in normalized or normalized in key:
            matched_key = key
            break

    if matched_key is None:
        # Try partial street match
        street_part = normalized.split(",")[0].strip()
        for key in _PROPERTIES:
            if street_part in key:
                matched_key = key
                break

    if matched_key is None:
        raise KeyError(
            f"No AVM data for address '{property_address}'. "
            f"Available addresses: {[_PROPERTIES[k]['property_address']['street'] for k in _PROPERTIES]}"
        )

    prop = _PROPERTIES[matched_key]

    logger.info(
        "property_valuation.get_avm_estimate | address=%s | value=$%s confidence=%.2f",
        property_address,
        f"{prop['avm_estimate']['estimated_value']:,}",
        prop["avm_estimate"]["confidence_score"],
    )

    return {
        "valuation_id": f"AVM-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "source": "CoreLogic AVM (simulated)",
        **prop,
    }
