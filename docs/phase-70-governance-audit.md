# Phase 70: Independent Clinical Safety Governance Audit Planning, Execution, Findings & Follow-Up Management

## Document Type
Technical Architecture, API Specification & Independent Clinical Safety Governance Audit Lifecycle Documentation

## Phase Overview
Phase 70 establishes the Independent Clinical Safety Governance Audit Management layer for HealthSetu.

While Phase 69 continuously evaluates compliance against approved requirements and controls, Phase 70 manages the independent audit lifecycle that examines whether governance processes, controls, evidence, and compliance assessments are adequately designed, implemented, documented, and reviewed.

Phase 70 provides a controlled backend workflow for planning, scheduling, conducting, documenting, reviewing, and following up on internal or independently governed audits of clinical safety governance processes across HealthSetu.

---

## 1. Non-Negotiable Audit Governance Distinctions & Invariants

1. **An audit is not a routine monitoring dashboard or automated compliance check**: Routine automated metrics indicate status; an audit is an independent, systematically planned evaluation of governance design, operational implementation, and evidentiary integrity.
2. **Phase 70 does not rebuild or duplicate Phase 69**: Phase 69 evaluates compliance against approved requirements and controls; Phase 70 manages the independent audit lifecycle examining whether governance processes, controls, evidence, and compliance assessments are adequately designed, implemented, documented, and reviewed.
3. **An automated compliance result is not an independent audit conclusion**: Automated checks are potential evidentiary inputs for an auditor; they never substitute for auditor professional skepticism, sampling, and independent conclusion sign-off.
4. **An auditor cannot verify their own independence**: Separation of duties mandates that conflict-of-interest declarations and independence reviews are evaluated and confirmed by an independent governance authority, never by the auditor themselves.
5. **A report author cannot approve their own audit report**: The auditor or lead author who drafted the report is strictly forbidden from executing the governance approval (`REPORT_SELF_APPROVAL_FORBIDDEN`). Independent governance sign-off is mandatory.
6. **An audit cannot be closed without an approved audit report**: Formal audit closure requires that an approved report exists, ensuring closure rationale, findings, and follow-up requirements are formally documented and approved (`AUDIT_CLOSURE_CONDITIONS_UNMET`).
7. **Audit scope freeze protects evidentiary integrity**: Once audit execution commences, the scope is frozen and cannot be silently altered or curtailed to conceal deficiencies; any change requires a formal, traceable amendment workflow (`SCOPE_FROZEN_MODIFICATION_FORBIDDEN`).
8. **Phase 70 does not independently close Phase 54 corrective actions**: Corrective actions generated from audit findings are referred to Phase 54 orchestration and Phase 55 effectiveness evaluation; Phase 70 tracks referral links and follow-up status without usurping Phase 54/55 authority.
9. **An auditee dispute does not erase an observation**: Auditee disputes are recorded with rationale and supporting evidence, but the original observation and dispute stance are immutably preserved in the audit record.
10. **Evidence submission requires provenance verification**: Auditors examine whether evidence is traceable, authenticated, and consistent with operational records, rather than accepting unverified self-assertions.
11. **An internal audit does not constitute statutory regulatory certification or accreditation**: Conclusions rendered are internal governance evaluations, never statutory or regulatory accreditations.
12. **Audit history and provenance are immutable**: Historical audit drafts, test records, observations, and reports are permanently preserved; audit reopening creates controlled lifecycle transitions with full traceability.

---

## 2. Audit Lifecycle States (12 Controlled States)

Phase 70 defines 12 explicit lifecycle states for clinical safety governance audits:

