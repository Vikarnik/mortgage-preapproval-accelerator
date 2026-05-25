# Income & Employment Verification Agent

## Purpose

Cross-references all income data sources, calculates qualifying income per agency guidelines, verifies current employment, and computes front-end and back-end DTI (Debt-to-Income) ratios. This agent synthesizes outputs from Document Analysis and Credit Bureau agents into a unified income and affordability assessment.

## Triggers

| Trigger | Source |
|---------|--------|
| After Document Analysis (02) AND Credit Bureau (03) agents complete | Sequential — requires both upstream agents' outputs |

## Inputs

### From Document Analysis Agent (02)

| Field | Description |
|-------|-------------|
| W-2 extracted data | Employer name, wages (Box 1), tax years |
| Pay stub extracted data | Current gross pay, YTD earnings, employer, pay period |
| Tax return extracted data | AGI, filing status, self-employment income, rental income |
| Bank statement extracted data | Average monthly deposits, large deposit flags |
| Document confidence scores | Per-field and overall confidence |
| Cross-reference discrepancy report | Any mismatches found between documents |

### From Credit Bureau Agent (03)

| Field | Description |
|-------|-------------|
| Total monthly obligations | Sum of all minimum monthly debt payments |
| Tradeline array | For detailed debt itemization |
| Mortgage/rent tradeline | Current housing payment (if applicable) |

### From Intake Orchestrator (01)

| Field | Description |
|-------|-------------|
| Loan amount requested | Principal amount |
| Loan term | 15 / 20 / 30 years |
| Loan type | Conventional / FHA / VA / USDA |
| Property type | Single Family / Condo / etc. |
| Occupancy type | Primary / Second Home / Investment |

### Estimated Costs (from rate sheet or defaults)

| Field | Source |
|-------|--------|
| Estimated interest rate | Current rate sheet for loan type and term |
| Estimated property taxes | County tax database or estimate based on value |
| Estimated homeowner's insurance | Standard estimate based on property value |
| Estimated mortgage insurance (if applicable) | Based on LTV and loan type |
| HOA dues (if applicable) | From application or property data |

## Processing Logic

### Step 1: Calculate Monthly Gross Income

**W-2 / Salaried Employment**

| Method | Calculation |
|--------|-------------|
| W-2 annualized | Average of last 2 years W-2 Box 1 wages / 12 |
| Pay stub annualized | Current YTD gross / months elapsed in year |
| **Qualifying income** | **Use the lower of W-2 average and pay stub annualization** |

**Self-Employment Income**

| Method | Calculation |
|--------|-------------|
| Requires 2 years tax returns | Non-negotiable — if < 2 years, cannot use self-employment income |
| Net self-employment income | Average of 2 years (Schedule C net profit or K-1 distributions) |
| Declining income test | If year 2 < year 1 by > 10%, use year 2 only |
| Add back eligible deductions | Depreciation, depletion, amortization (per agency guidelines) |

**Other Income Sources**

| Source | Qualifying Rule |
|--------|-----------------|
| Rental income (Schedule E) | 75% of gross rent minus PITIA on rental property |
| Investment income | 2-year average, must demonstrate likelihood of continuance |
| Alimony / child support | Only if documented via court order AND received consistently for 6+ months AND will continue for 3+ years |
| Social Security / pension | Use gross amount; if non-taxable, may gross up by 125% |

### Step 2: Verify Employment

- Submit employer verification request to VOIE (Verification of Income and Employment) service — The Work Number.
- Verify: current employer name, hire date, employment status (active/inactive), income.
- Cross-reference VOIE employer name against W-2 and pay stub employer name.
- Flag if employment start date is < 2 years (evaluate job history for gaps).

### Step 3: Compute PITI (Principal, Interest, Taxes, Insurance)

| Component | Calculation |
|-----------|-------------|
| Principal & Interest (P&I) | Standard amortization formula using loan amount, rate, term |
| Property taxes (T) | Monthly estimate from county data or application |
| Homeowner's insurance (I) | Monthly estimate |
| Mortgage insurance (MI) | If LTV > 80% (conventional) or FHA/VA funding fee equivalent |
| HOA dues | If applicable |
| **Total PITI** | **P + I + T + I + MI + HOA** |

### Step 4: Compute DTI Ratios

