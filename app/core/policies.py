"""Centralized policy registry for HealthSetu authorization.

DATABASE TEAM DEPENDENCY — PHASE 3
===================================
The policy definitions here are the backend's source of truth for
what actions are CONCEPTUALLY supported. When the Database Team delivers
a dynamic permission/role-permission table, this registry can be replaced
or supplemented by database-driven policy lookup via PermissionRepository.

DESIGN PRINCIPLES
=================
- Do NOT scatter permission strings across route handlers.
- All permission identifiers live here; routes reference them by constant.
- Deny by default: any action NOT in a role's policy set is DENIED.
- Admin permissions ≠ clinical access (admin:user_manage ≠ clinical_record:read).
- Role → Permission mapping is additive, not hierarchical by default.
"""

from enum import Enum
from typing import FrozenSet


# ---------------------------------------------------------------------------
# Permission Constants
# ---------------------------------------------------------------------------

class Permission(str, Enum):
    """Canonical permission identifiers.

    Format: "<resource>:<action>"

    New permissions must be added here and assigned to at least one role
    before routes can use them. Never create permission strings inline.
    """

    # ---- Patient self-access ----
    PATIENT_READ_SELF = "patient:read_self"
    PATIENT_UPDATE_SELF = "patient:update_self"

    # ---- Clinical records (requires relationship + consent checks) ----
    CLINICAL_RECORD_READ = "clinical_record:read"
    CLINICAL_RECORD_CREATE = "clinical_record:create"
    CLINICAL_RECORD_UPDATE = "clinical_record:update"

    # ---- Clinical history (Phase 4) ----
    CLINICAL_HISTORY_READ = "clinical_history:read"
    CLINICAL_HISTORY_CREATE = "clinical_history:create"
    CLINICAL_HISTORY_UPDATE = "clinical_history:update"

    # ---- Allergies (Phase 4) ----
    ALLERGY_READ = "allergy:read"
    ALLERGY_CREATE = "allergy:create"
    ALLERGY_UPDATE = "allergy:update"

    # ---- Vitals (Phase 4) ----
    VITAL_READ = "vital:read"
    VITAL_CREATE = "vital:create"

    # ---- Encounters (Phase 4) ----
    ENCOUNTER_READ = "encounter:read"
    ENCOUNTER_CREATE = "encounter:create"

    # ---- Clinical summary (Phase 4) ----
    CLINICAL_SUMMARY_READ = "clinical_summary:read"

    # ---- Medical Documents (Phase 5) ----
    DOCUMENT_READ = "document:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_PROCESS = "document:process"
    DOCUMENT_ARCHIVE = "document:archive"
    DOCUMENT_EXTRACTION_READ = "document_extraction:read"

    # ---- Prescriptions ----
    PRESCRIPTION_READ = "prescription:read"
    PRESCRIPTION_CREATE = "prescription:create"
    PRESCRIPTION_NORMALIZE = "prescription:normalize"

    # ---- Medications ----
    MEDICATION_READ = "medication:read"
    MEDICATION_UPDATE = "medication:update"

    # ---- Medication Safety (Phase 7) ----
    MEDICATION_SAFETY_READ = "medication_safety:read"
    MEDICATION_SAFETY_CHECK = "medication_safety:check"

    # ---- Symptoms, Triage & SBAR (Phase 8) ----
    SYMPTOM_READ = "symptom:read"
    SYMPTOM_CREATE = "symptom:create"
    TRIAGE_READ = "triage:read"
    TRIAGE_ASSESS = "triage:assess"
    SBAR_READ = "sbar:read"
    SBAR_CREATE = "sbar:create"

    # ---- Care plans & Discharge (Phase 9) ----
    CARE_PLAN_READ = "care_plan:read"
    CARE_PLAN_CREATE = "care_plan:create"
    CARE_PLAN_UPDATE = "care_plan:update"
    DISCHARGE_EXTRACT = "discharge:extract"
    DISCHARGE_VERIFY = "discharge:verify"
    DISCHARGE_READ = "discharge:read"

    # ---- Doctor Clinical Workflow (Phase 10) ----
    CLINICAL_NOTE_READ = "clinical_note:read"
    CLINICAL_NOTE_CREATE = "clinical_note:create"
    CLINICAL_NOTE_UPDATE = "clinical_note:update"
    CLINICAL_NOTE_SIGN = "clinical_note:sign"
    CLINICAL_ASSESSMENT_READ = "clinical_assessment:read"
    CLINICAL_ASSESSMENT_CREATE = "clinical_assessment:create"
    CLINICAL_ASSESSMENT_UPDATE = "clinical_assessment:update"
    CLINICAL_ASSESSMENT_FINALIZE = "clinical_assessment:finalize"
    CLINICAL_PLAN_READ = "clinical_plan:read"
    CLINICAL_PLAN_CREATE = "clinical_plan:create"
    CLINICAL_PLAN_UPDATE = "clinical_plan:update"
    CLINICAL_PLAN_FINALIZE = "clinical_plan:finalize"
    CLINICAL_WORKSPACE_READ = "clinical_workspace:read"

    # ---- Organization, Facility & Department (Phase 11) ----
    ORGANIZATION_READ = "organization:read"
    FACILITY_READ = "facility:read"
    DEPARTMENT_READ = "department:read"
    CLINICIAN_NETWORK_READ = "clinician_network:read"

    # ---- Facility Discovery & Transfer (Phase 12) ----
    FACILITY_DISCOVER = "facility:discover"
    TRANSFER_CREATE = "transfer:create"
    TRANSFER_READ = "transfer:read"
    TRANSFER_UPDATE_STATUS = "transfer:update_status"

    # ---- Interoperability & Healthcare Data Exchange (Phase 13) ----
    INTEROPERABILITY_IMPORT = "interoperability:import"
    INTEROPERABILITY_EXPORT = "interoperability:export"
    INTEROPERABILITY_READ = "interoperability:read"

    # ---- AI & Intelligence Layer (Phase 14) ----
    AI_EXECUTE = "ai:execute"
    AI_READ = "ai:read"
    AI_VERIFY = "ai:verify"

    # ---- Consent lifecycle ----
    CONSENT_CREATE = "consent:create"
    CONSENT_READ = "consent:read"
    CONSENT_REVOKE = "consent:revoke"

    # ---- Admin user management (does NOT imply clinical access) ----
    ADMIN_USER_MANAGE = "admin:user_manage"
    ADMIN_AUDIT_READ = "admin:audit_read"

    # ---- Phase 24: Advanced Data Privacy, Retention & Governance ----
    DATA_EXPORT_REQUEST = "data_export:request"
    DATA_EXPORT_READ = "data_export:read"
    DATA_EXPORT_DOWNLOAD = "data_export:download"
    PRIVACY_POLICY_READ = "privacy_policy:read"
    PRIVACY_ADMIN = "privacy:admin"
    RETENTION_MANAGE = "retention:manage"
    RETENTION_READ = "retention:read"
    DELETION_MANAGE = "deletion:manage"
    DEIDENTIFICATION_EXECUTE = "deidentification:execute"
    PSEUDONYMIZATION_EXECUTE = "pseudonymization:execute"

    # ---- Phase 25: Feature Flags, Configuration Governance & Rollout ----
    CONFIGURATION_READ = "configuration:read"
    CONFIGURATION_MANAGE = "configuration:manage"
    FEATURE_FLAG_READ = "feature_flag:read"
    FEATURE_FLAG_MANAGE = "feature_flag:manage"
    KILL_SWITCH_MANAGE = "kill_switch:manage"

    # ---- Phase 26: Data Quality, Clinical Record Integrity & Reconciliation ----
    DATA_QUALITY_READ = "data_quality:read"
    DATA_QUALITY_CHECK = "data_quality:check"
    DATA_QUALITY_REVIEW = "data_quality:review"
    DATA_QUALITY_RESOLVE = "data_quality:resolve"
    RECONCILIATION_READ = "reconciliation:read"
    RECONCILIATION_EXECUTE = "reconciliation:execute"
    RECONCILIATION_RESOLVE = "reconciliation:resolve"

    # ---- Phase 27: Administration, Support Operations & Backoffice ----
    ADMIN_SYSTEM_VIEW = "admin:system_view"
    ADMIN_SYSTEM_MANAGE = "admin:system_manage"
    ADMIN_USERS_VIEW = "admin:users_view"
    ADMIN_USERS_MANAGE = "admin:users_manage"
    ADMIN_JOBS_VIEW = "admin:jobs_view"
    ADMIN_JOBS_MANAGE = "admin:jobs_manage"
    ADMIN_INTEGRATIONS_VIEW = "admin:integrations_view"
    ADMIN_INCIDENTS_VIEW = "admin:incidents_view"
    ADMIN_INCIDENTS_MANAGE = "admin:incidents_manage"
    ADMIN_AUDIT_VIEW = "admin:audit_view"
    ADMIN_SECURITY_VIEW = "admin:security_view"
    ADMIN_CONFIGURATION_VIEW = "admin:configuration_view"
    ADMIN_CONFIGURATION_MANAGE = "admin:configuration_manage"
    ADMIN_SUPPORT_VIEW = "admin:support_view"
    ADMIN_SUPPORT_MANAGE = "admin:support_manage"

    # ---- Phase 28: API Analytics, Usage Governance & Operational Intelligence ----
    ADMIN_ANALYTICS_VIEW = "admin:analytics_view"
    ORGANIZATION_ANALYTICS_VIEW = "organization:analytics_view"
    FACILITY_ANALYTICS_VIEW = "facility:analytics_view"

    # ---- Phase 29: Notification, Communication & Event Delivery System ----
    NOTIFICATION_READ = "notification:read"
    NOTIFICATION_DISMISS = "notification:dismiss"
    NOTIFICATION_CREATE = "notification:create"
    NOTIFICATION_MANAGE = "notification:manage"
    NOTIFICATION_PREFERENCE_READ = "notification_preference:read"
    NOTIFICATION_PREFERENCE_MANAGE = "notification_preference:manage"
    ADMIN_NOTIFICATION_VIEW = "admin:notification_view"
    ADMIN_NOTIFICATION_MANAGE = "admin:notification_manage"
    ADMIN_NOTIFICATION_PROVIDER_TEST = "admin:notification_provider_test"

    # ---- Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval ----
    SEARCH_EXECUTE = "search:execute"
    SEARCH_PATIENT = "search:patient"
    SEARCH_CLINICAL = "search:clinical"
    SEARCH_DOCUMENT = "search:document"
    SEARCH_FACILITY = "search:facility"
    SEARCH_ORGANIZATION = "search:organization"
    ADMIN_SEARCH_VIEW = "admin:search_view"
    ADMIN_SEARCH_MANAGE = "admin:search_manage"

    # ---- Phase 31: Scheduling, Appointment & Clinical Access Management ----
    APPOINTMENT_READ = "appointment:read"
    APPOINTMENT_CREATE = "appointment:create"
    APPOINTMENT_UPDATE = "appointment:update"
    APPOINTMENT_CANCEL = "appointment:cancel"
    APPOINTMENT_RESCHEDULE = "appointment:reschedule"
    APPOINTMENT_CHECK_IN = "appointment:check_in"
    AVAILABILITY_READ = "availability:read"
    SCHEDULE_MANAGE = "schedule:manage"
    ADMIN_SCHEDULING_VIEW = "admin:scheduling_view"
    ADMIN_SCHEDULING_MANAGE = "admin:scheduling_manage"

    # ---- Phase 32: Billing, Payments & Financial Transaction Management ----
    INVOICE_READ = "invoice:read"
    INVOICE_CREATE = "invoice:create"
    INVOICE_UPDATE = "invoice:update"
    INVOICE_ISSUE = "invoice:issue"
    INVOICE_CANCEL = "invoice:cancel"
    PAYMENT_READ = "payment:read"
    PAYMENT_CREATE = "payment:create"
    PAYMENT_REFUND = "payment:refund"
    ADMIN_BILLING_VIEW = "admin:billing_view"
    ADMIN_BILLING_MANAGE = "admin:billing_manage"
    ADMIN_PAYMENT_VIEW = "admin:payment_view"
    ADMIN_PAYMENT_RECONCILE = "admin:payment_reconcile"
    ADMIN_REFUND_MANAGE = "admin:refund_manage"

    # ---- Phase 33: Insurance, Claims & Payer Integration ----
    INSURANCE_READ = "insurance:read"
    INSURANCE_CREATE = "insurance:create"
    INSURANCE_UPDATE = "insurance:update"
    INSURANCE_VERIFY = "insurance:verify"
    ELIGIBILITY_CHECK = "eligibility:check"
    BENEFITS_READ = "benefits:read"
    AUTHORIZATION_READ = "authorization:read"
    AUTHORIZATION_CREATE = "authorization:create"
    AUTHORIZATION_UPDATE = "authorization:update"
    AUTHORIZATION_SUBMIT = "authorization:submit"
    CLAIM_READ = "claim:read"
    CLAIM_CREATE = "claim:create"
    CLAIM_UPDATE = "claim:update"
    CLAIM_SUBMIT = "claim:submit"
    CLAIM_RECONCILE = "claim:reconcile"
    ADMIN_INSURANCE_VIEW = "admin:insurance_view"
    ADMIN_INSURANCE_MANAGE = "admin:insurance_manage"
    ADMIN_ELIGIBILITY_VIEW = "admin:eligibility_view"
    ADMIN_ELIGIBILITY_MANAGE = "admin:eligibility_manage"
    ADMIN_AUTHORIZATION_VIEW = "admin:authorization_view"
    ADMIN_AUTHORIZATION_MANAGE = "admin:authorization_manage"
    ADMIN_CLAIMS_VIEW = "admin:claims_view"
    ADMIN_CLAIMS_MANAGE = "admin:claims_manage"
    ADMIN_CLAIM_RECONCILE = "admin:claim_reconcile"
    ADMIN_PAYER_VIEW = "admin:payer_view"
    ADMIN_PAYER_MANAGE = "admin:payer_manage"
    ADMIN_PAYER_TEST = "admin:payer_test"

    # ---- Phase 34: Laboratory, Diagnostic Orders & Result Management ----
    DIAGNOSTIC_CATALOG_READ = "diagnostic_catalog:read"
    DIAGNOSTIC_ORDER_READ = "diagnostic_order:read"
    DIAGNOSTIC_ORDER_CREATE = "diagnostic_order:create"
    DIAGNOSTIC_ORDER_CANCEL = "diagnostic_order:cancel"
    DIAGNOSTIC_RESULT_READ = "diagnostic_result:read"
    DIAGNOSTIC_RESULT_VERIFY = "diagnostic_result:verify"
    DIAGNOSTIC_REPORT_READ = "diagnostic_report:read"
    DIAGNOSTIC_REPORT_CREATE = "diagnostic_report:create"
    ADMIN_DIAGNOSTICS_VIEW = "admin:diagnostics_view"
    ADMIN_DIAGNOSTICS_MANAGE = "admin:diagnostics_manage"
    ADMIN_DIAGNOSTIC_ORDERS_VIEW = "admin:diagnostic_orders_view"
    ADMIN_DIAGNOSTIC_ORDERS_MANAGE = "admin:diagnostic_orders_manage"
    ADMIN_DIAGNOSTIC_RESULTS_VIEW = "admin:diagnostic_results_view"
    ADMIN_DIAGNOSTIC_RESULTS_MANAGE = "admin:diagnostic_results_manage"
    ADMIN_DIAGNOSTIC_RECONCILIATION = "admin:diagnostic_reconciliation"
    ADMIN_DIAGNOSTIC_PROVIDER_VIEW = "admin:diagnostic_provider_view"
    ADMIN_DIAGNOSTIC_PROVIDER_TEST = "admin:diagnostic_provider_test"

    # ---- Phase 35: Clinical Alerts, Safety Notifications & Escalation Management ----
    ALERT_READ = "alert:read"
    ALERT_ACKNOWLEDGE = "alert:acknowledge"
    ALERT_RESOLVE = "alert:resolve"
    ALERT_DISMISS = "alert:dismiss"
    ALERT_ESCALATE = "alert:escalate"
    ALERT_POLICY_READ = "alert_policy:read"
    ADMIN_ALERTS_VIEW = "admin:alerts_view"
    ADMIN_ALERTS_MANAGE = "admin:alerts_manage"
    ADMIN_ALERT_POLICIES_MANAGE = "admin:alert_policies_manage"
    ADMIN_ALERT_ESCALATION_MANAGE = "admin:alert_escalation_manage"

    # ---- Phase 36: Clinical Tasks, Work Queues & Action Management ----
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_ASSIGN = "task:assign"
    TASK_ACCEPT = "task:accept"
    TASK_START = "task:start"
    TASK_COMPLETE = "task:complete"
    TASK_VERIFY = "task:verify"
    TASK_REJECT = "task:reject"
    TASK_CANCEL = "task:cancel"
    ADMIN_TASKS_VIEW = "admin:tasks_view"
    ADMIN_TASKS_MANAGE = "admin:tasks_manage"

    # ---- Phase 37: Clinical Workflow Orchestration, Order Management & Controlled Action Chains ----
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_APPROVE = "workflow:approve"
    WORKFLOW_PAUSE = "workflow:pause"
    WORKFLOW_RESUME = "workflow:resume"
    WORKFLOW_CANCEL = "workflow:cancel"
    ADMIN_WORKFLOWS_VIEW = "admin:workflows_view"
    ADMIN_WORKFLOWS_MANAGE = "admin:workflows_manage"


