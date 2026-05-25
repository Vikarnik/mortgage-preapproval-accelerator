# Intake Orchestrator

## Purpose

Receives mortgage application (1003 form data), validates completeness, creates a case record, and routes to downstream agents. This is the entry point for the entire pre-approval pipeline — no other agent runs until Intake Orchestrator has validated and dispatched the application.

## Triggers

| Trigger | Source |
|---------|--------|
| New application submission | Borrower portal, LO-assisted entry, or API submission |

## Inputs

### Borrower Personal Information

| Field | Required | Format |
|-------|----------|--------|
| Full legal name | Yes | First, Middle, Last, Suffix |
| SSN | Yes | XXX-XX-XXXX (encrypted at rest) |
| Date of birth | Yes | YYYY-MM-DD |
| Current address | Yes | Street, City, State, ZIP |
| Prior address (if < 2 years at current) | Conditional | Street, City, State, ZIP |
| Phone number | Yes | 10-digit |
| Email | Yes | Valid email format |
| Citizenship/residency status | Yes | US Citizen / Permanent Resident / Non-Permanent Resident |

### Property Information

| Field | Required | Format |
|-------|----------|--------|
| Property address | Yes | Street, City, State, ZIP |
| Property type | Yes | Single Family / Condo / Townhouse / Multi-Family (2-4 units) |
| Estimated value | Yes | USD, whole dollars |
| Purchase price | Yes (purchase) | USD, whole dollars |
| Occupancy type | Yes | Primary Residence / Second Home / Investment |

### Loan Request

| Field | Required | Format |
|-------|----------|--------|
| Loan amount | Yes | USD, whole dollars |
| Loan term | Yes | 15 / 20 / 30 years |
| Loan type | Yes | Conventional / FHA / VA / USDA |
| Purpose | Yes | Purchase / Refinance / Cash-Out Refinance |

### Uploaded Documents

| Field | Required |
|-------|----------|
| Documents list | Yes — at minimum government ID; remaining docs may follow |

## Processing Logic

1. **Field completeness check** — Verify all required fields are populated. For conditional fields (e.g., prior address), evaluate whether the condition is met and enforce accordingly.
2. **Format validation** — SSN matches `\d{3}-\d{2}-\d{4}` pattern. Dates are valid calendar dates. Email is well-formed. ZIP codes are 5-digit or ZIP+4.
3. **Business rule validation**
   - Loan amount must be between **$50,000 and $2,000,000**.
   - Property state must be within the bank's lending footprint (configurable state list).
   - LTV sanity check: loan amount should not exceed estimated property value (no negative equity at application).
   - Borrower age derived from DOB must be ≥ 18.
4. **Existing customer lookup** — Query Core Banking API by SSN to determine if borrower is an existing customer. If yes, attach customer ID to case record.
5. **Case record creation** — Generate a unique Case ID (format: `MPA-YYYYMMDD-XXXXXX`), timestamp the application, set initial status to `INTAKE_COMPLETE` or `INTAKE_INCOMPLETE`.
6. **Routing manifest generation** — Determine which downstream agents to invoke and in what order:
   - **Parallel**: Document Analysis Agent (02), Credit Bureau Agent (03), KYC/AML Screening Agent (04)
   - **Sequential after parallel completion**: Income & Employment Verification Agent (05) → AUS Submission Agent (06) → Pre-Approval Decision Agent (07)
   - **Post-human-decision**: Compliance & Audit Agent (08)

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Case ID | String | Unique identifier for this application |
| Validation status | Enum | `COMPLETE` or `INCOMPLETE` |
| Missing items list | Array | Specific fields or documents still required |
| Routing manifest | Object | Ordered list of agents to invoke with dependency graph |
| Existing customer flag | Boolean | Whether borrower was found in Core Banking |
| Timestamp | ISO 8601 | Application receipt time |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| Required fields missing | Return specific missing field list to borrower portal. Do **not** proceed until minimum required fields are present. |
| SSN format invalid | Reject with clear error message; do not store malformed SSN. |
| Loan amount outside $50K–$2M range | Reject with explanation of bank limits. |
| Property state outside lending footprint | Reject with message listing states where bank operates. |
| Core Banking API unavailable | Proceed without existing customer lookup; flag case for manual customer match later. |
| Duplicate application (same SSN + property within 30 days) | Flag as potential duplicate; present to LO for confirmation before creating new case. |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Timeout | 120 seconds |
| Retry policy | Not applicable — validation is deterministic. If Core Banking lookup times out, skip and flag. |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Core Banking API | Existing customer lookup by SSN | REST / mTLS |

## Regulatory Requirements

- SSN must be encrypted at rest and in transit (AES-256 / TLS 1.2+).
- Application receipt timestamp is legally significant — it starts the TRID clock (Loan Estimate due within 3 business days).
- All validation failures and routing decisions must be logged to the audit trail.
- PII fields must not appear in application logs; use masked/tokenized references.