| Ratio | Formula | Description |
|-------|---------|-------------|
| Front-end DTI | PITI / Monthly gross income | Housing expense ratio |
| Back-end DTI | (PITI + all monthly debt obligations) / Monthly gross income | Total obligation ratio |

### Step 5: Income Stability Assessment

| Factor | Evaluation |
|--------|------------|
| Job tenure | Flag if < 2 years at current employer |
| Job changes | Count employer changes in last 2 years; flag if > 2 |
| Industry consistency | Flag if career/industry change in last 2 years |
| Income trend | Flag if income is declining year-over-year |
| Employment gaps | Flag any gap > 30 days in last 2 years |
| Self-employment stability | Flag if self-employment < 2 years |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Qualifying monthly income | Currency | Calculated per agency guidelines |
| Income breakdown | Object | By source (W-2, self-employment, rental, other) with amounts |
| Front-end DTI ratio | Percentage | Housing expense / gross income |
| Back-end DTI ratio | Percentage | Total obligations / gross income |
| PITI breakdown | Object | P&I, taxes, insurance, MI, HOA — each component |
| Employment verification status | Enum | `VERIFIED` / `UNABLE_TO_VERIFY` / `DISCREPANCY` |
| Employment verification details | Object | Employer, hire date, status, income per VOIE |
| Income stability assessment | Enum | `STABLE` / `MODERATE_RISK` / `HIGH_RISK` |
| Income stability factors | Array | Specific flags raised |
| Discrepancy flags | Array | Mismatches between income sources |

## Error Handling & Escalation

### DTI Threshold Flags

| Condition | Loan Type | Action |
|-----------|-----------|--------|
| Front-end DTI > 28% | Conventional | Flag — may still be acceptable with compensating factors |
| Front-end DTI > 31% | FHA | Flag |
| Back-end DTI > 36% | Conventional (standard) | Flag |
| Back-end DTI > 43% | All — QM limit | **Strong flag** — exceeds Qualified Mortgage threshold |
| Back-end DTI > 45% | FHA (with compensating factors) | Flag for manual review |
| Back-end DTI > 50% | All | **Very strong flag** — likely denial. Requires exceptional compensating factors. |

### Other Escalation Rules

| Scenario | Action |
|----------|--------|
| Income mismatch > 15% between any two sources | Flag for human underwriter review. Do not auto-calculate qualifying income — underwriter must determine which source to rely on. |
| VOIE returns employer not found | Flag for manual verification (verbal VOE). Do not block pipeline but carry flag to Decision Agent. |
| VOIE returns inactive employment | **Critical flag** — borrower may no longer be employed. Escalate immediately to Loan Officer for borrower contact. |
| Self-employment with < 2 years history | Cannot qualify self-employment income. Use only W-2/salary income if available. Flag for underwriter. |
| Declining self-employment income (> 20% drop) | Flag — underwriter must evaluate business viability. |
| Large unexplained deposits in bank statements | Carry forward flag from Document Analysis. Income agent should not count unexplained deposits as qualifying income. |

## Timeout & Retry

| Parameter | Value |
|-----------|-------|
| Total agent timeout | 120 seconds |
| VOIE service timeout | 30 seconds |
| VOIE retry policy | 2 attempts with 5-second delay. If fails, flag for manual verbal VOE. |

## Data Connectors

| System | Purpose | Protocol |
|--------|---------|----------|
| Employer Verification API (VOIE / The Work Number) | Employment and income verification | REST API, encrypted |
| Rate Sheet Service | Current interest rates for PITI calculation | Internal API |
| County Tax Database | Property tax estimates | REST API or cached lookup |

## Regulatory Requirements

- **Ability-to-Repay (ATR) / Qualified Mortgage (QM)**: Lenders must make a reasonable, good-faith determination that the borrower can repay the loan. DTI > 43% generally fails the QM safe harbor (with limited exceptions for GSE-eligible loans).
- **Equal Credit Opportunity Act (ECOA)**: Income from public assistance, part-time employment, alimony, and child support must be considered if the borrower chooses to disclose it. Cannot discount income based on source if it is stable and verifiable.
- **Fair lending**: Income calculations must be applied consistently across all applicants. Document all assumptions and methodologies used.
- All income calculations, source documents, and verification results must be retained in the case file for audit.
