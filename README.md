Mortgage Pre-Approval Accelerator
An agentic workflow system designed to reduce mortgage pre-approval time from 3–5 business days to under 1 hour at a mid-sized US retail bank (modeled on Truist-scale operations). Built as a reference architecture for Claude Cowork agents with full regulatory compliance, mandatory human checkpoints, and auditable decision trails.

Why This Exists
At a typical mid-sized bank, a mortgage pre-approval touches 9 discrete steps across 4 different roles (borrower, loan officer, loan processor, underwriter), accumulating 6–8 hours of human effort spread over 3–5 calendar days. Most of that time is spent on mechanical tasks — chasing documents, re-keying data between systems, waiting in underwriting queues, and manually cross-referencing income sources.
This project demonstrates how an orchestrated pipeline of specialized agents can compress that timeline to under an hour by automating the mechanical work while preserving the human judgment that regulators and sound lending practice require.
The system is designed around three hard constraints that shaped every architectural decision:

No autonomous credit decisioning. US mortgage regulation (ECOA, TRID, fair lending) and prudent risk management require a human underwriter to make the final approve/deny/condition call. The agents produce a recommendation packet — never a decision.
Full auditability. Every agent action is logged to an append-only ledger with timestamps, input hashes, output summaries, confidence scores, and escalation flags. This supports regulatory examination, fair-lending analysis, and internal quality assurance.
Graceful degradation. Legacy bank systems go down. Credit bureaus time out. OCR misreads a smudged W-2. The pipeline handles every failure mode with specific retry logic, fallback paths, and human escalation — it never silently fails or auto-denies.


Repository Structure
mortgage-preapproval-accelerator/
├── ARCHITECTURE.md                          # Full architecture document
├── README.md                                # This file
├── agents/                                  # Agent SKILL.md specifications
│   ├── 01-intake-orchestrator.skill.md
│   ├── 02-document-analysis.skill.md
│   ├── 03-credit-bureau.skill.md
│   ├── 04-kyc-aml-screening.skill.md
│   ├── 05-income-employment-verification.skill.md
│   ├── 06-aus-submission.skill.md
│   ├── 07-preapproval-decision.skill.md
│   └── 08-compliance-audit.skill.md
├── connectors/                              # Python data connector stubs
│   ├── __init__.py
│   ├── core_banking.py
│   ├── credit_bureau.py
│   ├── document_ocr.py
│   ├── kyc_aml_screening.py
│   ├── aus_service.py
│   ├── employer_verification.py
│   └── property_valuation.py
└── mock-data/
    └── test_applicants.json                 # 3 detailed test profiles

Architecture Choices
Why 8 Agents Instead of 1 Monolith
Each agent maps to a distinct regulatory domain and data source. Splitting them provides three practical benefits:
Parallel execution. Document Analysis and Credit Bureau run simultaneously — they have no dependency on each other. In a monolith, these would be sequential. This alone saves 5–10 minutes.
Isolated failure. If the credit bureau times out, only the Credit Bureau Agent retries and escalates. Document analysis continues unaffected. A monolith would stall the entire pipeline.
Audit granularity. Regulators want to know exactly when the OFAC check ran, what it returned, and who reviewed the result. Per-agent logging gives this naturally, without parsing a single massive log.
Why These Specific 8 Agents
The agent boundaries follow the natural seams in mortgage origination:
AgentWhy It's SeparateIntake OrchestratorValidation logic is purely structural (are all fields present?). It has zero domain knowledge about credit or income. Separating it means the pipeline fails fast on incomplete applications before burning API calls.Document AnalysisOCR is computationally expensive and has its own confidence model. It talks to a completely different backend (Ocrolus, Blend, Textract) than anything else in the pipeline.Credit BureauTalks to a legacy SOAP endpoint via an adapter. Has FCRA-specific logging requirements (permissible purpose, inquiry tracking). The retry logic is unique — you can proceed with 2 of 3 bureaus, but not 1.KYC/AML ScreeningRegulatory criticality. An OFAC hit halts the entire pipeline and escalates to the BSA Officer. This is the only agent with a hard-stop escalation path. Mixing it with other logic would make the halt semantics ambiguous.Income & Employment VerificationThis is where data from multiple upstream agents converges. It needs both document extraction (from Agent 02) and credit report data (from Agent 03) to compute DTI ratios. It's the first agent with true cross-agent dependencies.AUS SubmissionTalks to Fannie Mae DU / Freddie Mac LPA via MISMO XML. Has dual-AUS fallback logic (try DU first, fall back to LPA on a Refer). Completely different protocol and error semantics from everything else.Pre-Approval DecisionThis is the synthesis point — it reads from all 6 upstream agents and produces a single recommendation packet. Critically, it is recommendation-only. Separating it from the human checkpoint makes the boundary between machine recommendation and human decision architecturally explicit.Compliance & AuditRuns after the human decision. Generates legally required documents (Loan Estimate, adverse action notice) with specific timing constraints (TRID 3-day rule). It's the only agent that takes the human's decision as input.
Pipeline Flow and Dependencies
Intake Orchestrator
    ├── Document Analysis ──────┐
    └── Credit Bureau ──────────┤  (parallel)
                                ▼
                    KYC/AML Screening
                          │
                          ▼
              Income & Employment Verification
                          │
                          ▼
                    AUS Submission
                          │
                          ▼
                Pre-Approval Decision
                          │
                    ══════╪══════  HUMAN CHECKPOINT
                          │
                          ▼
                  Compliance & Audit
