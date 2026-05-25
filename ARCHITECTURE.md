# Mortgage Pre-Approval Accelerator — Architecture Overview

**Objective:** Reduce mortgage pre-approval time from 3–5 days to under 1 hour at a mid-sized US retail bank (modeled on Truist-scale operations).

**Regulatory Framework:** TRID (TILA-RESPA Integrated Disclosure), ECOA/Reg B (Equal Credit Opportunity), BSA/AML, FCRA (Fair Credit Reporting Act), RESPA, Fannie Mae/Freddie Mac guidelines.

---

## 1. Current-State Process (3–5 Days)

| Step | Owner | Time | Pain Points |
|------|-------|------|-------------|
| 1. Application intake (1003 form) | Borrower + LO | 30 min – 1 day | Incomplete apps, manual data entry errors |
| 2. Document collection (W-2, paystubs, bank statements, ID) | Borrower | 1–3 days | Chasing documents, email back-and-forth |
| 3. Tri-merge credit pull | Loan processor | 15 min | Legacy API latency, manual triggering |
| 4. Income & employment verification | Loan processor | 4–8 hours | Manual cross-referencing, phone calls to employers |
| 5. KYC/AML screening (OFAC, watchlists) | Compliance | 1–4 hours | Siloed system, manual review of hits |
| 6. AUS submission (DU/LP) | Underwriter | 30 min | Manual data prep, re-keying from documents |
| 7. Human underwriter review | Underwriter | 1–2 days | Backlog, conditions loops |
| 8. Pre-approval letter generation | LO | 30 min | Manual drafting |
| 9. TRID Loan Estimate delivery | LO/Compliance | 30 min | Timing compliance tracking |

**Total elapsed:** 3–5 business days, ~6–8 hours of human effort.

---

## 2. Target-State Process (Under 1 Hour)

### Agent Pipeline Architecture

```
BORROWER APPLICATION
        │
        ▼
┌─────────────────────────┐
│  INTAKE ORCHESTRATOR     │  ← Validates completeness, creates case
│  AGENT                   │     Elapsed: 0–2 min
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────────┐
│ DOC    │ │ CREDIT     │   ← Parallel execution
│ ANAL.  │ │ BUREAU     │      Elapsed: 2–8 min
│ AGENT  │ │ AGENT      │
└───┬────┘ └─────┬──────┘
    │            │
    ▼            ▼
┌────────────────────────┐
│  KYC/AML SCREENING     │  ← Identity + watchlist checks
│  AGENT                 │     Elapsed: 8–12 min
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  INCOME & EMPLOYMENT   │  ← Cross-references docs + credit
│  VERIFICATION AGENT    │     Elapsed: 12–18 min
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  AUS SUBMISSION        │  ← Prepares 1003 data → DU/LP
│  AGENT                 │     Elapsed: 18–25 min
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│  PRE-APPROVAL DECISION │  ← Synthesizes recommendation
│  AGENT                 │     Elapsed: 25–30 min
└────────┬───────────────┘
         │
         ▼
╔════════════════════════╗
║  HUMAN REVIEW          ║  ← MANDATORY checkpoint
║  CHECKPOINT            ║     Elapsed: 30–55 min
╚════════╤═══════════════╝
         │
         ▼
┌────────────────────────┐
│  COMPLIANCE & AUDIT    │  ← Final compliance, letter gen
│  AGENT                 │     Elapsed: 55–60 min
└────────────────────────┘
```

---

## 3. Agent Inventory

| # | Agent | Automation Level | Human Required? | Timeout |
|---|-------|-----------------|-----------------|---------|
| 1 | Intake Orchestrator | Full | No | 120s |
| 2 | Document Analysis | Full | No (escalate on low confidence) | 180s |
| 3 | Credit Bureau | Full | No | 60s (retry 2x) |
| 4 | KYC/AML Screening | Partial | Yes (on hits) | 90s |
| 5 | Income & Employment Verification | Full | No (escalate on mismatch >15%) | 120s |
| 6 | AUS Submission | Full | No | 90s |
| 7 | Pre-Approval Decision | Recommendation only | YES — always | N/A |
| 8 | Compliance & Audit | Full | No (escalate on violations) | 60s |

---

## 4. Data Connectors

| Connector | Protocol | Latency | Availability | Mock Strategy |
|-----------|----------|---------|-------------|---------------|
| Core Banking (customer lookup) | REST/JSON | <500ms | 99.9% | JSON stub with 5 test profiles |
| Credit Bureau (Equifax/Experian/TransUnion) | SOAP/XML legacy → REST adapter | 2–15s | 99.5% | Python class returning mock tri-merge |
| Document OCR (W-2, paystub, bank stmt) | REST/multipart | 3–30s | 99.0% | Pre-parsed JSON from sample PDFs |
| OFAC/Sanctions Screening | REST/JSON | <2s | 99.9% | JSON stub with hit/no-hit scenarios |
| AUS (Desktop Underwriter / Loan Product Advisor) | MISMO XML v3.4 | 5–30s | 99.0% | Python class returning Approve/Refer/Caution |
| Property Valuation (AVM) | REST/JSON | 1–5s | 98.0% | JSON stub with property data |
| Employer Verification (VOIE — The Work Number) | REST/JSON | 2–10s | 98.5% | JSON stub with employment records |