- `DRAFT`: Audit record initialized under an approved audit programme.
- `PENDING_APPROVAL`: Audit charter and proposed scope submitted for governance approval.
- `APPROVED`: Audit scope and charter formally approved by clinical governance authority.
- `SCHEDULED`: Execution timetable and auditor roster finalized.
- `IN_PROGRESS`: Active fieldwork, criteria testing, and evidence collection underway (scope is frozen).
- `PAUSED`: Execution temporarily suspended with documented operational justification.
- `PENDING_REVIEW`: Fieldwork completed; test findings and observations submitted for peer/technical review.
- `REPORT_DRAFT`: Draft audit report compiled from test results and confirmed findings.
- `REPORT_APPROVED`: Report reviewed and approved by independent governance authority (separation of duties enforced).
- `FOLLOW_UP_REQUIRED`: Audit closed conditionally pending remediation of identified high/critical findings.
- `CLOSED`: Audit fully closed following approval of report and resolution/referral of findings.
- `CANCELLED`: Audit cancelled with documented governance rationale; all prior history preserved.

---

## 3. Finding Categories & Severity Tiers

### Finding Categories (10 Categories)
- `CONTROL_GAP`: Required safety or governance control is missing or inadequately designed.
- `PROCESS_DEVIATION`: Governance procedure was not followed as approved.
- `DOCUMENTATION_GAP`: Mandatory clinical safety or risk management documentation is missing or incomplete.
- `EVIDENCE_GAP`: Supporting evidence is insufficient, contradictory, or unverifiable.
- `GOVERNANCE_WEAKNESS`: Structural governance ambiguity, missing approvals, or lack of oversight.
- `AUTHORIZATION_ISSUE`: Actions or decisions executed without verified delegation of authority.
- `TRACEABILITY_GAP`: Decisions, handoffs, or clinical risks cannot be traced end-to-end.
- `REPEAT_FINDING`: Recurrence of a deficiency previously identified in past audits or reviews.
- `POTENTIAL_SYSTEMIC_ISSUE`: Cross-workflow failure pattern indicating organizational or systemic vulnerability.
- `OTHER`: Other governance deficiency requiring controlled follow-up.

### Severity Tiers (5 Tiers)
- `ROUTINE`: Minor administrative or documentation non-conformance.
- `ELEVATED`: Noticeable procedural departure not directly impacting immediate patient safety.
- `HIGH`: Substantial control weakness or missing governance approval requiring corrective action.
- `URGENT`: Severe governance breakdown with potential clinical safety risk requiring rapid remediation.
- `CRITICAL`: Immediate safety compromise, unmanaged safety signal, or critical unauthorized departure.

---

## 4. Auditor Independence & Separation of Duties

### Auditor Roles
- `LEAD_AUDITOR`: Directs audit planning, oversees fieldwork, confirms findings, and compiles reports.
- `SUPPORTING_AUDITOR`: Conducts test procedures, issues evidence requests, and records observations.
- `INDEPENDENT_REVIEWER`: Conducts technical peer review of test procedures and draft reports.
- `SUBJECT_MATTER_EXPERT`: Provides specialist domain review (e.g. pharmacology, clinical safety informatics).
- `AUTHORIZED_OBSERVER`: Oversight representative without operational testing duties.
- `PROGRAMME_OWNER`: Oversees broader audit programme objectives.

### Independence Rules
1. **Self-Review Forbidden**: An assigned auditor cannot review or verify their own independence (`AUDITOR_INDEPENDENCE_CONFLICT`).
2. **Conflict Declaration**: Auditors must declare any past participation in the audited process or facility. Conflicted auditors must have documented mitigations approved or be reassigned.
3. **Report Approval Separation**: The author/creator of an audit report cannot execute the governance approval of that report (`REPORT_SELF_APPROVAL_FORBIDDEN`). Independent sign-off by a separate administrator or doctor is required.

---

## 5. REST API Specification

Base Path: `/api/v1/governance-audits`

### 5.1 Supervisory Queues & Aggregated Reports
- `GET /queues/review-required`: Audits requiring supervisory, peer, or governance review.
- `GET /queues/overdue`: Audits past planned end date that remain open.
- `GET /reports/summary`: High-level metrics across audit programmes, audits, and completion rates.
- `GET /reports/findings`: Aggregated finding metrics by severity, category, confirmation, and closure.
- `GET /reports/overdue`: Overdue audit milestones, evidence requests, and finding responses.
- `GET /reports/follow-up-status`: Monitoring metrics for audits requiring follow-up and active CAPA links.

