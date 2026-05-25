# Document Analysis Agent

## Purpose

Ingests uploaded documents (W-2s, pay stubs, bank statements, tax returns, government ID), extracts structured data via OCR, validates consistency across documents, and produces confidence-scored extraction results. This agent transforms unstructured documents into structured, verified data that downstream agents consume.

## Triggers

| Trigger | Source |
|---------|--------|
| Intake Orchestrator routes documents | Routing manifest dispatches this agent in parallel with Credit Bureau and KYC/AML agents |

## Inputs

### Required Documents

| Document | Recency Requirement | Format |
|----------|---------------------|--------|
| W-2 | Last 2 tax years | PDF / image (JPEG, PNG, TIFF) |
| Pay stubs | Last 30 days (most recent pay period) | PDF / image |
| Bank statements | Last 2 months (all accounts) | PDF / image |
| Federal tax returns (1040) | Last 2 tax years | PDF / image |
| Government-issued ID | Current / unexpired | PDF / image |

### Metadata

| Field | Description |
|-------|-------------|
| Case ID | From Intake Orchestrator |
| Borrower name | For cross-referencing against documents |
| Borrower SSN (last 4) | For matching W-2 / tax return SSN |

## Processing Logic

### Step 1: Document Classification

Identify each uploaded file's document type (W-2, pay stub, bank statement, tax return, government ID) using layout analysis and keyword detection. Reject or flag unrecognizable documents.

### Step 2: OCR Extraction

Extract key fields per document type:

**W-2 Extraction**

| Field | Box |
|-------|-----|
| Employer name & EIN | Box c, Box b |
| Employee SSN (last 4) | Box a |
| Wages, tips, other compensation | Box 1 |
| Federal income tax withheld | Box 2 |
| Social Security wages | Box 3 |
| Medicare wages | Box 5 |
| Tax year | Header |

**Pay Stub Extraction**

| Field | Source |
|-------|--------|
| Employer name | Header |
| Employee name | Header |
| Pay period dates | Header |
| Gross pay (current period) | Earnings section |
| YTD gross earnings | Earnings section |
| Deductions breakdown | Deductions section |
| Net pay | Summary |

**Bank Statement Extraction**

| Field | Source |
|-------|--------|
| Account holder name | Header |
| Account number (last 4) | Header |
| Statement period | Header |
| Beginning balance | Summary |
| Ending balance | Summary |
| Total deposits | Summary |
| Total withdrawals | Summary |
| Average daily balance | Calculated |
| Large deposits (> $5,000) | Transaction detail |

**Tax Return (1040) Extraction**

| Field | Line |
|-------|------|
| Filing status | Top of form |
| SSN (last 4) | Header |
| Total income | Line 9 |
| Adjusted gross income (AGI) | Line 11 |
| Taxable income | Line 15 |
| Self-employment income (Schedule SE) | If applicable |
| Rental income (Schedule E) | If applicable |

**Government ID Extraction**

| Field | Source |
|-------|--------|
| Full name | ID face |
| Date of birth | ID face |
| ID number (masked) | ID face |
| Expiration date | ID face |
| Photo presence | ID face |

### Step 3: Confidence Scoring

Assign a confidence score (0–100%) to each extracted field based on OCR clarity, character recognition certainty, and layout match.

### Step 4: Cross-Reference Validation

| Cross-Reference Check | Sources | Tolerance |
|------------------------|---------|-----------|
| Employer name consistency | W-2 employer vs. pay stub employer | Exact match (allow minor formatting differences) |
| Wage consistency | W-2 Box 1 wages vs. tax return AGI | Within 10% (AGI may include other income) |
| Income consistency | Pay stub YTD annualized vs. W-2 wages | Within 10% |
| Name consistency | All documents vs. application name | Exact match (flag maiden name / name changes) |
| SSN consistency | W-2 last 4 vs. tax return last 4 vs. application | Exact match |
| Bank statement deposits vs. income | Monthly deposits vs. monthly gross pay | Flag if deposits significantly exceed or fall short of stated income |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Structured extraction object | Object | Per-document extraction with all fields and per-field confidence scores |
| Cross-reference discrepancy report | Array | List of mismatches with severity (INFO / WARNING / CRITICAL) |
| Overall document package confidence score | Number (0–100) | Weighted average across all documents and fields |
| Document inventory status | Object | Which required documents are present, missing, or illegible |
| Large deposit flags | Array | Bank statement deposits > $5,000 requiring sourcing explanation |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| Any field confidence < 85% | Flag specific field for manual review by document processor |
| Cross-reference discrepancy > 10% | Flag discrepancy with details for underwriter review |
| Suspected altered document (metadata anomalies, font inconsistencies, pixel-level manipulation indicators) | **HALT processing for that document**. Escalate to fraud team immediately. Do not include extracted data from suspect document in outputs. |
| Unreadable / corrupt file | Return error for specific file; request re-upload from borrower |
| Missing required document | Include in document inventory status; Intake Orchestrator will request from borrower |
| Password-protected PDF | Return error; request unprotected version |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Timeout | 180 seconds (documents can be large, multi-page) |
| Retry policy | If OCR service times out, retry once after 5 seconds. If second attempt fails, flag for manual document processing. |
| Per-document timeout | 45 seconds per document |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Document OCR Service | Optical character recognition and field extraction | REST API |

## Regulatory Requirements

- All uploaded documents must be stored encrypted at rest (AES-256).
- Document images must be retained for the life of the loan + 7 years per record retention requirements.
- PII extracted from documents must be handled per GLBA (Gramm-Leach-Bliley Act) safeguards.
- Fraud detection flags must be logged with full detail for potential SAR (Suspicious Activity Report) filing.
- Document processing audit trail must capture: timestamp, document type, extraction results, confidence scores, and any flags raised.