Document Analysis and Credit Bureau run in parallel because they are independent — one parses uploaded PDFs, the other pulls a credit report from external bureaus. Both must complete before Income Verification can run, since DTI calculation requires wages (from documents) and monthly obligations (from the credit report).
KYC/AML sits between the parallel agents and Income Verification as a gate. If there's an OFAC hit, there's no point computing DTI — the pipeline is on hold regardless.
The Human Checkpoint
The checkpoint between the Decision Agent and the Compliance Agent is the architectural spine of the entire system. It exists because:

ECOA (Equal Credit Opportunity Act) requires that credit decisions be made by accountable parties. An algorithm can inform the decision; it cannot be the decision-maker.
Fair lending compliance requires the ability to explain why a decision was made in terms a human reviewed and endorsed.
The bank's risk management framework treats credit decisioning as a function that requires human sign-off, regardless of what an AUS recommends.

The Decision Agent packages everything the underwriter needs into a single review screen: a risk scorecard (GREEN/YELLOW/RED by category), the AUS finding, all conditions, the recommended loan amount, and any flags from upstream agents. The underwriter can then APPROVE, APPROVE WITH CONDITIONS, or DENY.
If no action is taken within 25 minutes, an alert goes to the underwriting manager. The pipeline does not auto-approve or auto-deny on timeout — it waits.

Agent Skill Specifications
Each agent is specified as a SKILL.md file in the agents/ directory. These are structured as Claude Cowork skill definitions and follow a consistent format:
Anatomy of a SKILL.md
Every skill spec contains these sections:
SectionPurposePurposeWhat the agent does, its role in the pipeline, and critical constraints (e.g., "this agent does NOT make final decisions")TriggersWhat initiates the agent, with dependency table showing upstream requirementsInputsField-level input specs with data types, formats, and source agentsProcessing LogicStep-by-step processing with decision tables, calculation formulas, and mapping rulesOutputsTyped output fields with descriptions and downstream consumersError Handling & EscalationScenario-based escalation rules with severity levels and specific actionsTimeout & RetryTimeout values, retry counts, backoff strategy, and fallback behaviorData ConnectorsExternal systems required, with protocols and expected latencyRegulatory RequirementsApplicable regulations (FCRA, ECOA, TRID, BSA/AML, HMDA, GLBA) with retention periods
Why SKILL.md Format
The SKILL.md format was chosen because:

