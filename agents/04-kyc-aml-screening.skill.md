# KYC/AML Screening Agent

## Purpose

Performs identity verification and sanctions/watchlist screening per BSA/AML (Bank Secrecy Act / Anti-Money Laundering) requirements. Verifies borrower identity through the Customer Identification Program (CIP) and screens against OFAC, FinCEN, PEP, and adverse media databases.

## Triggers

| Trigger | Source |
|---------|--------|
| After Intake Orchestrator validates identity fields | Runs in **parallel** with Document Analysis (02) and Credit Bureau (03) |

## Inputs

| Field | Required | Format | Notes |
|-------|----------|--------|-------|
| Full legal name | Yes | First, Middle, Last, Suffix | As entered on application |
| Date of birth | Yes | YYYY-MM-DD | |
| SSN | Yes | Encrypted | For CIP verification |
| Current address | Yes | Street, City, State, ZIP | |
| Prior addresses | If available | Array of addresses | Strengthens identity verification |
| Citizenship / residency status | Yes | US Citizen / Permanent Resident / Non-Permanent Resident | |
| Government ID image | Yes | PDF / image | Driver's license, passport, or state ID |
| Country of citizenship | Yes | ISO 3166-1 alpha-2 | |

## Processing Logic

### Step 1: OFAC SDN List Screening

- Screen borrower full name (including variations, transliterations, and aliases) against the OFAC Specially Designated Nationals and Blocked Persons List.
- Apply fuzzy matching with configurable threshold (default: 80% match score).
- Screen against all OFAC programs (SDN, SSI, FSE, etc.).
- If co-borrower exists, screen co-borrower independently.

### Step 2: FinCEN 314(a) Check

- Submit borrower information to FinCEN 314(a) matching system.
- Check against subjects of ongoing law enforcement investigations.
- Response is binary: match or no match.

### Step 3: PEP (Politically Exposed Persons) Screening

- Screen borrower against domestic and international PEP databases.
- Include family members and close associates if data is available.
- PEP categories: current/former government officials, senior political figures, military leaders, state-owned enterprise executives.

### Step 4: Adverse Media Screening

- Search structured adverse media databases for borrower name + identifying details.
- Categories: financial crime, fraud, sanctions evasion, money laundering, terrorism financing, tax evasion.
- Apply relevance scoring to filter false positives (common names).

### Step 5: ID Document Authentication

- Analyze government ID image for signs of tampering or forgery:
  - Font consistency and alignment
  - Microprint and security feature verification
  - Photo quality and edge analysis
  - Barcode/MRZ data cross-reference against printed data
- Verify ID is not expired.
- Cross-reference ID name and DOB against application data.

### Step 6: CIP (Customer Identification Program) Verification

- Verify identity through independent data sources:
  - Name + SSN + DOB match against national identity databases
  - Address verification through postal and public records databases
  - Phone number verification (if available)
- Produce CIP verification score based on number of corroborating data points.

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Screening result | Enum | `CLEAR` / `HIT` / `POTENTIAL_MATCH` |
| Hit details | Array | If not CLEAR: list name matched, match score, matched fields, program/list name |
| CIP verification status | Enum | `VERIFIED` / `PARTIALLY_VERIFIED` / `UNABLE_TO_VERIFY` |
| CIP verification details | Object | Which data points matched, which did not |
| ID authentication result | Enum | `AUTHENTIC` / `SUSPECT` / `UNABLE_TO_DETERMINE` |
| Risk score | Enum | `LOW` / `MEDIUM` / `HIGH` |
| Risk score factors | Array | Reasons contributing to risk classification |
| Screening timestamp | ISO 8601 | When screening was performed (audit requirement) |

### Risk Score Matrix

| Condition | Risk Level |
|-----------|------------|
| All screenings clear, CIP verified, ID authentic | LOW |
| Minor adverse media, PEP family member, partial CIP verification | MEDIUM |
| OFAC potential match, direct PEP, multiple adverse media hits, ID suspect | HIGH |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| **Any OFAC hit (match score > 80%)** | **HALT the entire pipeline immediately.** Escalate to BSA Officer. Case status set to `OFAC_HOLD`. No further processing until BSA Officer reviews and documents disposition. |
| PEP match (direct) | Flag for Enhanced Due Diligence (EDD). Pipeline may continue in `EDD_HOLD` state — downstream agents process but final decision is held for compliance review. |
| PEP match (family/associate) | Flag for review. Pipeline continues normally but flag is carried through to Decision Agent. |
| Multiple adverse media hits | Flag for compliance officer review. Pipeline continues in `COMPLIANCE_REVIEW` state. |
| ID authentication returns SUSPECT | Halt document processing for that ID. Request alternative ID from borrower. Escalate to fraud team if pattern indicates forgery. |
| CIP unable to verify | Flag for enhanced verification. May require borrower to present ID in person at branch. |
| OFAC/FinCEN service unavailable | **Do not proceed.** Retry 3x with 10-second intervals. If still unavailable, queue case for manual screening. Compliance must screen before any decision is made. |

### CRITICAL CONSTRAINT

**This agent CANNOT auto-clear OFAC hits.** Any OFAC match or potential match — regardless of match score — requires human BSA Officer review and documented disposition. The BSA Officer must record:
- Whether the match is a true positive or false positive
- Basis for determination
- Supporting documentation
- Date and officer identification

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Total agent timeout | 90 seconds |
| OFAC/sanctions screening timeout | 30 seconds |
| ID verification timeout | 30 seconds |
| Retry policy | 3 attempts with 10-second intervals for screening service failures |
| Retry policy (ID auth) | 2 attempts; if second fails, flag for manual review |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| OFAC/Sanctions Screening API | SDN list, consolidated sanctions screening | REST API, encrypted |
| FinCEN 314(a) Service | Law enforcement investigation matching | Secure batch submission |
| PEP Database | Politically exposed persons screening | REST API |
| Adverse Media Database | Negative news screening | REST API |
| ID Verification Service | Document authentication and CIP verification | REST API, image upload |

## Regulatory Requirements

### BSA/AML (Bank Secrecy Act / Anti-Money Laundering)

- OFAC screening is **mandatory** before any financial transaction or relationship is established. No pre-approval can be issued without completed OFAC screening.
- CIP verification is required under USA PATRIOT Act Section 326 — the bank must verify the identity of any person seeking to open an account or conduct a financial transaction.
- All screening results (including clears) must be documented and retained for 5 years after the account relationship ends.

### SAR Filing Obligations

- If screening reveals suspicious activity indicators (identity fraud, structuring, sanctions evasion), the BSA Officer must evaluate whether a SAR (Suspicious Activity Report) filing is required.
- SAR must be filed within 30 days of initial detection if warranted.
- The borrower must **not** be notified of SAR filing (tipping off is prohibited under 31 USC 5318(g)(2)).

### Record Retention

- All screening results, hit details, disposition records, and supporting documentation: **5 years minimum** after account closure or application denial.
- OFAC screening records: retain indefinitely if a true hit was identified.

### Fair Lending

- Screening criteria must be applied uniformly to all applicants regardless of protected class characteristics.
- PEP and adverse media screening must use objective, documented criteria to avoid discriminatory application.
