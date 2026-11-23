# Phase 86: Clinical Safety Governance Resilience Resource Dependency Mapping, Critical Resource Availability & Continuity Capacity Assurance

## Executive Overview

Phase 86 introduces a production-grade backend capability for identifying, mapping, monitoring, and assessing the operational resources, systems, facilities, information repositories, communication networks, and third-party dependencies required to sustain critical clinical safety governance capabilities during normal operations and prolonged disruptions.

Building on **Phase 85** (Resilience Role-Coverage Continuity, Succession Readiness & Authorized Backup Coordination) and **Phase 80** (Governance Continuity Operations), Phase 86 shifts governance resilience from personnel availability to the foundational material, infrastructure, and technical dependencies that enable safety governance execution.

---

## 1. Clinical Safety Disclaimer & Governance Boundaries

> [!IMPORTANT]
> **Mandatory Clinical Safety Disclaimer**:
> Resource dependency mapping, availability observations, and continuity capacity assessments are administrative governance instruments and do NOT constitute proof of operational resilience, engineering redundancy, or failover guarantee. Phase 86 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, or 85.

### Strict Governance Invariants:
1. **Administrative Only**: Phase 86 maps and assesses governance resource dependencies; it does **not** automatically activate fallback systems, perform automated DNS cutovers, reboot infrastructure, or alter production runtime configurations.
2. **Availability Rule**:
   - Missing monitoring or telemetry data is strictly treated as `UNKNOWN`, **never** inferred as `AVAILABLE`.
3. **Alternative Resource Rule**:
   - An unverified alternative or plan-only fallback is strictly treated as `UNVERIFIED_FALLBACK` / `INSUFFICIENT_EVIDENCE`, **never** assumed to be operational.
4. **Independence Rule**:
   - Two resources with different names are **not** assumed independent without documented evidence of upstream independence.
5. **Separation of Duties**:
   - A dependency mapping proposer cannot approve their own dependency mapping.
   - Resource gap closures require documented verification evidence (`resolution_evidence_ref`).
6. **No Duplication**:
   - Does not duplicate low-level IT infrastructure APM/asset management tools (e.g. Datadog, ServiceNow CMDB). It specifically tracks *clinical safety governance dependencies*.

---

## 2. Core Architectural Pillars

### 2.1 Critical Governance Resource Inventory
- Catalogs operational resources across 8 categories:
  - `CLINICAL_INFORMATION_SYSTEM`, `INFRASTRUCTURE`, `COMMUNICATION_NETWORK`, `PHYSICAL_FACILITY`, `THIRD_PARTY_SERVICE`, `GOVERNANCE_RECORDS_REPOSITORY`, `SPECIALIZED_EQUIPMENT`, `EXTERNAL_REGULATORY_PORTAL`.
- Assigns criticality tiers: `TIER_1_ESSENTIAL`, `TIER_2_CRITICAL`, `TIER_3_IMPORTANT`, `TIER_4_SUPPORTING`.
- Enforces availability requirement thresholds (hours) and review cycle schedules.
- Full lifecycle governance: `DRAFT`, `ACTIVE`, `DEGRADED`, `UNDER_MAINTENANCE`, `RETIRED`, `DEPRECATED`.

### 2.2 Capability-Resource Dependency Mapping
- Formalizes linkages between governance capabilities (e.g., Clinical Safety Committee Quorum, Safety Incident Escalation, Continuity Recovery Coordination) and underlying resources.
- Supports dependency types: `PRIMARY`, `SECONDARY`, `CONTINGENCY`, `PREREQUISITE`, `UPSTREAM_FEED`.
- Separation of duties enforcement: Approval requires an independent authorized user (`proposer_id != approver_id`).

### 2.3 Operational Telemetry & Availability Observation Ingestion
- Accepts telemetry feeds and manual verification inputs.
- Computes staleness (observations older than 24 hours flagged as `STALE`).
- Detects status conflicts between contradictory telemetry sources within a 1-hour window.
- Returns `UNKNOWN` status whenever telemetry is absent or stale.

### 2.4 Alternative Resources & Fallback Readiness Assessment
- Maps primary resources to designated alternatives with explicit substitution conditions and dependency compatibility checks.
- Disallows circular self-referencing alternatives (`primary_resource_id != alternative_resource_id`).
- Readiness tiers: `READY_VERIFIED`, `READY_UNVERIFIED`, `DEGRADED_FALLBACK`, `INSUFFICIENT_EVIDENCE`, `EXPIRED`, `NOT_ASSESSED`.