# ---------------------------------------------------------------------------
# Role-to-Permission Mapping
# ---------------------------------------------------------------------------
# IMPORTANT:
# - This is the STATIC default policy. Database-driven overrides are
#   a future Phase 3+ enhancement.
# - Permissions are additive; a role only has what is explicitly listed.
# - ADMIN role has administrative capabilities; it does NOT automatically
#   receive clinical_record:read or prescription:create etc.
# - DOCTOR permissions for clinical data are gated behind relationship +
#   consent checks at the service layer — having the permission here is a
#   necessary but NOT sufficient condition for access.

ROLE_PERMISSIONS: dict[str, FrozenSet[Permission]] = {
    "PATIENT": frozenset({
        Permission.PATIENT_READ_SELF,
        Permission.PATIENT_UPDATE_SELF,
        Permission.CLINICAL_RECORD_READ,      # own records only — ownership enforced in service
        Permission.CLINICAL_HISTORY_READ,     # own history
        Permission.CLINICAL_HISTORY_CREATE,   # can add own history entries
        Permission.ALLERGY_READ,
        Permission.ALLERGY_CREATE,
        Permission.VITAL_READ,
        Permission.VITAL_CREATE,              # patient-reported vitals
        Permission.ENCOUNTER_READ,
        Permission.CLINICAL_SUMMARY_READ,
        Permission.DOCUMENT_READ,             # own documents
        Permission.DOCUMENT_UPLOAD,           # can upload own documents
        Permission.DOCUMENT_PROCESS,          # can retry own processing
        Permission.DOCUMENT_ARCHIVE,          # can archive own documents
        Permission.DOCUMENT_EXTRACTION_READ,  # can read extractions from own documents
        Permission.PRESCRIPTION_READ,
        Permission.MEDICATION_READ,
        Permission.MEDICATION_UPDATE,
        Permission.MEDICATION_SAFETY_READ,
        Permission.MEDICATION_SAFETY_CHECK,
        Permission.SYMPTOM_READ,
        Permission.SYMPTOM_CREATE,
        Permission.TRIAGE_READ,
        Permission.TRIAGE_ASSESS,
        Permission.SBAR_READ,
        Permission.CARE_PLAN_READ,
        Permission.CARE_PLAN_UPDATE,
        Permission.DISCHARGE_EXTRACT,
        Permission.DISCHARGE_READ,
        Permission.CLINICAL_NOTE_READ,          # own notes authored by clinician
        Permission.CLINICAL_ASSESSMENT_READ,    # own assessments
        Permission.CLINICAL_PLAN_READ,          # own plans
        Permission.CONSENT_CREATE,
        Permission.CONSENT_READ,
        Permission.CONSENT_REVOKE,
        # Organization network
        Permission.ORGANIZATION_READ,
        Permission.FACILITY_READ,
        Permission.DEPARTMENT_READ,
        # Phase 12: Discovery & Transfer
        Permission.FACILITY_DISCOVER,
        Permission.TRANSFER_CREATE,
        Permission.TRANSFER_READ,
        # Phase 13: Interoperability
        Permission.INTEROPERABILITY_EXPORT,
        Permission.INTEROPERABILITY_READ,
        # Phase 14: AI & Intelligence Layer
        Permission.AI_EXECUTE,
        Permission.AI_READ,
        # Phase 24: Advanced Data Privacy
        Permission.DATA_EXPORT_REQUEST,
        Permission.DATA_EXPORT_READ,
        Permission.DATA_EXPORT_DOWNLOAD,
        Permission.PRIVACY_POLICY_READ,
        # Phase 25: Feature Flags & Configuration
        Permission.FEATURE_FLAG_READ,
        # Phase 26: Data Quality & Reconciliation
        Permission.DATA_QUALITY_READ,
        Permission.RECONCILIATION_READ,
        # Phase 29: Notifications
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_DISMISS,
        Permission.NOTIFICATION_PREFERENCE_READ,
        Permission.NOTIFICATION_PREFERENCE_MANAGE,
        # Phase 30: Authorized Search
        Permission.SEARCH_EXECUTE,
        Permission.SEARCH_FACILITY,
        Permission.SEARCH_ORGANIZATION,
        # Phase 31: Scheduling & Appointments
        Permission.APPOINTMENT_READ,
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_CANCEL,
        Permission.APPOINTMENT_RESCHEDULE,
        Permission.AVAILABILITY_READ,
        # Phase 32: Billing & Payments
        Permission.INVOICE_READ,
        Permission.INVOICE_CREATE,
        Permission.INVOICE_UPDATE,
        Permission.INVOICE_ISSUE,
        Permission.INVOICE_CANCEL,
        Permission.PAYMENT_READ,
        Permission.PAYMENT_CREATE,
        # Phase 33: Insurance, Claims & Benefits (Patient Self-Service)
        Permission.INSURANCE_READ,
        Permission.INSURANCE_CREATE,
        Permission.INSURANCE_UPDATE,
        Permission.ELIGIBILITY_CHECK,
        Permission.BENEFITS_READ,
        Permission.AUTHORIZATION_READ,
        Permission.AUTHORIZATION_CREATE,
        Permission.CLAIM_READ,
        Permission.CLAIM_CREATE,
        Permission.CLAIM_SUBMIT,
        # Phase 34: Laboratory, Diagnostic Orders & Result Management
        Permission.DIAGNOSTIC_ORDER_READ,
        Permission.DIAGNOSTIC_RESULT_READ,
        Permission.DIAGNOSTIC_REPORT_READ,
        # Phase 35: Clinical Alerts & Notifications (Patient-facing)
        Permission.ALERT_READ,
        Permission.ALERT_ACKNOWLEDGE,
        # Phase 36: Clinical Tasks (Patient-facing)
        Permission.TASK_READ,
        # Phase 37: Clinical Workflows (Patient-facing)
        Permission.WORKFLOW_READ,
    }),
    "DOCTOR": frozenset({
        Permission.PATIENT_READ_SELF,         # can read patient profile in context
        Permission.CLINICAL_RECORD_READ,      # gated by relationship + consent
        Permission.CLINICAL_RECORD_CREATE,
        Permission.CLINICAL_RECORD_UPDATE,
        Permission.CLINICAL_HISTORY_READ,
        Permission.CLINICAL_HISTORY_CREATE,
        Permission.CLINICAL_HISTORY_UPDATE,
        Permission.ALLERGY_READ,
        Permission.ALLERGY_CREATE,
        Permission.ALLERGY_UPDATE,
        Permission.VITAL_READ,
        Permission.VITAL_CREATE,
        Permission.ENCOUNTER_READ,
        Permission.ENCOUNTER_CREATE,
        Permission.CLINICAL_SUMMARY_READ,
        Permission.DOCUMENT_READ,             # gated by relationship + consent
        Permission.DOCUMENT_UPLOAD,           # clinician document upload
        Permission.DOCUMENT_PROCESS,          # retry / trigger processing
        Permission.DOCUMENT_ARCHIVE,
        Permission.DOCUMENT_EXTRACTION_READ,  # view extraction results
        Permission.PRESCRIPTION_READ,
        Permission.PRESCRIPTION_CREATE,
        Permission.PRESCRIPTION_NORMALIZE,
        Permission.MEDICATION_READ,
        Permission.MEDICATION_UPDATE,
        Permission.MEDICATION_SAFETY_READ,
        Permission.MEDICATION_SAFETY_CHECK,
        Permission.SYMPTOM_READ,
        Permission.SYMPTOM_CREATE,
        Permission.TRIAGE_READ,
        Permission.TRIAGE_ASSESS,
        Permission.SBAR_READ,
        Permission.SBAR_CREATE,
        Permission.CARE_PLAN_READ,
        Permission.CARE_PLAN_CREATE,
        Permission.CARE_PLAN_UPDATE,
        Permission.DISCHARGE_EXTRACT,
        Permission.DISCHARGE_VERIFY,
        Permission.DISCHARGE_READ,
        Permission.CLINICAL_NOTE_READ,
        Permission.CLINICAL_NOTE_CREATE,
        Permission.CLINICAL_NOTE_UPDATE,
        Permission.CLINICAL_NOTE_SIGN,
        Permission.CLINICAL_ASSESSMENT_READ,
        Permission.CLINICAL_ASSESSMENT_CREATE,
        Permission.CLINICAL_ASSESSMENT_UPDATE,
        Permission.CLINICAL_ASSESSMENT_FINALIZE,
        Permission.CLINICAL_PLAN_READ,
        Permission.CLINICAL_PLAN_CREATE,
        Permission.CLINICAL_PLAN_UPDATE,
        Permission.CLINICAL_PLAN_FINALIZE,
        Permission.CLINICAL_WORKSPACE_READ,
        Permission.CONSENT_READ,
        # Organization network
        Permission.ORGANIZATION_READ,
        Permission.FACILITY_READ,
        Permission.DEPARTMENT_READ,
        Permission.CLINICIAN_NETWORK_READ,
        # Phase 12: Discovery & Transfer
        Permission.FACILITY_DISCOVER,
        Permission.TRANSFER_CREATE,
        Permission.TRANSFER_READ,
        Permission.TRANSFER_UPDATE_STATUS,
        # Phase 13: Interoperability
        Permission.INTEROPERABILITY_IMPORT,
        Permission.INTEROPERABILITY_EXPORT,
        Permission.INTEROPERABILITY_READ,
        # Phase 14: AI & Intelligence Layer
        Permission.AI_EXECUTE,
        Permission.AI_READ,
        Permission.AI_VERIFY,
        # Phase 24: Advanced Data Privacy
        Permission.PRIVACY_POLICY_READ,
        Permission.DATA_EXPORT_READ,
        # Phase 25: Feature Flags & Configuration
        Permission.FEATURE_FLAG_READ,
        Permission.CONFIGURATION_READ,
        # Phase 26: Data Quality & Reconciliation
        Permission.DATA_QUALITY_READ,
        Permission.DATA_QUALITY_CHECK,
        Permission.DATA_QUALITY_REVIEW,
        Permission.DATA_QUALITY_RESOLVE,
        Permission.RECONCILIATION_READ,
        Permission.RECONCILIATION_EXECUTE,
        Permission.RECONCILIATION_RESOLVE,
        # Phase 28: Analytics
        Permission.ORGANIZATION_ANALYTICS_VIEW,
        Permission.FACILITY_ANALYTICS_VIEW,
        # Phase 29: Notifications
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_DISMISS,
        Permission.NOTIFICATION_CREATE,
        Permission.NOTIFICATION_PREFERENCE_READ,
        Permission.NOTIFICATION_PREFERENCE_MANAGE,
        # Phase 30: Authorized Search
        Permission.SEARCH_EXECUTE,
        Permission.SEARCH_PATIENT,
        Permission.SEARCH_CLINICAL,
        Permission.SEARCH_DOCUMENT,
        Permission.SEARCH_FACILITY,
        Permission.SEARCH_ORGANIZATION,
        # Phase 31: Scheduling & Appointments
        Permission.APPOINTMENT_READ,
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_UPDATE,
        Permission.APPOINTMENT_CANCEL,
        Permission.APPOINTMENT_RESCHEDULE,
        Permission.APPOINTMENT_CHECK_IN,
        Permission.AVAILABILITY_READ,
        Permission.SCHEDULE_MANAGE,
        # Phase 32: Billing & Payments
        Permission.INVOICE_READ,
        # Phase 33: Insurance & Clinical Prior Auth
        Permission.INSURANCE_READ,
        Permission.ELIGIBILITY_CHECK,
        Permission.BENEFITS_READ,
        Permission.AUTHORIZATION_READ,
        Permission.AUTHORIZATION_CREATE,
        Permission.AUTHORIZATION_UPDATE,
        Permission.AUTHORIZATION_SUBMIT,
        Permission.CLAIM_READ,
        # Phase 34: Laboratory, Diagnostic Orders & Result Management
        Permission.DIAGNOSTIC_CATALOG_READ,
        Permission.DIAGNOSTIC_ORDER_READ,
        Permission.DIAGNOSTIC_ORDER_CREATE,
        Permission.DIAGNOSTIC_ORDER_CANCEL,
        Permission.DIAGNOSTIC_RESULT_READ,
        Permission.DIAGNOSTIC_RESULT_VERIFY,
        Permission.DIAGNOSTIC_REPORT_READ,
        Permission.DIAGNOSTIC_REPORT_CREATE,
        # Phase 35: Clinical Alerts, Safety Notifications & Escalation Management
        Permission.ALERT_READ,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.ALERT_DISMISS,
        Permission.ALERT_POLICY_READ,
        # Phase 36: Clinical Tasks, Work Queues & Action Management
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_ASSIGN,
        Permission.TASK_ACCEPT,
        Permission.TASK_START,
        Permission.TASK_COMPLETE,
        Permission.TASK_VERIFY,
        Permission.TASK_REJECT,
        Permission.TASK_CANCEL,
        # Phase 37: Clinical Workflows
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_EXECUTE,
        Permission.WORKFLOW_APPROVE,
        Permission.WORKFLOW_PAUSE,
        Permission.WORKFLOW_RESUME,
        Permission.WORKFLOW_CANCEL,
    }),
    "ADMIN": frozenset({
        # Administrative capabilities ONLY — no automatic clinical data access
        Permission.ADMIN_USER_MANAGE,
        Permission.ADMIN_AUDIT_READ,
        Permission.CONSENT_READ,
        # Organization network administration/read
        Permission.ORGANIZATION_READ,
        Permission.FACILITY_READ,
        Permission.DEPARTMENT_READ,
        Permission.CLINICIAN_NETWORK_READ,
        # Phase 12: Discovery & Transfer administration
        Permission.FACILITY_DISCOVER,
        Permission.TRANSFER_READ,
        # Phase 13: Interoperability
        Permission.INTEROPERABILITY_IMPORT,
        Permission.INTEROPERABILITY_EXPORT,
        Permission.INTEROPERABILITY_READ,
        # Phase 14: AI & Intelligence Layer
        Permission.AI_READ,
        # Phase 24: Advanced Data Privacy & Governance
        Permission.PRIVACY_POLICY_READ,
        Permission.PRIVACY_ADMIN,
        Permission.RETENTION_MANAGE,
        Permission.RETENTION_READ,
        Permission.DELETION_MANAGE,
        Permission.DEIDENTIFICATION_EXECUTE,
        Permission.PSEUDONYMIZATION_EXECUTE,
        Permission.DATA_EXPORT_READ,
        # Phase 25: Feature Flags, Configuration Governance & Rollout
        Permission.CONFIGURATION_READ,
        Permission.CONFIGURATION_MANAGE,
        Permission.FEATURE_FLAG_READ,
        Permission.FEATURE_FLAG_MANAGE,
        Permission.KILL_SWITCH_MANAGE,
        # Phase 26: Data Quality, Clinical Record Integrity & Reconciliation
        Permission.DATA_QUALITY_READ,
        Permission.DATA_QUALITY_CHECK,
        Permission.DATA_QUALITY_REVIEW,
        Permission.DATA_QUALITY_RESOLVE,
        Permission.RECONCILIATION_READ,
        Permission.RECONCILIATION_EXECUTE,
        Permission.RECONCILIATION_RESOLVE,
        # Phase 27: Administration, Support Operations & Backoffice
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_SYSTEM_MANAGE,
        Permission.ADMIN_USERS_VIEW,
        Permission.ADMIN_USERS_MANAGE,
        Permission.ADMIN_JOBS_VIEW,
        Permission.ADMIN_JOBS_MANAGE,
        Permission.ADMIN_INTEGRATIONS_VIEW,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.ADMIN_AUDIT_VIEW,
        Permission.ADMIN_SECURITY_VIEW,
        Permission.ADMIN_CONFIGURATION_VIEW,
        Permission.ADMIN_CONFIGURATION_MANAGE,
        Permission.ADMIN_SUPPORT_VIEW,
        Permission.ADMIN_SUPPORT_MANAGE,
        # Phase 28: Analytics
        Permission.ADMIN_ANALYTICS_VIEW,
        Permission.ORGANIZATION_ANALYTICS_VIEW,
        Permission.FACILITY_ANALYTICS_VIEW,
        # Phase 29: Notifications
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_DISMISS,
        Permission.NOTIFICATION_CREATE,
        Permission.NOTIFICATION_PREFERENCE_READ,
        Permission.NOTIFICATION_PREFERENCE_MANAGE,
        Permission.ADMIN_NOTIFICATION_VIEW,
        Permission.ADMIN_NOTIFICATION_MANAGE,
        Permission.ADMIN_NOTIFICATION_PROVIDER_TEST,
        # Phase 30: Authorized Search & Admin Operations
        Permission.SEARCH_EXECUTE,
        Permission.SEARCH_FACILITY,
        Permission.SEARCH_ORGANIZATION,
        Permission.ADMIN_SEARCH_VIEW,
        Permission.ADMIN_SEARCH_MANAGE,
        # Phase 31: Scheduling & Appointments
        Permission.APPOINTMENT_READ,
        Permission.AVAILABILITY_READ,
        Permission.SCHEDULE_MANAGE,
        Permission.ADMIN_SCHEDULING_VIEW,
        Permission.ADMIN_SCHEDULING_MANAGE,
        # Phase 32: Billing & Payments Admin
        Permission.INVOICE_READ,
        Permission.INVOICE_CREATE,
        Permission.INVOICE_UPDATE,
        Permission.INVOICE_ISSUE,
        Permission.INVOICE_CANCEL,
        Permission.PAYMENT_READ,
        Permission.PAYMENT_CREATE,
        Permission.PAYMENT_REFUND,
        Permission.ADMIN_BILLING_VIEW,
        Permission.ADMIN_BILLING_MANAGE,
        Permission.ADMIN_PAYMENT_VIEW,
        Permission.ADMIN_PAYMENT_RECONCILE,
        Permission.ADMIN_REFUND_MANAGE,
        # Phase 33: Insurance & Claims Admin
        Permission.INSURANCE_READ,
        Permission.INSURANCE_CREATE,
        Permission.INSURANCE_UPDATE,
        Permission.INSURANCE_VERIFY,
        Permission.ELIGIBILITY_CHECK,
        Permission.BENEFITS_READ,
        Permission.AUTHORIZATION_READ,
        Permission.AUTHORIZATION_CREATE,
        Permission.AUTHORIZATION_UPDATE,
        Permission.AUTHORIZATION_SUBMIT,
        Permission.CLAIM_READ,
        Permission.CLAIM_CREATE,
        Permission.CLAIM_UPDATE,
        Permission.CLAIM_SUBMIT,
        Permission.CLAIM_RECONCILE,
        Permission.ADMIN_INSURANCE_VIEW,
        Permission.ADMIN_INSURANCE_MANAGE,
        Permission.ADMIN_ELIGIBILITY_VIEW,
        Permission.ADMIN_ELIGIBILITY_MANAGE,
        Permission.ADMIN_AUTHORIZATION_VIEW,
        Permission.ADMIN_AUTHORIZATION_MANAGE,
        Permission.ADMIN_CLAIMS_VIEW,
        Permission.ADMIN_CLAIMS_MANAGE,
        Permission.ADMIN_CLAIM_RECONCILE,
        Permission.ADMIN_PAYER_VIEW,
        Permission.ADMIN_PAYER_MANAGE,
        Permission.ADMIN_PAYER_TEST,
        # Phase 34: Diagnostics Admin
        Permission.DIAGNOSTIC_CATALOG_READ,
        Permission.DIAGNOSTIC_ORDER_READ,
        Permission.DIAGNOSTIC_RESULT_READ,
        Permission.DIAGNOSTIC_REPORT_READ,
        Permission.ADMIN_DIAGNOSTICS_VIEW,
        Permission.ADMIN_DIAGNOSTICS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_ORDERS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_ORDERS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_RESULTS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_RESULTS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_RECONCILIATION,
        Permission.ADMIN_DIAGNOSTIC_PROVIDER_VIEW,
        Permission.ADMIN_DIAGNOSTIC_PROVIDER_TEST,
        # Phase 35: Clinical Alerts Administration
        Permission.ADMIN_ALERTS_VIEW,
        Permission.ADMIN_ALERTS_MANAGE,
        Permission.ADMIN_ALERT_POLICIES_MANAGE,
        Permission.ADMIN_ALERT_ESCALATION_MANAGE,
        # Phase 36: Clinical Tasks Administration
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_ASSIGN,
        Permission.TASK_ACCEPT,
        Permission.TASK_START,
        Permission.TASK_COMPLETE,
        Permission.TASK_VERIFY,
        Permission.TASK_CANCEL,
        Permission.ADMIN_TASKS_VIEW,
        Permission.ADMIN_TASKS_MANAGE,
        # Phase 37: Clinical Workflows Administration
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_EXECUTE,
        Permission.WORKFLOW_APPROVE,
        Permission.WORKFLOW_PAUSE,
        Permission.WORKFLOW_RESUME,
        Permission.WORKFLOW_CANCEL,
        Permission.ADMIN_WORKFLOWS_VIEW,
        Permission.ADMIN_WORKFLOWS_MANAGE,
    }),
    "SYSTEM_ADMIN": frozenset({
        Permission.ADMIN_USER_MANAGE,
        Permission.ADMIN_AUDIT_READ,
        Permission.CONSENT_READ,
        Permission.ORGANIZATION_READ,
        Permission.FACILITY_READ,
        Permission.DEPARTMENT_READ,
        Permission.CLINICIAN_NETWORK_READ,
        Permission.FACILITY_DISCOVER,
        Permission.TRANSFER_READ,
        Permission.INTEROPERABILITY_READ,
        Permission.AI_READ,
        Permission.PRIVACY_POLICY_READ,
        Permission.PRIVACY_ADMIN,
        Permission.CONFIGURATION_READ,
        Permission.CONFIGURATION_MANAGE,
        Permission.FEATURE_FLAG_READ,
        Permission.FEATURE_FLAG_MANAGE,
        Permission.KILL_SWITCH_MANAGE,
        Permission.DATA_QUALITY_READ,
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_SYSTEM_MANAGE,
        Permission.ADMIN_USERS_VIEW,
        Permission.ADMIN_USERS_MANAGE,
        Permission.ADMIN_JOBS_VIEW,
        Permission.ADMIN_JOBS_MANAGE,
        Permission.ADMIN_INTEGRATIONS_VIEW,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.ADMIN_AUDIT_VIEW,
        Permission.ADMIN_SECURITY_VIEW,
        Permission.ADMIN_CONFIGURATION_VIEW,
        Permission.ADMIN_CONFIGURATION_MANAGE,
        Permission.ADMIN_SUPPORT_VIEW,
        Permission.ADMIN_SUPPORT_MANAGE,
        # Phase 28: Analytics
        Permission.ADMIN_ANALYTICS_VIEW,
        Permission.ORGANIZATION_ANALYTICS_VIEW,
        Permission.FACILITY_ANALYTICS_VIEW,
        # Phase 29: Notifications
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_DISMISS,
        Permission.NOTIFICATION_CREATE,
        Permission.NOTIFICATION_PREFERENCE_READ,
        Permission.NOTIFICATION_PREFERENCE_MANAGE,
        Permission.ADMIN_NOTIFICATION_VIEW,
        Permission.ADMIN_NOTIFICATION_MANAGE,
        Permission.ADMIN_NOTIFICATION_PROVIDER_TEST,
        # Phase 30: Authorized Search & Admin Operations
        Permission.SEARCH_EXECUTE,
        Permission.SEARCH_FACILITY,
        Permission.SEARCH_ORGANIZATION,
        Permission.ADMIN_SEARCH_VIEW,
        Permission.ADMIN_SEARCH_MANAGE,
        # Phase 31: Scheduling & Appointments
        Permission.APPOINTMENT_READ,
        Permission.APPOINTMENT_CREATE,
        Permission.APPOINTMENT_UPDATE,
        Permission.APPOINTMENT_CANCEL,
        Permission.APPOINTMENT_RESCHEDULE,
        Permission.APPOINTMENT_CHECK_IN,
        Permission.AVAILABILITY_READ,
        Permission.SCHEDULE_MANAGE,
        Permission.ADMIN_SCHEDULING_VIEW,
        Permission.ADMIN_SCHEDULING_MANAGE,
        # Phase 32: Billing & Payments Admin
        Permission.INVOICE_READ,
        Permission.INVOICE_CREATE,
        Permission.INVOICE_UPDATE,
        Permission.INVOICE_ISSUE,
        Permission.INVOICE_CANCEL,
        Permission.PAYMENT_READ,
        Permission.PAYMENT_CREATE,
        Permission.PAYMENT_REFUND,
        Permission.ADMIN_BILLING_VIEW,
        Permission.ADMIN_BILLING_MANAGE,
        Permission.ADMIN_PAYMENT_VIEW,
        Permission.ADMIN_PAYMENT_RECONCILE,
        Permission.ADMIN_REFUND_MANAGE,
        # Phase 33: Insurance & Claims Admin
        Permission.INSURANCE_READ,
        Permission.INSURANCE_CREATE,
        Permission.INSURANCE_UPDATE,
        Permission.INSURANCE_VERIFY,
        Permission.ELIGIBILITY_CHECK,
        Permission.BENEFITS_READ,
        Permission.AUTHORIZATION_READ,
        Permission.AUTHORIZATION_CREATE,
        Permission.AUTHORIZATION_UPDATE,
        Permission.AUTHORIZATION_SUBMIT,
        Permission.CLAIM_READ,
        Permission.CLAIM_CREATE,
        Permission.CLAIM_UPDATE,
        Permission.CLAIM_SUBMIT,
        Permission.CLAIM_RECONCILE,
        Permission.ADMIN_INSURANCE_VIEW,
        Permission.ADMIN_INSURANCE_MANAGE,
        Permission.ADMIN_ELIGIBILITY_VIEW,
        Permission.ADMIN_ELIGIBILITY_MANAGE,
        Permission.ADMIN_AUTHORIZATION_VIEW,
        Permission.ADMIN_AUTHORIZATION_MANAGE,
        Permission.ADMIN_CLAIMS_VIEW,
        Permission.ADMIN_CLAIMS_MANAGE,
        Permission.ADMIN_CLAIM_RECONCILE,
        Permission.ADMIN_PAYER_VIEW,
        Permission.ADMIN_PAYER_MANAGE,
        Permission.ADMIN_PAYER_TEST,
        # Phase 34: Diagnostics Admin
        Permission.DIAGNOSTIC_CATALOG_READ,
        Permission.DIAGNOSTIC_ORDER_READ,
        Permission.DIAGNOSTIC_RESULT_READ,
        Permission.DIAGNOSTIC_REPORT_READ,
        Permission.ADMIN_DIAGNOSTICS_VIEW,
        Permission.ADMIN_DIAGNOSTICS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_ORDERS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_ORDERS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_RESULTS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_RESULTS_MANAGE,
        Permission.ADMIN_DIAGNOSTIC_RECONCILIATION,
        Permission.ADMIN_DIAGNOSTIC_PROVIDER_VIEW,
        Permission.ADMIN_DIAGNOSTIC_PROVIDER_TEST,
        # Phase 35: Clinical Alerts Administration
        Permission.ADMIN_ALERTS_VIEW,
        Permission.ADMIN_ALERTS_MANAGE,
        Permission.ADMIN_ALERT_POLICIES_MANAGE,
        Permission.ADMIN_ALERT_ESCALATION_MANAGE,
        # Phase 36: Clinical Tasks Administration
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_ASSIGN,
        Permission.TASK_ACCEPT,
        Permission.TASK_START,
        Permission.TASK_COMPLETE,
        Permission.TASK_VERIFY,
        Permission.TASK_CANCEL,
        Permission.ADMIN_TASKS_VIEW,
        Permission.ADMIN_TASKS_MANAGE,
        # Phase 37: Clinical Workflows Administration
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_EXECUTE,
        Permission.WORKFLOW_APPROVE,
        Permission.WORKFLOW_PAUSE,
        Permission.WORKFLOW_RESUME,
        Permission.WORKFLOW_CANCEL,
        Permission.ADMIN_WORKFLOWS_VIEW,
        Permission.ADMIN_WORKFLOWS_MANAGE,
    }),
    "OPERATIONS_ADMIN": frozenset({
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_SYSTEM_MANAGE,
        Permission.ADMIN_JOBS_VIEW,
        Permission.ADMIN_JOBS_MANAGE,
        Permission.ADMIN_INTEGRATIONS_VIEW,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.ADMIN_SUPPORT_VIEW,
        Permission.ADMIN_SUPPORT_MANAGE,
        Permission.DATA_QUALITY_READ,
        Permission.CONFIGURATION_READ,
        # Phase 28: Analytics
        Permission.ADMIN_ANALYTICS_VIEW,
        Permission.ORGANIZATION_ANALYTICS_VIEW,
        Permission.FACILITY_ANALYTICS_VIEW,
        # Phase 31: Scheduling Admin
        Permission.ADMIN_SCHEDULING_VIEW,
        Permission.APPOINTMENT_READ,
        # Phase 32: Billing Admin
        Permission.ADMIN_BILLING_VIEW,
        Permission.ADMIN_PAYMENT_VIEW,
        Permission.ADMIN_PAYMENT_RECONCILE,
        Permission.INVOICE_READ,
        Permission.PAYMENT_READ,
        # Phase 33: Insurance & Claims Operations
        Permission.ADMIN_INSURANCE_VIEW,
        Permission.ADMIN_CLAIMS_VIEW,
        Permission.ADMIN_CLAIM_RECONCILE,
        Permission.ADMIN_PAYER_VIEW,
        Permission.INSURANCE_READ,
        Permission.CLAIM_READ,
        # Phase 34: Diagnostics Operations
        Permission.DIAGNOSTIC_CATALOG_READ,
        Permission.DIAGNOSTIC_ORDER_READ,
        Permission.DIAGNOSTIC_RESULT_READ,
        Permission.DIAGNOSTIC_REPORT_READ,
        Permission.ADMIN_DIAGNOSTICS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_ORDERS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_RESULTS_VIEW,
        Permission.ADMIN_DIAGNOSTIC_RECONCILIATION,
        Permission.ADMIN_DIAGNOSTIC_PROVIDER_VIEW,
        # Phase 35: Clinical Alerts Operations
        Permission.ADMIN_ALERTS_VIEW,
        Permission.ADMIN_ALERTS_MANAGE,
        Permission.ADMIN_ALERT_ESCALATION_MANAGE,
    }),
    "SUPPORT_OPERATOR": frozenset({
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_SUPPORT_VIEW,
        Permission.ADMIN_SUPPORT_MANAGE,
        Permission.ADMIN_JOBS_VIEW,
        Permission.ADMIN_JOBS_MANAGE,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.ADMIN_INTEGRATIONS_VIEW,
        Permission.DATA_QUALITY_READ,
        # Phase 28: Analytics
        Permission.ADMIN_ANALYTICS_VIEW,
        # Phase 29: Notifications
        Permission.ADMIN_NOTIFICATION_VIEW,
        # Phase 31: Scheduling Admin
        Permission.ADMIN_SCHEDULING_VIEW,
        Permission.APPOINTMENT_READ,
        # Phase 32: Billing Support
        Permission.ADMIN_BILLING_VIEW,
        Permission.ADMIN_PAYMENT_VIEW,
        Permission.INVOICE_READ,
        Permission.PAYMENT_READ,
        # Phase 35: Clinical Alerts Support
        Permission.ADMIN_ALERTS_VIEW,
    }),
    "SECURITY_OPERATOR": frozenset({
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_SECURITY_VIEW,
        Permission.ADMIN_AUDIT_VIEW,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.PRIVACY_POLICY_READ,
    }),
    "AUDIT_OPERATOR": frozenset({
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_AUDIT_VIEW,
        Permission.ADMIN_SECURITY_VIEW,
        Permission.ADMIN_AUDIT_READ,
    }),
    "INTEGRATION_OPERATOR": frozenset({
        Permission.ADMIN_SYSTEM_VIEW,
        Permission.ADMIN_INTEGRATIONS_VIEW,
        Permission.ADMIN_JOBS_VIEW,
        Permission.ADMIN_INCIDENTS_VIEW,
        Permission.ADMIN_INCIDENTS_MANAGE,
        Permission.INTEROPERABILITY_READ,
    }),
}