It's what Claude Cowork agents consume. Each file is a complete specification that a Claude agent can read and execute against. The structured sections map to the agent's decision-making process — inputs tell it what to expect, processing logic tells it what to do, escalation rules tell it when to stop and ask for help.
It's human-reviewable. An underwriting manager or compliance officer can read these specs and validate that the agent's logic matches bank policy. Markdown renders cleanly in any browser, git diff, or documentation tool.
It's version-controllable. When lending guidelines change (Fannie Mae updates DTI thresholds, OFAC adds new screening requirements), the change is a diff to a specific SKILL.md file. The git history shows exactly what changed, when, and why.

Key Design Decisions in the Specs
Confidence thresholds are explicit, not tunable. The Document Analysis agent uses 85% as its escalation threshold. This isn't a parameter to optimize — it's a compliance boundary. Below 85%, the extracted data isn't reliable enough for a credit decision without human verification. This number is baked into the spec, not configurable at runtime, because changing it has regulatory implications.
Escalation rules are exhaustive. Each spec lists every scenario that triggers escalation, the severity level, and the exact action taken. There are no catch-all "escalate if something seems wrong" rules. This is deliberate — in a regulated environment, ambiguous escalation logic leads to inconsistent outcomes, which leads to fair-lending violations.
Outputs name their downstream consumers. Each output field specifies which agent consumes it. This makes the data flow traceable without reading the orchestration layer, and ensures that if an agent's output schema changes, the impacted downstream agents are immediately identifiable.

Data Connector Stubs
The connectors/ directory contains 7 Python modules that simulate the external integrations a production system would connect to. Each stub is designed to be realistic enough to drive an interactive demo while exposing the integration patterns a real implementation would follow.
Connector Inventory
ModuleReal-World SystemProtocol SimulatedLinescore_banking.pyFIS, Jack Henry, Fiserv core banking / CISREST/JSONCustomer lookup, existing product check, lending footprintcredit_bureau.pyCoreLogic Credco, MeridianLink (aggregating Equifax, Experian, TransUnion)SOAP/XML → REST adapterTri-merge credit pull with tradelines, payment history, public recordsdocument_ocr.pyOcrolus, Blend Doc AI, AWS TextractREST/multipartW-2, paystub, bank statement, tax return extraction with per-field confidencekyc_aml_screening.pyLexisNexis, Dow Jones Risk & Compliance, World-CheckREST/JSONOFAC SDN screening, PEP check, CIP identity verificationaus_service.pyFannie Mae Desktop Underwriter, Freddie Mac Loan Product AdvisorMISMO XML v3.4Underwriting decision with conditions, risk factors, appraisal waiveremployer_verification.pyEquifax Workforce Solutions / The Work NumberREST/JSONEmployment verification, income data, job change gap detectionproperty_valuation.pyCoreLogic, HouseCanary, CAPE AnalyticsREST/JSONAVM estimate with confidence interval, comparable sales, flood zone
Why These Specific Stubs Were Written
Each stub exists because the corresponding integration is a hard dependency in the pipeline — without it, the agent that consumes it cannot function:
Credit Bureau is the most complex stub because it's the most complex real-world integration. Production credit pulls go through a multi-hop path: the bank's LOS (Loan Origination System) sends a request to an aggregator (Credco), which fans out to three bureaus via SOAP, merges the results, and returns a tri-merge report. The stub simulates this with realistic latency (0.35s base + jitter), retry logic with exponential backoff, and a 3% timeout rate that triggers the fallback path. Three credit profiles are provided — excellent (788 FICO), fair (692 FICO), and poor (648 FICO) — each with full tradeline arrays including 24-month payment histories.
Document OCR is stubbed because document extraction confidence is the primary driver of human escalation in the pipeline. The stub provides per-field confidence scores, and the Elena Rodriguez profile deliberately includes low-confidence extractions (72–82%) to exercise the escalation path. In production, this would be the most variable and failure-prone integration — PDF quality, scan resolution, handwritten annotations, and multi-page documents all degrade extraction accuracy.
KYC/AML Screening is stubbed with three scenarios (clear, potential match, confirmed hit) because OFAC screening is the only integration that can halt the entire pipeline. The potential-match scenario (Elena Rodriguez fuzzy-matching against an SDN entry with score 0.72) is the most important test case — it exercises the BSA Officer escalation path and the pipeline's HOLD state.
AUS Service simulates both DU and LPA because dual-AUS submission is standard practice. A file that gets a Refer from DU may get an Approve from LPA — the two systems use different algorithms and weight factors differently. The stub implements the decision logic based on FICO/DTI/LTV thresholds and returns realistic conditions lists and risk factors.
Stub Design Patterns
All stubs share these patterns:
python# 1. Configurable error rate via environment variable
ERROR_RATE = float(os.environ.get("CONNECTOR_ERROR_RATE", "0.05"))