---

## 5. Non-Functional Requirements

### 5.1 Human-in-the-Loop (Mandatory)

- **Pre-Approval Decision**: No loan recommendation is ever auto-approved. The Decision Agent produces a recommendation packet; a human underwriter must review and approve/deny/condition.
- **KYC/AML Hits**: Any OFAC or watchlist hit escalates to BSA Officer. Agent pauses and waits.
- **Document Confidence < 85%**: If OCR confidence on any extracted field is below 85%, the document is flagged for manual review.
- **Income Mismatch > 15%**: If stated income vs. document-derived income diverges by more than 15%, human review is required.

### 5.2 Timeout & Retry

| Scenario | Timeout | Retries | Fallback |
|----------|---------|---------|----------|
| Credit bureau unreachable | 30s | 2 (exponential backoff) | Queue for manual pull, notify LO |
| AUS system down | 45s | 1 | Flag case for manual underwriting |
| OCR service timeout | 60s | 1 | Queue document for manual review |
| OFAC API timeout | 15s | 3 | Hold case — cannot proceed without screening |

### 5.3 Graceful Decline & Model Guardrails

- **No autonomous denials.** If any agent produces a negative signal (high DTI, low credit score, AUS Refer), the pipeline continues to the Decision Agent, which packages the finding as part of the recommendation. A human makes the final call.
- **Adverse action notice.** If a human reviewer denies the application, the Compliance Agent auto-generates an adverse action notice per ECOA/Reg B, citing specific reasons from the pipeline data.
- **Model confidence thresholds.** Document extraction, income calculation, and AUS interpretation all carry confidence scores. Anything below threshold triggers escalation, never silent failure.
- **Bias monitoring.** The Compliance Agent logs all decision factors to enable fair-lending analysis (HMDA data fields). No protected-class data is used in credit decisioning.

### 5.4 Audit Trail

Every agent writes structured log entries to an append-only audit ledger:

```json
{
  "case_id": "MPA-2026-00142",
  "agent": "document_analysis",
  "timestamp": "2026-05-24T14:32:01Z",
  "action": "extract_w2_data",
  "input_hash": "sha256:abc123...",
  "output_summary": { "employer": "Acme Corp", "wages": 95000, "confidence": 0.94 },
  "confidence": 0.94,
  "escalation": false,
  "duration_ms": 2340
}
```

### 5.5 Security & PII

- All PII encrypted at rest (AES-256) and in transit (TLS 1.3).
- SSN masked in all logs and UI (last 4 only).
- Document storage in bank-controlled S3-equivalent with 90-day retention per regulation.
- Agent-to-agent communication via internal message bus — no PII leaves the bank perimeter.

### 5.6 TRID Compliance

- Loan Estimate must be generated within 3 business days of receiving a complete application.
- The Compliance Agent tracks the "application received" timestamp and raises an alert if the pipeline hasn't completed within 2 business days (safety buffer).
- All fee disclosures pulled from bank's current rate sheet at time of pre-approval.

---

## 6. Error Handling Matrix

| Error | Agent | Severity | Action |
|-------|-------|----------|--------|
| Incomplete application (missing fields) | Intake Orchestrator | Low | Return to borrower with specific missing items |
| Unreadable document | Document Analysis | Medium | Flag for manual review, continue pipeline with available docs |
| Credit bureau returns error | Credit Bureau | High | Retry 2x, then queue for manual pull |
| OFAC hit (true positive) | KYC/AML | Critical | Halt pipeline, escalate to BSA Officer |
| OFAC hit (false positive) | KYC/AML | Medium | Flag for BSA review, continue pipeline in hold state |
| Income mismatch > 15% | Income Verification | Medium | Flag for human review, include discrepancy details |
| AUS returns "Refer" | AUS Submission | Medium | Package for manual underwriting, include all conditions |
| AUS returns "Caution" | AUS Submission | High | Package for senior underwriter, include risk factors |
| DTI > 50% | Income Verification | Medium | Continue pipeline, flag in decision packet |
| Pipeline timeout (> 45 min without human step) | All | High | Alert LO, provide partial results |

---

## 7. Workflow State Machine

```
SUBMITTED → VALIDATING → PROCESSING → ANALYZING → DECISIONING → HUMAN_REVIEW → APPROVED/DENIED/CONDITIONED
     │           │            │            │             │              │
     └→ INCOMPLETE  └→ ERROR    └→ TIMEOUT   └→ ESCALATED  └→ HOLD      └→ ADVERSE_ACTION
```

Each state transition is logged with timestamp, actor (agent or human), and reason code.