# ---------------------------------------------------------------------------
# Resource Action → Required Permission Mapping
# ---------------------------------------------------------------------------
# Routes look up the permission required for an (resource_type, action) pair.
# Centralizes policy intent without embedding strings in handlers.

ACTION_PERMISSION_MAP: dict[tuple[str, str], Permission] = {
    # Patient profile
    ("patient_profile", "read"):          Permission.PATIENT_READ_SELF,
    ("patient_profile", "update"):        Permission.PATIENT_UPDATE_SELF,
    # Clinical records (broad)
    ("clinical_record", "read"):          Permission.CLINICAL_RECORD_READ,
    ("clinical_record", "create"):        Permission.CLINICAL_RECORD_CREATE,
    ("clinical_record", "update"):        Permission.CLINICAL_RECORD_UPDATE,
    # Clinical history (Phase 4)
    ("clinical_history", "read"):         Permission.CLINICAL_HISTORY_READ,
    ("clinical_history", "create"):       Permission.CLINICAL_HISTORY_CREATE,
    ("clinical_history", "update"):       Permission.CLINICAL_HISTORY_UPDATE,
    # Allergies (Phase 4)
    ("allergy", "read"):                  Permission.ALLERGY_READ,
    ("allergy", "create"):                Permission.ALLERGY_CREATE,
    ("allergy", "update"):                Permission.ALLERGY_UPDATE,
    # Vitals (Phase 4)
    ("vital", "read"):                    Permission.VITAL_READ,
    ("vital", "create"):                  Permission.VITAL_CREATE,
    # Encounters (Phase 4)
    ("encounter", "read"):                Permission.ENCOUNTER_READ,
    ("encounter", "create"):              Permission.ENCOUNTER_CREATE,
    # Clinical summary (Phase 4)
    ("clinical_summary", "read"):         Permission.CLINICAL_SUMMARY_READ,
    # Medical Documents (Phase 5)
    ("document", "read"):                 Permission.DOCUMENT_READ,
    ("document", "upload"):               Permission.DOCUMENT_UPLOAD,
    ("document", "download"):             Permission.DOCUMENT_READ,
    ("document", "retry"):                Permission.DOCUMENT_PROCESS,
    ("document", "archive"):              Permission.DOCUMENT_ARCHIVE,
    ("document_extraction", "read"):      Permission.DOCUMENT_EXTRACTION_READ,
    # Prescriptions / medications / care plans
    ("prescription", "read"):             Permission.PRESCRIPTION_READ,
    ("prescription", "create"):           Permission.PRESCRIPTION_CREATE,
    ("prescription", "normalize"):        Permission.PRESCRIPTION_NORMALIZE,
    ("prescription", "item_read"):        Permission.PRESCRIPTION_READ,
    ("medication", "read"):               Permission.MEDICATION_READ,
    ("medication", "update"):             Permission.MEDICATION_UPDATE,
    ("medication", "status"):             Permission.MEDICATION_UPDATE,
    ("medication", "correct"):            Permission.MEDICATION_UPDATE,
    # Medication Safety (Phase 7)
    ("medication_safety", "read"):        Permission.MEDICATION_SAFETY_READ,
    ("medication_safety", "check"):       Permission.MEDICATION_SAFETY_CHECK,
    # Symptoms, Triage & SBAR (Phase 8)
    ("symptom", "read"):                  Permission.SYMPTOM_READ,
    ("symptom", "create"):                Permission.SYMPTOM_CREATE,
    ("triage", "read"):                   Permission.TRIAGE_READ,
    ("triage", "assess"):                 Permission.TRIAGE_ASSESS,
    ("sbar", "read"):                     Permission.SBAR_READ,
    ("sbar", "create"):                   Permission.SBAR_CREATE,
    # Care Plan & Discharge (Phase 9)
    ("care_plan", "read"):                Permission.CARE_PLAN_READ,
    ("care_plan", "create"):              Permission.CARE_PLAN_CREATE,
    ("care_plan", "update"):              Permission.CARE_PLAN_UPDATE,
    ("discharge", "extract"):             Permission.DISCHARGE_EXTRACT,
    ("discharge", "verify"):              Permission.DISCHARGE_VERIFY,
    ("discharge", "read"):                Permission.DISCHARGE_READ,
    # Doctor Clinical Workflow (Phase 10)
    ("clinical_note", "read"):            Permission.CLINICAL_NOTE_READ,
    ("clinical_note", "create"):          Permission.CLINICAL_NOTE_CREATE,
    ("clinical_note", "update"):          Permission.CLINICAL_NOTE_UPDATE,
    ("clinical_note", "sign"):            Permission.CLINICAL_NOTE_SIGN,
    ("clinical_assessment", "read"):      Permission.CLINICAL_ASSESSMENT_READ,
    ("clinical_assessment", "create"):    Permission.CLINICAL_ASSESSMENT_CREATE,
    ("clinical_assessment", "update"):    Permission.CLINICAL_ASSESSMENT_UPDATE,
    ("clinical_assessment", "finalize"): Permission.CLINICAL_ASSESSMENT_FINALIZE,
    ("clinical_plan", "read"):            Permission.CLINICAL_PLAN_READ,
    ("clinical_plan", "create"):          Permission.CLINICAL_PLAN_CREATE,
    ("clinical_plan", "update"):          Permission.CLINICAL_PLAN_UPDATE,
    ("clinical_plan", "finalize"):        Permission.CLINICAL_PLAN_FINALIZE,
    ("clinical_workspace", "read"):       Permission.CLINICAL_WORKSPACE_READ,
    # Consent
    ("consent", "create"):                Permission.CONSENT_CREATE,
    ("consent", "read"):                  Permission.CONSENT_READ,
    ("consent", "revoke"):                Permission.CONSENT_REVOKE,
    # Admin
    ("user_management", "manage"):        Permission.ADMIN_USER_MANAGE,
    ("audit_log", "read"):                Permission.ADMIN_AUDIT_READ,
    # Phase 11: Organization, Facility & Department
    ("organization", "read"):             Permission.ORGANIZATION_READ,
    ("facility", "read"):                 Permission.FACILITY_READ,
    ("department", "read"):               Permission.DEPARTMENT_READ,
    ("clinician_network", "read"):        Permission.CLINICIAN_NETWORK_READ,
    # Phase 12: Facility Discovery & Transfer
    ("facility_discovery", "read"):       Permission.FACILITY_DISCOVER,
    ("transfer", "create"):               Permission.TRANSFER_CREATE,
    ("transfer", "read"):                 Permission.TRANSFER_READ,
    ("transfer", "update_status"):        Permission.TRANSFER_UPDATE_STATUS,
    # Phase 13: Interoperability & Healthcare Data Exchange
    ("interoperability", "import"):       Permission.INTEROPERABILITY_IMPORT,
    ("interoperability", "export"):       Permission.INTEROPERABILITY_EXPORT,
    ("interoperability", "read"):         Permission.INTEROPERABILITY_READ,
    # Phase 14: AI & Intelligence Layer
    ("ai", "execute"):                    Permission.AI_EXECUTE,
    ("ai", "read"):                       Permission.AI_READ,
    ("ai", "verify"):                     Permission.AI_VERIFY,
    ("ai_task", "create"):                Permission.AI_EXECUTE,
    ("ai_task", "read"):                  Permission.AI_READ,
    ("ai_task", "verify"):                Permission.AI_VERIFY,
    # Phase 24: Privacy, Retention & Governance
    ("data_export", "request"):          Permission.DATA_EXPORT_REQUEST,
    ("data_export", "read"):             Permission.DATA_EXPORT_READ,
    ("data_export", "download"):         Permission.DATA_EXPORT_DOWNLOAD,
    ("privacy_policy", "read"):          Permission.PRIVACY_POLICY_READ,
    ("privacy", "admin"):                Permission.PRIVACY_ADMIN,
    ("retention", "manage"):             Permission.RETENTION_MANAGE,
    ("retention", "read"):               Permission.RETENTION_READ,
    ("deletion", "manage"):              Permission.DELETION_MANAGE,
    ("deidentification", "execute"):     Permission.DEIDENTIFICATION_EXECUTE,
    ("pseudonymization", "execute"):     Permission.PSEUDONYMIZATION_EXECUTE,
    # Phase 25: Configuration & Feature Flags
    ("configuration", "read"):           Permission.CONFIGURATION_READ,
    ("configuration", "manage"):         Permission.CONFIGURATION_MANAGE,
    ("feature_flag", "read"):            Permission.FEATURE_FLAG_READ,
    ("feature_flag", "manage"):          Permission.FEATURE_FLAG_MANAGE,
    ("kill_switch", "manage"):           Permission.KILL_SWITCH_MANAGE,
    # Phase 26: Data Quality & Reconciliation
    ("data_quality", "read"):            Permission.DATA_QUALITY_READ,
    ("data_quality", "check"):           Permission.DATA_QUALITY_CHECK,
    ("data_quality", "review"):          Permission.DATA_QUALITY_REVIEW,
    ("data_quality", "resolve"):         Permission.DATA_QUALITY_RESOLVE,
    ("reconciliation", "read"):          Permission.RECONCILIATION_READ,
    ("reconciliation", "execute"):       Permission.RECONCILIATION_EXECUTE,
    ("reconciliation", "resolve"):       Permission.RECONCILIATION_RESOLVE,
    # Phase 30: Authorized Search
    ("search", "execute"):               Permission.SEARCH_EXECUTE,
    ("search", "patient"):               Permission.SEARCH_PATIENT,
    ("search", "clinical"):              Permission.SEARCH_CLINICAL,
    ("search", "document"):              Permission.SEARCH_DOCUMENT,
    ("search", "facility"):              Permission.SEARCH_FACILITY,
    ("search", "organization"):          Permission.SEARCH_ORGANIZATION,
    ("search_admin", "view"):            Permission.ADMIN_SEARCH_VIEW,
    ("search_admin", "manage"):          Permission.ADMIN_SEARCH_MANAGE,
    # Phase 31: Scheduling & Appointments
    ("appointment", "read"):             Permission.APPOINTMENT_READ,
    ("appointment", "create"):           Permission.APPOINTMENT_CREATE,
    ("appointment", "update"):           Permission.APPOINTMENT_UPDATE,
    ("appointment", "cancel"):           Permission.APPOINTMENT_CANCEL,
    ("appointment", "reschedule"):       Permission.APPOINTMENT_RESCHEDULE,
    ("appointment", "check_in"):         Permission.APPOINTMENT_CHECK_IN,
    ("availability", "read"):            Permission.AVAILABILITY_READ,
    ("schedule", "manage"):              Permission.SCHEDULE_MANAGE,
    ("scheduling_admin", "view"):        Permission.ADMIN_SCHEDULING_VIEW,
    ("scheduling_admin", "manage"):      Permission.ADMIN_SCHEDULING_MANAGE,
    # Phase 32: Billing, Payments & Financial Transactions
    ("invoice", "read"):                 Permission.INVOICE_READ,
    ("invoice", "create"):               Permission.INVOICE_CREATE,
    ("invoice", "update"):               Permission.INVOICE_UPDATE,
    ("invoice", "issue"):                Permission.INVOICE_ISSUE,
    ("invoice", "cancel"):               Permission.INVOICE_CANCEL,
    ("payment", "read"):                 Permission.PAYMENT_READ,
    ("payment", "create"):               Permission.PAYMENT_CREATE,
    ("payment", "refund"):               Permission.PAYMENT_REFUND,
    ("billing_admin", "view"):           Permission.ADMIN_BILLING_VIEW,
    ("billing_admin", "manage"):         Permission.ADMIN_BILLING_MANAGE,
    ("payment_admin", "view"):           Permission.ADMIN_PAYMENT_VIEW,
    ("payment_admin", "reconcile"):      Permission.ADMIN_PAYMENT_RECONCILE,
    ("refund_admin", "manage"):          Permission.ADMIN_REFUND_MANAGE,
    # Phase 33: Insurance, Claims & Payer Integration
    ("insurance", "read"):               Permission.INSURANCE_READ,
    ("insurance", "create"):             Permission.INSURANCE_CREATE,
    ("insurance", "update"):             Permission.INSURANCE_UPDATE,
    ("insurance", "verify"):             Permission.INSURANCE_VERIFY,
    ("eligibility", "check"):            Permission.ELIGIBILITY_CHECK,
    ("benefits", "read"):                Permission.BENEFITS_READ,
    ("authorization", "read"):           Permission.AUTHORIZATION_READ,
    ("authorization", "create"):         Permission.AUTHORIZATION_CREATE,
    ("authorization", "update"):         Permission.AUTHORIZATION_UPDATE,
    ("authorization", "submit"):         Permission.AUTHORIZATION_SUBMIT,
    ("claim", "read"):                   Permission.CLAIM_READ,
    ("claim", "create"):                 Permission.CLAIM_CREATE,
    ("claim", "update"):                 Permission.CLAIM_UPDATE,
    ("claim", "submit"):                 Permission.CLAIM_SUBMIT,
    ("claim", "reconcile"):              Permission.CLAIM_RECONCILE,
    ("insurance_admin", "view"):         Permission.ADMIN_INSURANCE_VIEW,
    ("insurance_admin", "manage"):       Permission.ADMIN_INSURANCE_MANAGE,
    ("claims_admin", "view"):            Permission.ADMIN_CLAIMS_VIEW,
    ("claims_admin", "manage"):          Permission.ADMIN_CLAIMS_MANAGE,
    ("claim_admin", "reconcile"):        Permission.ADMIN_CLAIM_RECONCILE,
    ("payer_admin", "view"):             Permission.ADMIN_PAYER_VIEW,
    ("payer_admin", "manage"):           Permission.ADMIN_PAYER_MANAGE,
    ("payer_admin", "test"):             Permission.ADMIN_PAYER_TEST,
    # Phase 34: Laboratory, Diagnostic Orders & Result Management
    ("diagnostic_catalog", "read"):       Permission.DIAGNOSTIC_CATALOG_READ,
    ("diagnostic_order", "read"):         Permission.DIAGNOSTIC_ORDER_READ,
    ("diagnostic_order", "create"):       Permission.DIAGNOSTIC_ORDER_CREATE,
    ("diagnostic_order", "cancel"):       Permission.DIAGNOSTIC_ORDER_CANCEL,
    ("diagnostic_result", "read"):        Permission.DIAGNOSTIC_RESULT_READ,
    ("diagnostic_result", "verify"):      Permission.DIAGNOSTIC_RESULT_VERIFY,
    ("diagnostic_report", "read"):        Permission.DIAGNOSTIC_REPORT_READ,
    ("diagnostic_report", "create"):      Permission.DIAGNOSTIC_REPORT_CREATE,
    ("diagnostics_admin", "view"):        Permission.ADMIN_DIAGNOSTICS_VIEW,
    ("diagnostics_admin", "manage"):      Permission.ADMIN_DIAGNOSTICS_MANAGE,
    ("diagnostic_orders_admin", "view"):  Permission.ADMIN_DIAGNOSTIC_ORDERS_VIEW,
    ("diagnostic_orders_admin", "manage"):Permission.ADMIN_DIAGNOSTIC_ORDERS_MANAGE,
    ("diagnostic_results_admin", "view"): Permission.ADMIN_DIAGNOSTIC_RESULTS_VIEW,
    ("diagnostic_results_admin", "manage"):Permission.ADMIN_DIAGNOSTIC_RESULTS_MANAGE,
    ("diagnostic_admin", "reconcile"):    Permission.ADMIN_DIAGNOSTIC_RECONCILIATION,
    ("diagnostic_provider_admin", "view"):Permission.ADMIN_DIAGNOSTIC_PROVIDER_VIEW,
    ("diagnostic_provider_admin", "test"):Permission.ADMIN_DIAGNOSTIC_PROVIDER_TEST,
    # Phase 35: Clinical Alerts & Escalation
    ("alert", "read"):                    Permission.ALERT_READ,
    ("alert", "acknowledge"):             Permission.ALERT_ACKNOWLEDGE,
    ("alert", "resolve"):                 Permission.ALERT_RESOLVE,
    ("alert", "dismiss"):                 Permission.ALERT_DISMISS,
    ("alert", "escalate"):                Permission.ALERT_ESCALATE,
    ("alert_policy", "read"):             Permission.ALERT_POLICY_READ,
    ("alerts_admin", "view"):             Permission.ADMIN_ALERTS_VIEW,
    ("alerts_admin", "manage"):           Permission.ADMIN_ALERTS_MANAGE,
    ("alert_policies_admin", "manage"):   Permission.ADMIN_ALERT_POLICIES_MANAGE,
    ("alert_escalation_admin", "manage"): Permission.ADMIN_ALERT_ESCALATION_MANAGE,
    # Phase 36: Clinical Tasks & Queues
    ("task", "create"):                   Permission.TASK_CREATE,
    ("task", "read"):                     Permission.TASK_READ,
    ("task", "assign"):                   Permission.TASK_ASSIGN,
    ("task", "reassign"):                 Permission.TASK_ASSIGN,
    ("task", "accept"):                   Permission.TASK_ACCEPT,
    ("task", "start"):                    Permission.TASK_START,
    ("task", "complete"):                 Permission.TASK_COMPLETE,
    ("task", "verify"):                   Permission.TASK_VERIFY,
    ("task", "reject"):                   Permission.TASK_REJECT,
    ("task", "cancel"):                   Permission.TASK_CANCEL,
    ("tasks_admin", "view"):              Permission.ADMIN_TASKS_VIEW,
    ("tasks_admin", "manage"):            Permission.ADMIN_TASKS_MANAGE,
    # Phase 37: Clinical Workflows & Orchestration
    ("workflow", "create"):               Permission.WORKFLOW_CREATE,
    ("workflow", "read"):                 Permission.WORKFLOW_READ,
    ("workflow", "execute"):              Permission.WORKFLOW_EXECUTE,
    ("workflow", "approve"):              Permission.WORKFLOW_APPROVE,
    ("workflow", "pause"):                Permission.WORKFLOW_PAUSE,
    ("workflow", "resume"):               Permission.WORKFLOW_RESUME,
    ("workflow", "cancel"):               Permission.WORKFLOW_CANCEL,
    ("workflows_admin", "view"):          Permission.ADMIN_WORKFLOWS_VIEW,
    ("workflows_admin", "manage"):        Permission.ADMIN_WORKFLOWS_MANAGE,
}