### 2.5 Continuity Capacity Requirements & Shortfall Evaluation
- Evaluates operational capacity against defined minimum thresholds (e.g., minimum service capacity %, information accessibility %, max acceptable interruption minutes).
- Calculates capacity shortfall using `verified_capacity_pct` (disallows calculating surplus/deficit from unverified self-reported estimates).
- Categorizes status: `CAPACITY_ADEQUATE`, `CAPACITY_SHORTFALL_DETECTED`, `UNVERIFIED_ESTIMATE_ONLY`, `INSUFFICIENT_EVIDENCE`.

### 2.6 Dependency Graph Analysis & SPOF Identification
- Constructs dependency directed graphs to discover:
  - Shared resource dependencies and concentration risk.
  - Single Points of Failure (SPOFs) supporting multiple capabilities with no verified fallback.
  - Circular dependencies across upstream feeds and prerequisites.
  - Critical paths through the governance capability architecture.

### 2.7 Resource Dependency Gap Management & Escalation
- Identifies and tracks deficits (`UNMAPPED_DEPENDENCY`, `SINGLE_POINT_OF_FAILURE`, `ABSENT_FALLBACK`, `CAPACITY_SHORTFALL`, etc.).
- Coordinates assignments, target dates, and remediation proposals.
- Supports authoritative escalation to Phase 67 (Safety Risk Remediation), Phase 72 (Executive Management Review), or Phase 80 (Continuity Plan Overhaul).
- Requires verification evidence before transition to `VERIFIED_RESOLVED`.

### 2.8 Executive Resilience Reporting
- Provides 5 real-time aggregated governance intelligence reports:
  1. `Resource Coverage Summary Report`: Global inventory counts, active counts, unmapped capabilities.
  2. `Dependency Concentration Report`: High-concentration resources and bottleneck assets.
  3. `Fallback Readiness Report`: Alternative verification coverage and unverified fallbacks.
  4. `Resource Availability Status Report`: Real-time operational statuses, degraded counts, stale telemetry.
  5. `Resource Gaps Summary Report`: Open gaps by severity, status, and escalation pathways.

---

## 3. API Route Directory

Base namespace: `/api/v1/governance-resilience-resource-dependencies`
Protected by router-level non-patient role check: `dependencies=[Depends(_ensure_not_patient)]`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/resources` | Register critical governance resource |
| `GET` | `/resources` | List critical governance resources |
| `GET` | `/resources/{resource_id}` | Get resource details |
| `PUT` | `/resources/{resource_id}` | Update resource attributes |
| `POST` | `/mappings` | Create capability dependency mapping |
| `GET` | `/mappings` | List dependency mappings |
| `GET` | `/mappings/{dependency_id}` | Get dependency mapping details |
| `POST` | `/mappings/{dependency_id}/submit` | Submit mapping for review |
| `POST` | `/mappings/{dependency_id}/approve` | Approve dependency mapping (SoD enforced) |
| `POST` | `/observations` | Record availability observation |
| `GET` | `/resources/{resource_id}/availability` | Get availability summary and status |
| `POST` | `/alternatives` | Register alternative resource mapping |
| `GET` | `/alternatives` | List alternative resources |
| `POST` | `/alternatives/{alternative_id}/assess` | Assess fallback readiness |
| `POST` | `/capacity-requirements` | Define capacity requirement |
| `GET` | `/capacity-requirements` | List capacity requirements |
| `POST` | `/capacity-requirements/{requirement_id}/evaluate` | Evaluate continuity capacity & shortfalls |
| `POST` | `/graph/analyze` | Execute full dependency graph and SPOF analysis |
| `GET` | `/graph/analyses/{analysis_id}` | Retrieve graph analysis results |
| `POST` | `/gaps` | Create resource dependency gap |
| `GET` | `/gaps` | List resource dependency gaps |
| `POST` | `/gaps/{gap_id}/assign` | Assign gap remediation |
| `POST` | `/gaps/{gap_id}/escalate` | Escalate gap to Phase 67/72/80 |
| `POST` | `/gaps/{gap_id}/resolve` | Resolve gap with verified evidence |
| `GET` | `/reports/coverage-summary` | Executive resource coverage report |
| `GET` | `/reports/concentration` | Dependency concentration report |
| `GET` | `/reports/fallback-readiness` | Fallback readiness report |
| `GET` | `/reports/availability-status` | Real-time availability status report |
| `GET` | `/reports/gaps-summary` | Resource gaps summary report |
