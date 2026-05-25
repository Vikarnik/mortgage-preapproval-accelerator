# Compliance & Audit Agent

## Purpose

Performs final compliance checks, generates required regulatory disclosures, produces the complete audit trail, and — only after human underwriter approval — generates the pre-approval letter. This agent is the final gate ensuring that every regulatory obligation is met before any commitment is issued to the borrower.

## Triggers

| Trigger | Source |
|---------|--------|
| After human underwriter approves, denies, or conditions the application | Decision recorded in Underwriter Review UI following Pre-Approval Decision Agent (07) recommendation |

## Inputs

| Source | Data |
|--------|------|
| Human reviewer's decision | `APPROVED` / `APPROVED_WITH_CONDITIONS` / `DENIED` / `COUNTER_OFFER` with underwriter notes |
| Decision recommendation packet | Full output from Pre-Approval Decision Agent (07) |
| All upstream agent data | Complete case file from agents 01–06 |
| Bank's current rate sheet | For Loan Estimate fee and rate disclosure |
| Fee schedule | Origination fees, third-party fees, title/escrow estimates |
| Underwriter identity | Name, NMLS ID, timestamp of decision |

## Processing Logic

### Step 1: TRID Timing Compliance Validation

| Check | Rule |
|-------|------|
| Application receipt date | Captured by Intake Orchestrator (01) |
| Current date | System timestamp |
| Business days elapsed | Calculate business days between receipt and today |
| **Compliance status** | **Loan Estimate must be delivered within 3 business days of application receipt** |

If 3 business days have elapsed or will elapse before delivery is possible, generate a **TRID timing violation alert** to compliance officer and underwriting manager. This is a regulatory breach.

### Step 2: Generate Loan Estimate (if APPROVED or APPROVED_WITH_CONDITIONS)

Produce a TRID-compliant Loan Estimate document containing:

| Section | Content |
|---------|---------|
| Loan terms | Loan amount, interest rate (from rate sheet), monthly P&I, prepayment penalty (Y/N), balloon payment (Y/N) |
| Projected payments | P&I, mortgage insurance, estimated escrow (taxes + insurance), total monthly payment |
| Costs at closing | Estimated closing costs, estimated cash to close |
| Loan costs | Origination charges (itemized), services borrower cannot shop for, services borrower can shop for |
| Other costs | Taxes and government fees, prepaids, initial escrow payment at closing |
| Comparisons | APR, total interest percentage (TIP), total of payments over loan life |
| Other considerations | Appraisal requirement, assumption policy, homeowner's insurance requirement, late payment policy, servicing disclosure |

### Step 3: Generate Adverse Action Notice (if DENIED)

Per ECOA / Regulation B, produce adverse action notice containing:

| Element | Requirement |
|---------|-------------|
| Denial date | Date of underwriter's decision |
| Specific reason codes | From Decision Agent adverse action codes — must list specific reasons (up to 4 primary reasons) |
| Credit score disclosure | Middle FICO used, score range, key factors affecting score, bureau source |
| Applicant rights | Right to request specific reasons (if not provided), right to obtain free credit report within 60 days |
| Bureau contact information | Name, address, phone for each bureau that provided data |
| ECOA notice | Statement of anti-discrimination rights |
| Agency contact | CFPB or appropriate regulator contact information |

### Step 4: Generate Pre-Approval Letter (if APPROVED)

| Element | Content |
|---------|---------|
| Borrower name(s) | Full legal name |
| Pre-approved loan amount | As approved by underwriter (may differ from request) |
| Loan type and term | Conventional/FHA/VA, 15/20/30 year |
| Interest rate range | Current rate +/- spread, or "rate not locked" language |
| Conditions | Summary of conditions that must be met |
| Expiration date | 60–90 days from issuance (configurable, default 90 days) |
| Property specification | If specific property identified; otherwise "subject to acceptable property" |
| Standard caveats | Subject to appraisal, title search, final underwriting, no material change in financial condition |
| Lender information | Bank name, NMLS ID, Loan Officer name and NMLS ID |
| Underwriter approval reference | Underwriter name and decision timestamp |

### Step 5: Compile HMDA Data Fields

Collect and format data required for Home Mortgage Disclosure Act (HMDA) Loan Application Register (LAR) reporting:

| HMDA Field | Source |
|------------|--------|
| Application date | Intake Orchestrator |
| Loan type | Application data |
| Loan purpose | Application data |
| Loan amount | Approved amount |
| Action taken | Approved / Denied / Withdrawn / Incomplete |
| Action taken date | Underwriter decision date |
| Property location (census tract) | Property address geocoded |
| Applicant demographics | Race, ethnicity, sex, age (as reported by borrower per HMDA requirements) |
| Income | Gross annual income (in thousands) |
| Rate spread | If applicable |
| HOEPA status | High-cost mortgage determination |
| Lien status | First lien / subordinate |
| Credit score model | FICO version used |
| DTI ratio | Back-end DTI |
| AUS result | DU/LPA recommendation |

### Step 6: Produce Complete Audit Trail

Generate a comprehensive audit log package:

| Section | Content |
|---------|---------|
| Application timeline | Chronological list of all events from receipt to decision |
| Agent execution log | Each agent's start/stop time, inputs, outputs, flags raised |
| Data sources consulted | All external systems queried with timestamps |
| Discrepancy log | All discrepancies found and their resolution |
| Escalation log | Any escalations triggered, to whom, resolution |
| Decision documentation | Underwriter's decision, rationale, conditions, any deviations from recommendation |
| Compliance checklist | Each regulatory requirement verified with pass/fail status |

### Step 7: Validate Fair Lending Data Capture

| Check | Validation |
|-------|------------|
| HMDA demographic data | Collected per regulatory requirements (self-reported by borrower) |
| Pricing consistency | Rate and fees are consistent with rate sheet for borrower's risk profile |
| Denial reason consistency | If denied, reasons are objective and consistently applied |
| Comparable file check | Flag if this file's outcome differs significantly from comparable files (similar FICO, DTI, LTV) |

## Outputs

| Output | Type | Condition | Description |
|--------|------|-----------|-------------|
| Loan Estimate | PDF | If approved | TRID-compliant disclosure document |
| Adverse action notice | PDF | If denied | ECOA/Reg B compliant denial notice |
| Pre-approval letter | PDF | If approved | Borrower-facing commitment letter with terms and expiration |
| HMDA LAR data record | Structured data | Always | Record for HMDA reporting submission |
| Complete audit trail | PDF + structured data | Always | Full pipeline audit log |
| Compliance checklist | Object | Always | All regulatory items verified with status |
| TRID timing status | Enum | Always | `COMPLIANT` / `AT_RISK` / `VIOLATION` |
| Document delivery confirmation | Object | Always | Timestamp and method of delivery for each disclosure |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| TRID 3-day deadline at risk (< 4 hours remaining) | **Urgent alert** to compliance officer and underwriting manager. Prioritize Loan Estimate generation and delivery. |
| TRID 3-day deadline breached | **Compliance violation logged.** Generate incident report. Loan Estimate still generated and delivered with documentation of delay. |
| Rate sheet unavailable | Use most recent cached rate sheet with notation. Flag for compliance review to confirm rates are current. |
| Document generation service failure | Retry 2x. If persistent, generate documents via backup template system. Do not delay disclosure delivery. |
| HMDA data incomplete | Flag missing fields. Compliance must complete HMDA data before quarter-end LAR submission. |
| Adverse action reasons insufficient | If underwriter's denial lacks specific reasons, return to underwriter for clarification. Do not generate adverse action notice with vague reasons. |
| Fair lending flag triggered | Alert compliance officer. Comparable file analysis results included in audit trail. Does not block document generation but requires compliance review within 5 business days. |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Total agent timeout | 60 seconds |
| Document generation timeout | 30 seconds per document |
| Retry policy | 2 retries for document generation failures with 5-second delay |
| Rate sheet lookup timeout | 10 seconds; fall back to cached if unavailable |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Rate Sheet Service | Current interest rates and fee schedules | Internal API |
| Document Generation Service | PDF generation for Loan Estimate, adverse action notice, pre-approval letter | Internal API / template engine |
| HMDA Reporting System | LAR data submission | Internal database / batch submission |
| Document Delivery Service | eDelivery or mail delivery of disclosures | Email / postal / eSign platform |
| Audit Log Database | Permanent storage of audit trail | Internal database, encrypted |

## Regulatory Requirements

### TRID (TILA-RESPA Integrated Disclosure)

- **Loan Estimate** must be delivered to the borrower **within 3 business days** of receiving the application. "Received" is defined as the date the Intake Orchestrator timestamps the application.
- Loan Estimate must use the prescribed CFPB form.
- Fee tolerances: certain fees cannot exceed the disclosed amount at closing (zero tolerance, 10% cumulative tolerance, or unlimited based on fee category).

### ECOA / Regulation B (Equal Credit Opportunity Act)

- **Adverse action notice** must be sent **within 30 days** of receiving a completed application if the application is denied.
- Notice must contain specific reasons for denial (not generic boilerplate).
- Must include credit score disclosure per FCRA Section 615(a).
- Must include statement of ECOA rights.

### HMDA (Home Mortgage Disclosure Act)

- All application data must be captured for LAR reporting.
- LAR must be submitted to regulators by March 1 of the following year.
- Demographic data is self-reported by the borrower; lender must collect per HMDA requirements but cannot require disclosure.

### Fair Lending

- All pricing, terms, and decision outcomes must be consistent across comparable applicants.
- Regular fair lending analysis should be performed on aggregate data (this agent captures the per-file data; aggregate analysis is a separate process).

### Record Retention

| Document | Retention Period |
|----------|-----------------|
| Loan Estimate | Life of loan + 3 years (or 3 years if denied) |
| Adverse action notice | 25 months minimum |
| Pre-approval letter | Life of loan + 3 years |
| HMDA LAR data | 3 years after submission |
| Complete audit trail | Life of loan + 7 years (or 7 years if denied) |
| Credit report data | Life of loan + 7 years (or 25 months if denied) |

### Regulatory Timing Summary

| Disclosure | Deadline | Consequence of Miss |
|------------|----------|---------------------|
| Loan Estimate delivery | 3 business days from application | TRID violation — regulatory penalty, potential borrower claim |
| Adverse action notice | 30 days from completed application | ECOA violation — regulatory penalty |
| Pre-approval letter expiration | 60–90 days from issuance | Letter becomes void; borrower must re-apply |
