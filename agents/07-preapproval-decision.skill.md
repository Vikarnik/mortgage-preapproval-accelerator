# Pre-Approval Decision Agent

## Purpose

Synthesizes all upstream agent outputs into a structured recommendation packet for human underwriter review. This agent compiles the complete picture — credit, income, property, compliance, and AUS results — into a single decision-ready package with a recommended action.

**THIS AGENT DOES NOT MAKE FINAL DECISIONS.** It produces a recommendation only. A human underwriter must review and explicitly approve, deny, or condition the application.

## Triggers

| Trigger | Source |
|---------|--------|
| After AUS Submission (06) completes | Or after all prior agents complete if AUS is bypassed (manual underwriting path) |

## Inputs

### Upstream Agent Outputs

| Source Agent | Key Data Consumed |
|--------------|-------------------|
| Intake Orchestrator (01) | Case ID, application data, validation status, borrower info |
| Document Analysis (02) | Document extraction results, confidence scores, discrepancy report |
| Credit Bureau (03) | Middle FICO, tradelines, monthly obligations, derogatory history, public records |
| KYC/AML Screening (04) | Screening result (CLEAR/HIT/POTENTIAL_MATCH), risk score, CIP status |
| Income Verification (05) | Qualifying income, front-end DTI, back-end DTI, employment status, stability assessment |
| AUS Submission (06) | AUS recommendation, conditions list, risk factors, appraisal waiver status |

## Processing Logic

### Step 1: Compile Decision Factors Summary

Aggregate key decision metrics into a single-view dashboard:

| Factor | Value Source | Display |
|--------|-------------|---------|
| Middle FICO score | Credit Bureau Agent | Score + bureau breakdown |
| Front-end DTI | Income Verification Agent | Percentage + threshold comparison |
| Back-end DTI | Income Verification Agent | Percentage + threshold comparison |
| LTV ratio | Calculated (loan amount / property value) | Percentage |
| CLTV ratio | If subordinate liens exist | Percentage |
| Qualifying income | Income Verification Agent | Monthly amount + breakdown by source |
| Reserves | Document Analysis (bank statements) | Months of PITI in reserve |
| AUS finding | AUS Submission Agent | Recommendation code + engine |

### Step 2: Risk Rating by Category

Assign a risk rating per category using rules-based evaluation:

| Category | GREEN | YELLOW | RED |
|----------|-------|--------|-----|
| **Credit** | FICO ≥ 700, no derogatories | FICO 620–699, minor derogatories | FICO < 620, recent BK/foreclosure |
| **Income/DTI** | Back-end DTI ≤ 36%, stable income | DTI 37–43%, minor flags | DTI > 43%, declining income, gaps |
| **Employment** | Verified, 2+ years tenure | Verified, < 2 years or recent change | Unable to verify, inactive status |
| **Property/LTV** | LTV ≤ 80% | LTV 80–95% | LTV > 95% |
| **Documents** | All complete, confidence ≥ 95% | Minor gaps, confidence 85–94% | Missing docs, confidence < 85% |
| **KYC/AML** | CLEAR, LOW risk | POTENTIAL_MATCH or MEDIUM risk | HIT, HIGH risk, OFAC concerns |
| **AUS** | Approve/Eligible | Approve/Ineligible or Accept | Refer, Caution, or Out of Scope |

### Step 3: Generate Overall Recommendation

| Overall Recommendation | Criteria |
|------------------------|----------|
| **APPROVE** | All categories GREEN or YELLOW, AUS Approve/Eligible, no regulatory flags |
| **APPROVE_WITH_CONDITIONS** | Mostly GREEN/YELLOW but with outstanding conditions from AUS or document gaps that can be remedied |
| **DENY** | Any RED category that cannot be mitigated, DTI > 50%, FICO below program minimum, failed KYC/AML |
| **REFER_TO_SENIOR** | Mixed signals, AUS Refer with compensating factors, edge cases requiring experienced judgment |

### Step 4: Generate Recommended Pre-Approval Amount

If recommendation is APPROVE or APPROVE_WITH_CONDITIONS:

- Calculate maximum loan amount that keeps back-end DTI ≤ 43% (QM threshold).
- If requested amount ≤ maximum, recommend requested amount.
- If requested amount > maximum, recommend the maximum and note the reduction.
- Factor in required mortgage insurance impact on PITI.

### Step 5: Draft Conditions List