# 2. Simulated latency with jitter
time.sleep(BASE_LATENCY_S + random.uniform(0, 0.15))

# 3. Structured audit logging
logger.info("pull_credit_report | ssn=***%s | bureau=tri-merge | duration_ms=%d",
            ssn_last4, duration_ms)

# 4. Type hints on all public functions
def pull_credit_report(
    ssn_encrypted: str,
    full_name: str,
    dob: str,
    address: str,
) -> dict[str, Any]: ...
Why simulated latency? Real integrations have meaningful latency — credit pulls take 2–15 seconds, AUS submission takes 5–30 seconds, OFAC screening takes under 2 seconds. The stubs include small sleep values (0.1–0.5s) to make the demo feel sequential without being tedious. The latency values are documented in the ARCHITECTURE.md connector table for production capacity planning.
Why configurable error rates? Setting CONNECTOR_ERROR_RATE=0.20 lets you stress-test the pipeline's retry and fallback logic without modifying code. At 0% errors, the happy path runs clean. At 20%, you'll see retries, fallbacks, and escalations firing regularly.
Why audit logging on every call? FCRA requires that every credit inquiry be logged with permissible purpose documentation. BSA/AML requires that every sanctions screening be logged with timestamp and disposition. Rather than adding this per-regulation, every connector logs every call uniformly — timestamp, masked inputs, result summary, duration.

Mock Data
Test Applicant Profiles
mock-data/test_applicants.json contains three deeply detailed applicant profiles, each designed to exercise a different path through the pipeline:
Sarah Chen — The clean approval. FICO 785, W-2 employee at a tech company for 4 years, $145K income, buying a $450K home with 20% down. LTV 80%, front-end DTI 22%, back-end DTI 34%. All document confidence scores above 95%. OFAC clear. AUS returns Approve/Eligible with appraisal waiver. This profile validates the happy path — every agent completes cleanly, the Decision Agent recommends APPROVE, and the human reviewer has an easy call.
Marcus Johnson — The conditional approval. FICO 695, recently changed jobs (8 months at current employer after a 69-day gap), $82K income, buying a $320K home with 10% down. LTV 90%, back-end DTI 44% (at the QM limit). Two late payments on credit report. AUS returns Approve/Ineligible with 5 conditions (verify employment, explain late payments, PMI required, verify employment gap). This profile exercises the conditions path — the Decision Agent recommends APPROVE_WITH_CONDITIONS, and the human reviewer must assess whether the conditions are manageable.
Elena Rodriguez — The hard case. FICO 650, self-employed contractor for 3 years, $110K variable income, buying a $380K home with 15% down. Prior Chapter 7 bankruptcy (4 years ago). OFAC potential match (fuzzy name match, score 0.72, different DOB and nationality — almost certainly a false positive, but the BSA Officer must review). Document OCR confidence scores are low (72–82%) because self-employment income documentation is inherently messier. AUS returns Refer (manual underwriting required). This profile exercises every escalation path simultaneously — low OCR confidence, OFAC flag, self-employment complexity, prior bankruptcy, and AUS Refer. The Decision Agent recommends DENY, but a skilled underwriter might see a path to approval with sufficient conditions.
Why Three Profiles
Three profiles is the minimum to cover the decision space: a clean approval, a conditional approval, and a likely denial. Each profile is designed to hit different escalation triggers:
Escalation TriggerSarahMarcusElenaLow OCR confidence (< 85%)NoNoYesOFAC potential matchNoNoYesEmployment gapNoYesNoSelf-employed incomeNoNoYesBack-end DTI > 43%NoYes (44%)Yes (48%)Prior bankruptcyNoNoYesAUS ReferNoNoYesLate payments / derogatoriesNoYes (2)Yes (4)