# ---------------------------------------------------------------------------
# Consent Purpose Registry
# ---------------------------------------------------------------------------
# Supported consent purposes. Prevents arbitrary client-submitted purposes.
# Database team should eventually own this as a reference table.

class ConsentPurpose(str, Enum):
    """Supported consent purposes in HealthSetu.

    DATABASE TEAM DEPENDENCY:
    When a consent_purpose reference table is available, this enum should
    be validated against live database values. Until then this is the
    authoritative set of supported purposes.
    """

    CARE_DELIVERY = "care_delivery"
    EMERGENCY_ACCESS = "emergency_access"
    RESEARCH = "research"          # requires explicit separate consent grant
    ADMINISTRATIVE = "administrative"
    SECOND_OPINION = "second_opinion"


# ---------------------------------------------------------------------------
# Consent Scope Registry
# ---------------------------------------------------------------------------
# What resource scopes a consent can cover.

class ConsentScope(str, Enum):
    """Resource scopes that consent can cover.

    A consent for 'care_delivery' with scope 'clinical_records' does NOT
    automatically authorize access to 'prescriptions' or 'documents'.
    """

    CLINICAL_RECORDS = "clinical_records"
    PRESCRIPTIONS = "prescriptions"
    MEDICATIONS = "medications"
    MEDICATION_SAFETY = "medication_safety"
    SYMPTOMS = "symptoms"
    TRIAGE = "triage"
    CARE_PLAN = "care_plan"
    DOCUMENTS = "documents"
    DISCHARGE_SUMMARY = "discharge_summary"
    TRANSFER = "transfer"
    INTEROPERABILITY = "interoperability"
    DIAGNOSTICS = "diagnostics"
    ALERTS = "alerts"
    TASKS = "tasks"
    WORKFLOWS = "workflows"
    ALL_RECORDS = "all_records"   # broad scope — must require explicit grant


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_role_permissions(role: str) -> FrozenSet[Permission]:
    """Return the set of permissions for the given role string.

    Unknown roles receive an empty frozenset (deny by default).
    """
    return ROLE_PERMISSIONS.get(role.upper(), frozenset())


def role_has_permission(role: str, permission: Permission) -> bool:
    """Check whether the given role includes the specified permission."""
    return permission in get_role_permissions(role)


def get_required_permission(resource_type: str, action: str) -> Permission | None:
    """Resolve the required Permission for a (resource_type, action) pair.

    Returns None if the combination is not registered (unknown = deny).
    """
    return ACTION_PERMISSION_MAP.get((resource_type.lower(), action.lower()))


def is_valid_consent_purpose(purpose: str) -> bool:
    """Check whether a purpose string is a recognized consent purpose."""
    return purpose in {p.value for p in ConsentPurpose}


def is_valid_consent_scope(scope: str) -> bool:
    """Check whether a scope string is a recognized consent scope."""
    return scope in {s.value for s in ConsentScope}
