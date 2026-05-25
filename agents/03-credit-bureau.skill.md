# Credit Bureau Agent

## Purpose

Pulls a tri-merge credit report from Equifax, Experian, and TransUnion via a legacy SOAP-to-REST adapter. Parses the XML response into structured JSON, extracts FICO scores, tradelines, public records, and inquiries, and delivers a normalized credit summary for downstream underwriting agents.

## Triggers

| Trigger | Source |
|---------|--------|
| Intake Orchestrator initiates | Runs in **parallel** with Document Analysis (02) and KYC/AML Screening (04) |

## Inputs

| Field | Required | Format | Notes |
|-------|----------|--------|-------|
| Borrower SSN (last 4) | Yes | XXXX | For request correlation |
| Borrower SSN (full, encrypted) | Yes | Encrypted payload | Decrypted only at bureau submission |
| Full legal name | Yes | First, Middle, Last, Suffix | Must match credit file |
| Date of birth | Yes | YYYY-MM-DD | Bureau matching field |
| Current address | Yes | Street, City, State, ZIP | Bureau matching field |

## Processing Logic

### Step 1: Prepare Credit Inquiry Request

- Construct SOAP XML request per tri-merge service specification.
- Include permissible purpose code (mortgage pre-qualification / pre-approval).
- Attach encrypted SSN — decryption occurs within the secure adapter boundary only.
- Include borrower authorization reference ID (proof of consent).

### Step 2: Submit to Tri-Merge Service

- Submit single request that fans out to all three bureaus.
- Each bureau response is independent; adapter aggregates responses.

### Step 3: Parse XML Response

Transform raw XML into structured JSON:

**FICO Scores**

| Bureau | Score Field | Range |
|--------|-------------|-------|
| Equifax | FICO Score 5 (Beacon) | 300–850 |
| Experian | FICO Score 2 (Experian/Fair Isaac) | 300–850 |
| TransUnion | FICO Score 4 (EMPIRICA) | 300–850 |
| Middle score | Calculated | Median of available scores |

**Tradelines (per account)**

| Field | Description |
|-------|-------------|
| Creditor name | Name of lender |
| Account type | Revolving / Installment / Mortgage / Other |
| Date opened | Account origination date |
| Credit limit / original amount | Maximum credit or original loan amount |
| Current balance | Outstanding balance |
| Monthly payment | Minimum or scheduled payment |
| Payment history | 24-month payment pattern (current, 30/60/90/120+ days late) |
| Account status | Open / Closed / Paid / Collection |

**Public Records**

| Field | Description |
|-------|-------------|
| Record type | Bankruptcy (Ch 7/13), Tax Lien, Civil Judgment |
| Date filed | Filing date |
| Date resolved | Discharge/release date (if applicable) |
| Amount | Dollar amount (if applicable) |
| Status | Active / Discharged / Released |

**Inquiries**

| Field | Description |
|-------|-------------|
| Creditor name | Who pulled the report |
| Date of inquiry | When pulled |
| Inquiry type | Hard / Soft |

### Step 4: Compute Credit Summary

| Metric | Calculation |
|--------|-------------|
| Middle FICO | Median of available bureau scores |
| Total revolving debt | Sum of all revolving balances |
| Total installment debt | Sum of all installment balances |
| Total monthly obligations | Sum of all minimum monthly payments |
| Derogatory count | Count of 60+ day lates in last 24 months, collections, charge-offs |
| Bankruptcy flag | Any active or discharged within 7 years (Ch 7) or 3 years (Ch 13) |
| Open tradeline count | Number of currently open accounts |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Credit summary | Object | Middle FICO, total debt, monthly obligations, derogatory count, bankruptcy flag |
| Tradeline array | Array | All tradelines with full detail |
| Public records array | Array | Bankruptcies, liens, judgments |
| Inquiry count (last 12 months) | Number | Hard inquiries in prior 12 months |
| Bureau response status | Object | Per-bureau status (SUCCESS / FAILURE / TIMEOUT) |
| Raw response archive reference | String | Pointer to encrypted stored raw response for audit |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| Single bureau timeout (> 30s) | Retry that bureau 2x with exponential backoff (2s delay, then 8s delay). |
| Single bureau fails after retries | Proceed with 2 bureaus. Flag in output that one bureau is missing. Middle score calculation adjusts (use average of 2, or the single score if only 1). |
| 2+ bureaus fail after retries | **Do not proceed with automated underwriting.** Queue case for manual credit pull by operations team. Notify Loan Officer of delay. |
| SSN mismatch / no file found | Return NO_HIT status. Flag for LO review — borrower may have a thin file or identity issue. |
| Credit freeze detected | Return FROZEN status with bureau name. Notify borrower they must temporarily lift freeze. |
| All attempts logged | Every request, response, retry, and failure is logged with timestamps for FCRA compliance. |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Total agent timeout | 60 seconds |
| Per-bureau timeout | 30 seconds |
| Retry attempts per bureau | 2 |
| Backoff strategy | Exponential: 2 seconds after first failure, 8 seconds after second failure |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Credit Bureau Legacy API | Tri-merge credit report pull | SOAP/XML via REST adapter, mTLS |

## Regulatory Requirements

### FCRA (Fair Credit Reporting Act) Compliance

- **Permissible purpose**: Every credit pull must have documented permissible purpose (mortgage application with borrower authorization).
- **Borrower authorization**: Signed credit authorization must be on file before this agent executes. The agent verifies authorization reference ID exists in the case record.
- **Hard inquiry**: This pull is logged as a hard inquiry on the borrower's credit report. Borrower must be informed.
- **Adverse action**: If credit data contributes to a denial, adverse action notice must cite specific credit factors (handled by Compliance Agent 08).
- **Dispute rights**: Borrower has right to dispute inaccurate credit information. Pre-approval denial letter must include bureau contact information.

### Data Security

- Full SSN is encrypted end-to-end; decrypted only within the secure adapter boundary.
- Raw credit report XML is stored encrypted with restricted access (underwriter + compliance only).
- Credit data must not be logged in plaintext in application logs.
- Retention: Raw credit data retained for life of loan + 7 years, or 25 months if application is denied/withdrawn.