Non-Functional Requirements
Timeout and Retry Strategy
Every external integration has a specific timeout, retry count, and fallback path. These are not generic — they reflect the actual reliability characteristics of the systems being called:
IntegrationTimeoutRetriesBackoffFallbackCredit bureau30s2Exponential (2s, 8s)Proceed with 2 of 3 bureaus; if 2+ fail, queue for manual pullAUS (DU/LPA)45s1NoneFlag for manual underwritingDocument OCR60s1NoneQueue document for manual review, continue pipelineOFAC screening15s3Linear (5s)HOLD — cannot proceed without screening
The OFAC timeout is the most aggressive (15s timeout, 3 retries) because you cannot close a mortgage without a completed sanctions screening. The fallback is HOLD, not skip — the pipeline waits rather than proceeding without clearance.
Graceful Decline
The pipeline never auto-denies. Every negative signal (low FICO, high DTI, AUS Refer, OFAC hit) flows through to the Decision Agent, which packages it as part of the recommendation. The human underwriter sees the full picture and makes the call.
If the underwriter denies the application, the Compliance Agent generates an adverse action notice per ECOA/Reg B that cites the specific reasons from the pipeline data (e.g., "Insufficient credit history," "Debt-to-income ratio exceeds guidelines"). The reasons come from the data, not from the agent's judgment.
Regulatory Compliance
RegulationHow It's AddressedTRID (TILA-RESPA Integrated Disclosure)Compliance Agent tracks application-received timestamp, generates Loan Estimate within 3-business-day window, raises alert at 2-day mark as safety bufferECOA / Reg B (Equal Credit Opportunity)No protected-class data used in decisioning. Adverse action notices auto-generated with specific reason codes. HMDA data captured for fair-lending analysisFCRA (Fair Credit Reporting Act)Credit pulls logged with permissible purpose. Borrower authorization verified before pull. Hard inquiry documentedBSA/AML (Bank Secrecy Act)OFAC screening mandatory before any credit decision. Hits escalate to BSA Officer. CIP verification documentedHMDA (Home Mortgage Disclosure Act)Compliance Agent captures all required LAR (Loan Application Register) data fields for annual reportingGLBA (Gramm-Leach-Bliley Act)PII encrypted at rest (AES-256) and in transit (TLS 1.3). SSN masked in logs (last 4 only). Agent-to-agent communication via internal bus

Running the Connectors
The stubs are plain Python with no external dependencies beyond the standard library:
bashcd mortgage-preapproval-accelerator

# Import and test
python3 -c "
from connectors import pull_credit_report, submit_to_du, screen_individual
print('All connectors loaded successfully')
"

# Run with higher error rate to test fallback paths
CONNECTOR_ERROR_RATE=0.20 python3 -c "
from connectors.credit_bureau import pull_credit_report
result = pull_credit_report('encrypted_sarah', 'Sarah Chen', '1989-03-15', '742 Elm St')
print(result['summary']['middle_fico'])
"

Extending This System
Adding a New Agent

Create a new agents/NN-agent-name.skill.md following the established section structure.
Define inputs (which upstream agents provide them), processing logic, outputs (which downstream agents consume them), and escalation rules.
Update the pipeline flow in ARCHITECTURE.md to show where the new agent sits in the dependency chain.

Adding a New Connector

Create a new connectors/service_name.py with the standard patterns (configurable error rate, simulated latency, audit logging, type hints).
Add mock data for at least the three test profiles (clean, conditional, problem).
Register the public functions in connectors/__init__.py.

Swapping Stubs for Real Integrations
Each stub's docstring describes the production system it simulates and the protocol it would use. The function signatures are designed to match what a real adapter would expose — replace the mock data with actual API calls and the rest of the pipeline works unchanged.

References

Truist Mortgage Application Process
Fannie Mae Desktop Underwriter
CFPB TRID Rule
OFAC SDN List
MISMO Standards (v3.4)
