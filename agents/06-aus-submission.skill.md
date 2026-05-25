# AUS Submission Agent

## Purpose

Prepares and submits the complete application data package to Automated Underwriting Systems — Fannie Mae Desktop Underwriter (DU) and/or Freddie Mac Loan Product Advisor (LPA). Translates all upstream agent outputs into MISMO XML format, submits for automated risk assessment, and parses the AUS findings into structured, actionable results.

## Triggers

| Trigger | Source |
|---------|--------|
| After Income & Employment Verification (05) completes | Sequential — requires income verification results plus all prior agent outputs |

## Inputs

### From All Upstream Agents

| Source Agent | Data |
|--------------|------|
| Intake Orchestrator (01) | Complete 1003 application data, property info, loan terms |
| Document Analysis (02) | Structured document extractions, confidence scores |
| Credit Bureau (03) | Credit report data, FICO scores, tradelines, monthly obligations |
| KYC/AML Screening (04) | Screening status (must be CLEAR or EDD_HOLD — OFAC_HOLD blocks this agent) |
| Income Verification (05) | Qualifying income, DTI ratios, employment verification status |

### Additional Inputs

| Field | Source |
|-------|--------|
| Loan program parameters | Product/pricing engine or LO selection |
| Current interest rate | Rate sheet service |
| LTV / CLTV ratios | Calculated from loan amount and property value |
| Mortgage insurance details | If applicable based on LTV |

## Processing Logic

### Step 1: Pre-Submission Validation

Before submitting to AUS, verify:

| Check | Requirement |
|-------|-------------|
| All required data fields populated | No null required fields in MISMO mapping |
| KYC/AML screening complete | Status must not be `OFAC_HOLD` |
| Credit report available | At least 2 bureau scores present |
| Income verification complete | Qualifying income calculated |
| Property data complete | Address, type, value, occupancy |

If any pre-submission check fails, return error with specific missing items — do not submit incomplete data to AUS.

### Step 2: MISMO XML Mapping

Map all application data to **MISMO v3.4** XML format:

| MISMO Section | Source Data |
|---------------|-------------|
| `ABOUT_VERSIONS` | MISMO version, data format identifiers |
| `DEAL_SETS/DEAL_SET/DEALS/DEAL` | Container for all deal data |
| `PARTIES` | Borrower demographics, employer, contact info |
| `COLLATERALS` | Property address, type, value, legal description |
| `LOANS` | Loan amount, term, type, purpose, rate, LTV |
| `SERVICES/SERVICE/CREDIT` | Tri-merge credit data, scores, tradelines |
| `SERVICES/SERVICE/VERIFICATION_OF_EMPLOYMENT` | VOIE results |
| `LIABILITIES` | Monthly obligations from credit report |
| `ASSETS` | Bank account balances from statements |
| `QUALIFYING_THE_BORROWER` | DTI ratios, qualifying income |

### Step 3: Submit to Desktop Underwriter (DU) — Primary

- Submit MISMO XML package to Fannie Mae DU endpoint.
- Include casefile ID for tracking.
- Wait for synchronous response (typical response time: 15–45 seconds).

### Step 4: Conditional LPA Submission

If DU returns **Refer** or **Refer with Caution**:

- Also submit to Freddie Mac LPA for dual-AUS evaluation.
- Some loans eligible under LPA that are not eligible under DU (different risk models).
- Both results are presented to underwriter for decision.

### Step 5: Parse AUS Response

**DU Recommendation Codes**

| Code | Meaning | Next Step |
|------|---------|-----------|
| Approve/Eligible | Loan meets DU standards | Proceed to Decision Agent |
| Approve/Ineligible | Meets credit standards but fails eligibility (product/geography) | Review eligibility issue; may need program change |
| Refer | Does not meet DU standards for automated approval | Package for manual underwriting |
| Refer with Caution | Significant risk factors identified | Package for senior underwriter review |
| Out of Scope | Loan characteristics outside DU parameters | Manual underwriting required |
| Error | Submission or data issue | Diagnose and resubmit |

**LPA Recommendation Codes**

| Code | Meaning | Next Step |
|------|---------|-----------|
| Accept | Loan meets LPA standards | Proceed to Decision Agent |
| Caution | Risk factors require attention | Manual review required |
| Refer | Does not meet LPA standards | Manual underwriting required |