### 5.2 Programmes
- `POST /programmes`: Create a clinical safety audit programme (`201 Created`).
- `GET /programmes`: List audit programmes within tenant scope.
- `GET /programmes/{programme_id}`: Retrieve programme details.
- `POST /programmes/{programme_id}/approve`: Formally approve audit programme.

### 5.3 Audits Lifecycle
- `POST /audits`: Initiate a clinical safety audit (`201 Created`).
- `GET /audits`: List audits within tenant scope.
- `GET /audits/{audit_id}`: Retrieve audit record.
- `POST /audits/{audit_id}/schedule`: Schedule or start audit execution.
- `POST /audits/{audit_id}/pause`: Pause an in-progress audit with documented reason.
- `POST /audits/{audit_id}/resume`: Resume a paused audit.
- `POST /audits/{audit_id}/cancel`: Cancel an audit with documented reason.
- `POST /audits/{audit_id}/close`: Formally close audit (requires approved report).
- `POST /audits/{audit_id}/reopen`: Reopen closed audit upon new safety signals.

### 5.4 Audit Scope Management
- `POST /audits/{audit_id}/scope`: Establish draft audit scope (`201 Created`).
- `GET /audits/{audit_id}/scope`: Get current audit scope.
- `POST /audits/{audit_id}/scope/approve`: Approve audit scope prior to fieldwork.
- `POST /audits/{audit_id}/scope/amend`: Formally amend approved/frozen scope with version increment.

### 5.5 Auditor Assignment & Independence
- `POST /audits/{audit_id}/assignments`: Assign auditor with conflict declarations (`201 Created`).
- `GET /audits/{audit_id}/assignments`: List active auditor assignments.
- `POST /assignments/{assignment_id}/independence-review`: Review auditor independence (self-review blocked).

### 5.6 Audit Criteria
- `POST /audits/{audit_id}/criteria`: Create criterion mapped to Phase 69 controls (`201 Created`).
- `GET /audits/{audit_id}/criteria`: List criteria for an audit.

### 5.7 Evidence Requests
- `POST /audits/{audit_id}/evidence-requests`: Issue evidence request to an auditee (`201 Created`).
- `GET /audits/{audit_id}/evidence-requests`: List evidence requests.
- `POST /evidence-requests/{request_id}/submit`: Auditee submits evidence references.
- `POST /evidence-requests/{request_id}/review`: Auditor reviews and accepts/rejects evidence.

### 5.8 Audit Tests
- `POST /audits/{audit_id}/tests`: Define audit test procedure (`201 Created`).
- `GET /audits/{audit_id}/tests`: List tests configured for an audit.
- `POST /tests/{test_id}/execute`: Record test observations, evidence refs, and outcome.
- `POST /tests/{test_id}/review`: Peer or supervisory review of test execution.

### 5.9 Findings, Auditee Responses & CAPA Referral
- `POST /audits/{audit_id}/findings`: Record audit finding or observation (`201 Created`).
- `GET /audits/{audit_id}/findings`: List findings for an audit.
- `GET /findings/{finding_id}`: Retrieve finding details.
- `POST /findings/{finding_id}/confirm`: Confirm finding (lead auditor sign-off).
- `POST /findings/{finding_id}/dispute`: Auditee disputes finding with rationale.
- `POST /findings/{finding_id}/responses`: Submit auditee remediation plan (`201 Created`).
- `GET /findings/{finding_id}/responses`: List responses for a finding.
- `POST /findings/responses/{response_id}/review`: Auditor evaluates auditee response.
- `POST /findings/{finding_id}/link-corrective-action`: Link authoritative Phase 54 CAPA reference.

### 5.10 Audit Reports & Governance Approval
- `POST /audits/{audit_id}/reports`: Generate draft audit report (`201 Created`).
- `GET /audits/{audit_id}/reports`: List reports for an audit.
- `GET /reports/{report_id}`: Get audit report details.
- `POST /reports/{report_id}/review`: Peer/technical review of audit report.
- `POST /reports/{report_id}/approve`: Governance approval of report (author self-approval blocked).