Compile all outstanding conditions from:

| Source | Condition Type |
|--------|---------------|
| AUS findings | Prior-to-closing, prior-to-funding |
| Document Analysis flags | Missing documents, low-confidence extractions needing verification |
| Income Verification flags | Employment gaps, income discrepancies needing explanation |
| Credit flags | Open disputes, recent inquiries needing explanation |

### Step 6: Prepare Adverse Action Reason Codes (if DENY)

If recommendation is DENY, prepare specific reason codes per ECOA/Regulation B:

| Code Category | Examples |
|---------------|----------|
| Credit history | Insufficient credit history, excessive delinquencies |
| Income/employment | Insufficient income, unable to verify employment |
| Collateral | Insufficient collateral, property ineligible |
| DTI | Excessive obligations relative to income |

### Step 7: Generate Audit Trail Summary

Compile a chronological log of all agent actions, timestamps, data sources consulted, flags raised, and decisions made throughout the pipeline.

## Outputs

### Decision Recommendation Packet

| Output | Type | Description |
|--------|------|-------------|
| Overall recommendation | Enum | `APPROVE` / `APPROVE_WITH_CONDITIONS` / `DENY` / `REFER_TO_SENIOR` |
| Risk scorecard | Object | Per-category risk rating (GREEN/YELLOW/RED) with supporting data |
| Decision factors summary | Object | Single-view of all key metrics |
| Recommended loan amount | Currency | May differ from requested if DTI constraints apply |
| Recommended loan terms | Object | Rate, term, program, MI requirement |
| Conditions list | Array | All outstanding items, categorized by source and timing |
| Adverse action codes | Array | If DENY — specific reason codes per ECOA |
| Compensating factors | Array | Positive factors that may offset risk (high reserves, strong credit history, low LTV) |
| AUS results summary | Object | Engine used, recommendation, key findings |
| Full audit trail summary | Object | Chronological log of all pipeline actions |

## Error Handling & Escalation

| Scenario | Action |
|----------|--------|
| Missing upstream agent output | Cannot compile complete recommendation. Flag specific missing agent and reason. Do not generate partial recommendation — route to operations for investigation. |
| Conflicting signals across agents | Include all signals with notation. Recommend `REFER_TO_SENIOR` for human judgment. |
| KYC/AML in HOLD state | Note in recommendation. Underwriter cannot approve until KYC/AML is resolved. |
| Edge case not covered by rules | Recommend `REFER_TO_SENIOR` with detailed explanation of the ambiguity. |

### CRITICAL CONSTRAINT

**This agent produces a RECOMMENDATION ONLY.** The recommendation packet is presented to a human underwriter via the review UI. The following actions require explicit human approval:

- Issuing a pre-approval letter
- Denying an application
- Setting conditions
- Approving an amount different from the recommendation

No pre-approval letter, denial notice, or commitment is generated until a human underwriter explicitly records their decision in the system.

### Human Review SLA

| Timer | Action |
|-------|--------|
| Recommendation packet delivered | Start 30-minute review clock |
| 25 minutes elapsed, no action | Send alert to underwriting manager |
| 30 minutes elapsed, no action | Escalate to senior underwriting manager |
| 60 minutes elapsed, no action | Flag as SLA breach in reporting dashboard |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Agent processing timeout | 30 seconds (compilation is fast — the data is already prepared) |
| Human review timeout | N/A — this agent completes quickly; the wait is on the human reviewer |
| Retry policy | Not applicable — if compilation fails, it is a data issue, not a transient error |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Underwriter Review UI | Presents recommendation packet for human decision | Internal application |
| Notification Service | SLA alerts to underwriting manager | Internal messaging |

## Regulatory Requirements

- **ECOA / Regulation B**: If the recommendation is DENY, adverse action reason codes must be specific, accurate, and drawn from the approved code list. Generic reasons are not acceptable.
- **Fair lending**: The recommendation algorithm must not directly or indirectly use prohibited factors (race, color, religion, national origin, sex, marital status, age, receipt of public assistance). All decision factors must be documented and auditable.
- **TRID timing**: The clock started at Intake. The underwriter must act with sufficient speed to allow the Compliance Agent to generate and deliver the Loan Estimate within 3 business days.
- **Audit trail**: The complete audit trail is a regulatory requirement. Every data point, calculation, flag, and recommendation must be traceable to its source.