### Step 6: Extract Conditions and Findings

Parse AUS response for:

| Element | Description |
|---------|-------------|
| Conditions (prior-to-closing) | Items borrower must provide before loan can close |
| Conditions (prior-to-funding) | Items required before funds are disbursed |
| Findings messages | Specific observations or warnings from AUS |
| Risk factors | Key risk drivers identified by the model |
| Appraisal waiver | Whether property qualifies for appraisal waiver (DU Property Inspection Waiver / LPA ACE) |
| Documentation level | Full doc / reduced doc based on AUS risk assessment |

### Step 7: Translate AUS Codes

Convert AUS-specific codes and abbreviations into human-readable conditions list for the underwriter and borrower:

| AUS Code Example | Human-Readable Translation |
|------------------|---------------------------|
| `VOE_REQUIRED` | Verify employment — provide current employer contact or verbal VOE |
| `ASSET_DOC_60` | Provide 60 days of bank/asset statements |
| `TITLE_COMMIT` | Title commitment required prior to closing |
| `APPRAISAL_REQ` | Full appraisal required (no waiver eligible) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| AUS recommendation | Enum | `APPROVE_ELIGIBLE` / `APPROVE_INELIGIBLE` / `REFER` / `REFER_WITH_CAUTION` / `OUT_OF_SCOPE` / `ERROR` |
| AUS engine used | Enum | `DU` / `LPA` / `DUAL_AUS` |
| Conditions list | Array | Itemized conditions with category (prior-to-closing, prior-to-funding) |
| Human-readable conditions | Array | Translated conditions for underwriter/borrower |
| Risk assessment summary | Object | Key risk factors identified |
| Findings messages | Array | All AUS findings/warnings |
| Appraisal waiver status | Enum | `WAIVER_OFFERED` / `APPRAISAL_REQUIRED` |
| Documentation level | Enum | `FULL` / `REDUCED` |
| DU casefile ID | String | For reference and resubmission |
| LPA casefile ID | String | If dual-AUS was performed |
| Raw AUS response reference | String | Pointer to stored raw response for audit |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| DU returns Approve/Eligible | Proceed to Decision Agent (07) with full results |
| DU returns Refer | Submit to LPA (dual-AUS). Package both results for manual underwriting with full condition list. |
| DU returns Refer with Caution | Submit to LPA (dual-AUS). Package for **senior** underwriter review with risk factor analysis. |
| DU returns Error | Diagnose error code. If data mapping issue, fix and retry once. If system error, retry once after 15 seconds. If persistent, flag for manual AUS submission by operations. |
| DU returns Out of Scope | Flag loan as requiring manual underwriting. Notify LO of manual process timeline. |
| DU service unavailable | Retry 2x with 15-second intervals. If still unavailable, queue for submission when service recovers. Notify LO of delay. |
| MISMO mapping validation failure | Log specific mapping errors. Attempt to resolve programmatically. If unresolvable, flag for manual data correction. |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Total agent timeout | 90 seconds |
| DU submission timeout | 60 seconds |
| LPA submission timeout | 60 seconds (if dual-AUS) |
| Retry policy | 1 retry for errors, 2 retries for service unavailability (15-second intervals) |
| Total timeout with dual-AUS | May extend to 150 seconds — this is acceptable for dual submission |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Fannie Mae Desktop Underwriter (DU) | Primary AUS submission | MISMO XML over secure API |
| Freddie Mac Loan Product Advisor (LPA) | Secondary AUS submission (dual-AUS) | MISMO XML over secure API |
| Rate Sheet Service | Current rates for submission | Internal API |
| Product/Pricing Engine | Loan program eligibility | Internal API |

## Regulatory Requirements

- AUS submission and results are part of the permanent loan file and must be retained.
- AUS findings do not constitute a final lending decision — they are a tool to assist human underwriters. The lender retains responsibility for the final credit decision.
- If the loan is manually underwritten (AUS Refer or Out of Scope), the manual underwriting process must be fully documented.
- GSE (Government-Sponsored Enterprise) eligibility requirements: loans submitted to DU/LPA must meet Fannie Mae/Freddie Mac purchase eligibility criteria for the lender to sell the loan on the secondary market.
- MISMO data standards compliance is required for GSE delivery.
