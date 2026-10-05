"""FastAPI dependency injection providers for authentication, authorization, and services."""

from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.policies import Permission
from app.core.security import decode_access_token
from app.core.config import get_settings
from app.integrations.ocr.base import OCRProvider
from app.integrations.ocr.local_ocr import LocalOCRProvider
from app.integrations.scanning.base import DocumentSecurityScanner
from app.integrations.scanning.mock_scanner import MockSecurityScanner
from app.integrations.storage.base import DocumentStorage
from app.integrations.storage.local_storage import LocalDocumentStorage
from app.repositories.allergy_repository import AllergyRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.clinical_history_repository import ClinicalHistoryRepository
from app.repositories.consent_repository import ConsentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.encounter_repository import EncounterRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.vitals_repository import VitalsRepository
from app.schemas.auth import UserRole
from app.schemas.authorization import AuthorizationContext
from app.schemas.patient import PatientResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.authorization_service import AuthorizationService
from app.services.clinical_record_service import ClinicalRecordService
from app.services.consent_service import ConsentService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.patient_service import PatientService
from app.services.processors.generic_processor import GenericDocumentProcessor
from app.services.processors.registry import DocumentProcessorRegistry
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.patient_medication_repository import PatientMedicationRepository
from app.integrations.medication.base import MedicationTerminologyProvider
from app.integrations.medication.providers.local import LocalMedicationProvider
from app.integrations.medication.providers.rxnorm import RxNormProvider
from app.services.medication_normalization_service import MedicationNormalizationService
from app.services.prescription_service import PrescriptionService
from app.services.medication_service import MedicationService
from app.repositories.medication_safety_repository import MedicationSafetyRepository
from app.integrations.medication_safety.base import MedicationSafetyProvider
from app.integrations.medication_safety.registry import get_medication_safety_provider
from app.services.medication_safety_service import MedicationSafetyService

# Phase 8: Triage & SBAR imports
from app.repositories.symptom_repository import SymptomRepository
from app.repositories.triage_repository import TriageRepository
from app.repositories.sbar_repository import SBARRepository
from app.integrations.triage.base import TriageRuleEngine
from app.integrations.triage.rule_engine import HealthSetuDeterministicTriageEngine
from app.integrations.ai.base import ClinicalTextGenerator
from app.integrations.ai.providers.template_generator import TemplateClinicalTextGenerator
from app.integrations.ai.providers.mock_llm import MockLLMClinicalTextGenerator
from app.integrations.ai.validator import SBARFactValidator
from app.services.symptom_service import SymptomService
from app.services.triage_service import TriageService
from app.services.sbar_service import SBARService

# Phase 9: Care Plan & Discharge imports
from app.repositories.discharge_repository import DischargeRepository
from app.repositories.care_plan_repository import CarePlanRepository
from app.integrations.discharge.base import DischargeExtractor
from app.integrations.discharge.extractor import LocalDischargeExtractor
from app.services.discharge_service import DischargeService
from app.services.care_plan_service import CarePlanService

# Phase 10: Doctor Clinical Workflow imports
from app.repositories.clinical_note_repository import ClinicalNoteRepository
from app.repositories.clinical_assessment_repository import ClinicalAssessmentRepository
from app.repositories.clinical_plan_repository import ClinicalPlanRepository
from app.services.clinical_note_service import ClinicalNoteService
from app.services.clinical_assessment_service import ClinicalAssessmentService
from app.services.clinical_plan_service import ClinicalPlanService
from app.services.clinical_workspace_service import ClinicalWorkspaceService

# Phase 11: Hospital & Organization Network imports
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.facility_repository import FacilityRepository
from app.repositories.department_repository import DepartmentRepository
from app.integrations.healthcare_directory.provider import (
    HealthcareDirectoryProvider,
    get_healthcare_directory_provider,
)
from app.services.organization_access_service import OrganizationAccessService
from app.services.facility_access_service import FacilityAccessService
from app.services.organization_service import OrganizationService
from app.services.facility_service import FacilityService
from app.services.department_service import DepartmentService

# Phase 12: Facility Discovery & Transfer imports
from app.repositories.facility_discovery_repository import FacilityDiscoveryRepository
from app.repositories.transfer_repository import TransferRepository
from app.services.geographic_service import GeographicService
from app.services.facility_capability_service import FacilityCapabilityService
from app.services.facility_discovery_service import FacilityDiscoveryService
from app.services.transfer_service import TransferService

# Phase 13: Interoperability imports
from app.repositories.interoperability_repository import InteroperabilityRepository
from app.integrations.interoperability.base import InteroperabilityProvider
from app.integrations.interoperability.providers.mock_provider import MockInteroperabilityProvider
from app.integrations.interoperability.fhir.mapper import FHIRMapper
from app.integrations.interoperability.fhir.validator import FHIRValidator
from app.services.interoperability_service import InteroperabilityService

# Phase 14: AI Intelligence Layer imports
from app.repositories.ai_repository import AIRepository
from app.integrations.ai.client import get_ai_provider
from app.services.ai_service import AIService
from app.services.ai_task_service import AITaskService
from app.services.ai_validation_service import AIValidationService
from app.services.ai_provenance_service import AIProvenanceService
from app.services.ai_usage_service import AIUsageService

# Phase 22: Asynchronous Workflow & Event-Driven execution imports
from app.repositories.job_repository import JobRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.event_repository import EventRepository
from app.repositories.idempotency_repository import IdempotencyRepository
from app.integrations.queue.base import JobQueueProvider
from app.integrations.queue.provider import get_job_queue_provider
from app.integrations.events.base import EventTransport
from app.integrations.events.provider import get_event_transport
from app.services.idempotency_service import IdempotencyService
from app.services.event_service import EventService
from app.services.job_service import JobService
from app.services.workflow_service import WorkflowService

# Phase 24: Advanced Data Privacy & Data Governance imports
from app.services.privacy_service import PrivacyService
from app.services.retention_service import RetentionService
from app.services.data_export_service import DataExportService
from app.services.deidentification_service import DeidentificationService
from app.services.pseudonymization_service import PseudonymizationService

# Phase 25: Feature Flags, Configuration Governance & Rollout imports
from app.services.feature_flag_service import FeatureFlagService
from app.services.configuration_service import ConfigurationService

# Phase 26: Data Quality, Clinical Record Integrity & Reconciliation imports
from app.repositories.data_quality_repository import DataQualityRepository
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.services.provenance_service import ProvenanceService
from app.services.data_quality_service import DataQualityService
from app.services.reconciliation_service import ReconciliationService

# Phase 27: Administration, Support Operations & Controlled Backoffice imports
from app.repositories.incident_repository import IncidentRepository
from app.services.incident_service import IncidentService
from app.services.support_service import SupportService
from app.services.admin_service import AdminService

from app.repositories.analytics_repository import AnalyticsRepository
from app.services.analytics_service import AnalyticsService

# Phase 29: Notification, Communication & Event Delivery System imports
from app.repositories.notification_repository import NotificationRepository
from app.repositories.notification_delivery_repository import NotificationDeliveryRepository
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.services.notification_template_service import NotificationTemplateService
from app.services.notification_preference_service import NotificationPreferenceService
from app.services.communication_service import CommunicationService
from app.services.notification_service import NotificationService
from app.integrations.notifications import get_notification_provider_registry

# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval imports
from app.repositories.search_repository import SearchRepository
from app.integrations.search.postgres import PostgresSearchProvider
from app.services.search_normalization_service import SearchNormalizationService
from app.services.search_authorization_service import SearchAuthorizationService
from app.services.search_result_service import SearchResultService
from app.services.search_service import SearchService

# Phase 31: Scheduling, Appointment & Clinical Access Management imports
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.integrations.scheduling.base import SchedulingProvider
from app.integrations.scheduling.local import LocalSchedulingProvider
from app.services.appointment_validation_service import AppointmentValidationService
from app.services.appointment_authorization_service import AppointmentAuthorizationService
from app.services.availability_service import AvailabilityService
from app.services.appointment_service import AppointmentService
from app.services.scheduling_service import SchedulingService

# Phase 32: Billing, Payments & Financial Transaction Management imports
from app.repositories.billing_repository import BillingRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.providers.mock import MockPaymentProvider
from app.services.billing_validation_service import BillingValidationService
from app.services.billing_authorization_service import BillingAuthorizationService
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.services.refund_service import RefundService
from app.services.payment_webhook_service import PaymentWebhookService
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.repositories.insurance_repository import InsuranceRepository
from app.repositories.eligibility_repository import EligibilityRepository
from app.repositories.benefit_repository import BenefitRepository
from app.repositories.authorization_repository import AuthorizationRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_reconciliation_repository import ClaimReconciliationRepository
from app.repositories.payer_webhook_repository import PayerWebhookRepository
from app.integrations.payers.base import PayerProvider
from app.integrations.payers.providers.mock import MockPayerProvider
from app.services.insurance_validation_service import InsuranceValidationService
from app.services.payer_authorization_service import PayerAuthorizationService
from app.services.insurance_service import InsuranceService
from app.services.eligibility_service import EligibilityService
from app.services.benefit_service import BenefitService
from app.services.preauthorization_service import PreAuthorizationService
from app.services.claim_service import ClaimService
from app.services.claim_response_service import ClaimResponseService
from app.services.claim_reconciliation_service import ClaimReconciliationService
from app.services.payer_webhook_service import PayerWebhookService

# Phase 34: Laboratory, Diagnostic Orders & Result Management imports
from app.repositories.diagnostic_catalog_repository import DiagnosticCatalogRepository
from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.repositories.diagnostic_result_repository import DiagnosticResultRepository
from app.repositories.diagnostic_report_repository import DiagnosticReportRepository
from app.repositories.diagnostic_reconciliation_repository import DiagnosticReconciliationRepository
from app.repositories.diagnostic_webhook_repository import DiagnosticWebhookRepository
from app.integrations.diagnostics.base import DiagnosticProvider
from app.integrations.diagnostics.providers.mock import MockDiagnosticProvider
from app.services.diagnostic_validation_service import DiagnosticValidationService
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_catalog_service import DiagnosticCatalogService
from app.services.diagnostic_order_service import DiagnosticOrderService
from app.services.diagnostic_result_service import DiagnosticResultService
from app.services.diagnostic_verification_service import DiagnosticVerificationService
from app.services.diagnostic_report_service import DiagnosticReportService
from app.services.diagnostic_reconciliation_service import DiagnosticReconciliationService
from app.services.diagnostic_webhook_service import DiagnosticWebhookService

# Phase 35: Clinical Alerts, Safety Notifications & Escalation Management imports
from app.repositories.alert_repository import AlertRepository
from app.repositories.alert_escalation_repository import AlertEscalationRepository
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.integrations.alerts.base import AlertProvider
from app.integrations.alerts.providers.local import LocalAlertProvider
from app.services.alert_validation_service import AlertValidationService
from app.services.alert_recipient_service import AlertRecipientService
from app.services.alert_policy_service import AlertPolicyService
from app.services.alert_escalation_service import AlertEscalationService
from app.services.alert_service import AlertService

# Phase 36: Clinical Tasks, Work Queues & Action Management imports
from app.repositories.task_repository import TaskRepository
from app.repositories.task_assignment_repository import TaskAssignmentRepository
from app.services.task_validation_service import TaskValidationService
from app.services.task_assignment_service import TaskAssignmentService
from app.services.task_dependency_service import TaskDependencyService
from app.services.task_escalation_service import TaskEscalationService
from app.services.task_service import TaskService

# Phase 37: Clinical Workflow Orchestration, Order Management & Controlled Action Chains imports
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.services.workflow_definition_service import WorkflowDefinitionService
from app.services.workflow_validation_service import WorkflowValidationService
from app.services.workflow_step_service import WorkflowStepService
from app.services.workflow_approval_service import WorkflowApprovalService
from app.services.workflow_service import WorkflowService

# Phase 38: Clinical Orders, Results & Controlled Action Execution imports
from app.repositories.order_repository import OrderRepository
from app.services.order_validation_service import OrderValidationService
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.order_service import OrderService
from app.integrations.orders.providers.mock import MockOrderProvider

# Phase 39: Clinical Order Sets, Protocol Templates & Controlled Order Composition imports
from app.repositories.order_set_repository import OrderSetRepository
from app.services.order_set_validation_service import OrderSetValidationService
from app.services.order_set_authorization_service import OrderSetAuthorizationService
from app.services.order_set_service import OrderSetService

# Phase 40: Clinical Order Review, Approval Gates & Controlled Authorization Management imports
from app.repositories.approval_repository import ApprovalRepository
from app.services.approval_policy_service import ApprovalPolicyService
from app.services.approval_authorization_service import ApprovalAuthorizationService
from app.services.approval_service import ApprovalService

# Phase 41: Clinical Communication, Patient–Provider Messaging & Secure Conversation Management imports
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.integrations.communication.providers.mock import MockCommunicationProvider
from app.services.conversation_authorization_service import ConversationAuthorizationService
from app.services.communication_policy_service import CommunicationPolicyService
from app.services.conversation_service import ConversationService
from app.services.message_authorization_service import MessageAuthorizationService
from app.services.message_delivery_service import MessageDeliveryService
from app.services.message_search_service import MessageSearchService
from app.services.message_service import MessageService

# ---------------------------------------------------------------------------
# HTTP Bearer scheme
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer access token in Authorization header (Format: Bearer <token>)",
)

# ---------------------------------------------------------------------------
# Global default repositories (in-memory fallbacks until DB team delivers schema)
# ---------------------------------------------------------------------------
_global_user_repo = UserRepository()
_global_session_repo = AuthSessionRepository()
_global_consent_repo = ConsentRepository()
_global_audit_repo = AuditRepository()
_global_permission_repo = PermissionRepository()
_global_patient_repo = PatientRepository()
_global_history_repo = ClinicalHistoryRepository()
_global_allergy_repo = AllergyRepository()
_global_vitals_repo = VitalsRepository()
_global_encounter_repo = EncounterRepository()
_global_document_repo = DocumentRepository()
_global_document_storage = LocalDocumentStorage()
_global_security_scanner = MockSecurityScanner()
_global_ocr_provider = LocalOCRProvider()
_global_processor = GenericDocumentProcessor(_global_ocr_provider)
_global_processor_registry = DocumentProcessorRegistry(_global_processor)

# ---------------------------------------------------------------------------
# Phase 6: Global default repositories & providers
# ---------------------------------------------------------------------------
_global_prescription_repo = PrescriptionRepository()
_global_medication_repo = MedicationRepository()
_global_patient_medication_repo = PatientMedicationRepository()
_global_medication_terminology_provider = LocalMedicationProvider()
_global_medication_safety_repo = MedicationSafetyRepository()

# ---------------------------------------------------------------------------
# Phase 8: Global default repositories & providers
# ---------------------------------------------------------------------------
_global_symptom_repo = SymptomRepository()
_global_triage_repo = TriageRepository()
_global_sbar_repo = SBARRepository()
_global_triage_engine = HealthSetuDeterministicTriageEngine()
_global_template_generator = TemplateClinicalTextGenerator()
_global_ai_generator = MockLLMClinicalTextGenerator()
_global_sbar_validator = SBARFactValidator()

# ---------------------------------------------------------------------------
# Phase 9: Global default repositories & providers
# ---------------------------------------------------------------------------
_global_discharge_repo = DischargeRepository()
_global_care_plan_repo = CarePlanRepository()
_global_discharge_extractor = LocalDischargeExtractor()

# ---------------------------------------------------------------------------
# Phase 10: Global default repositories
# ---------------------------------------------------------------------------
_global_clinical_note_repo = ClinicalNoteRepository()
_global_clinical_assessment_repo = ClinicalAssessmentRepository()
_global_clinical_plan_repo = ClinicalPlanRepository()

# ---------------------------------------------------------------------------
# Phase 11: Global default repositories & providers
# ---------------------------------------------------------------------------
_global_organization_repo = OrganizationRepository()
_global_facility_repo = FacilityRepository()
_global_department_repo = DepartmentRepository()
_global_healthcare_directory_provider = get_healthcare_directory_provider()

# ---------------------------------------------------------------------------
# Phase 12: Global default repositories & services
# ---------------------------------------------------------------------------
_global_facility_discovery_repo = FacilityDiscoveryRepository(
    facility_repo=_global_facility_repo,
    department_repo=_global_department_repo,
)
_global_transfer_repo = TransferRepository()
_global_geo_service = GeographicService()
_global_facility_capability_service = FacilityCapabilityService(
    discovery_repo=_global_facility_discovery_repo
)

# ---------------------------------------------------------------------------
# Phase 13: Global default repositories & providers
# ---------------------------------------------------------------------------
_global_interoperability_repo = InteroperabilityRepository()
_global_fhir_validator = FHIRValidator()
_global_fhir_mapper = FHIRMapper()
_global_interoperability_provider = MockInteroperabilityProvider(name="MockProvider")

_global_audit_service = AuditService(audit_repository=_global_audit_repo)
_global_authz_service = AuthorizationService(
    permission_repository=_global_permission_repo,
    consent_service=ConsentService(consent_repository=_global_consent_repo),
    audit_service=_global_audit_service,
)

# ---------------------------------------------------------------------------
# Phase 14: AI Intelligence Layer global repositories
# ---------------------------------------------------------------------------
_global_ai_repo = AIRepository()

# ---------------------------------------------------------------------------
# Phase 22: Asynchronous Workflow & Event-Driven global repositories
# ---------------------------------------------------------------------------
_global_job_repo = JobRepository()
_global_workflow_repo = WorkflowRepository()
_global_event_repo = EventRepository()
_global_idempotency_repo = IdempotencyRepository()

# ---------------------------------------------------------------------------
# Phase 24: Advanced Data Privacy & Governance global singletons
# ---------------------------------------------------------------------------
_global_privacy_service = PrivacyService(
    audit_repository=_global_audit_repo,
    consent_repository=_global_consent_repo,
    patient_repository=_global_patient_repo,
)
_global_retention_service = RetentionService(
    audit_repository=_global_audit_repo,
    document_repository=_global_document_repo,
    patient_repository=_global_patient_repo,
    storage_adapter=_global_document_storage,
)
_global_data_export_service = DataExportService(
    audit_repository=_global_audit_repo,
    patient_repository=_global_patient_repo,
    document_repository=_global_document_repo,
    allergy_repository=_global_allergy_repo,
    clinical_history_repository=_global_history_repo,
    encounter_repository=_global_encounter_repo,
    vitals_repository=_global_vitals_repo,
    medication_repository=_global_medication_repo,
    prescription_repository=_global_prescription_repo,
    triage_repository=_global_triage_repo,
    care_plan_repository=_global_care_plan_repo,
    interoperability_repository=_global_interoperability_repo,
    consent_repository=_global_consent_repo,
    storage_adapter=_global_document_storage,
)
_global_deidentification_service = DeidentificationService(audit_repository=_global_audit_repo)
_global_pseudonymization_service = PseudonymizationService(audit_repository=_global_audit_repo)

# ---------------------------------------------------------------------------
# Phase 25: Feature Flags & Configuration Governance global singletons
# ---------------------------------------------------------------------------
_global_feature_flag_service = FeatureFlagService(audit_repo=_global_audit_repo)
_global_configuration_service = ConfigurationService(
    feature_flag_service=_global_feature_flag_service,
    audit_repo=_global_audit_repo,
)

# ---------------------------------------------------------------------------
# Phase 26: Data Quality & Reconciliation global singletons
# ---------------------------------------------------------------------------
_global_data_quality_repo = DataQualityRepository()
_global_reconciliation_repo = ReconciliationRepository()
_global_provenance_service = ProvenanceService()
_global_data_quality_service = DataQualityService(
    dq_repo=_global_data_quality_repo,
    patient_repo=_global_patient_repo,
    allergy_repo=_global_allergy_repo,
    medication_repo=_global_patient_medication_repo,
    document_repo=_global_document_repo,
    provenance_service=_global_provenance_service,
    audit_service=_global_audit_service,
)
_global_reconciliation_service = ReconciliationService(
    reconciliation_repo=_global_reconciliation_repo,
    allergy_repo=_global_allergy_repo,
    medication_repo=_global_patient_medication_repo,
    patient_repo=_global_patient_repo,
    provenance_service=_global_provenance_service,
    audit_service=_global_audit_service,
)

# ---------------------------------------------------------------------------
# Phase 27: Administration, Support Operations & Backoffice global singletons
# ---------------------------------------------------------------------------
_global_incident_repo = IncidentRepository()
_global_incident_service = IncidentService(
    incident_repo=_global_incident_repo,
    audit_service=_global_audit_service,
)
_global_support_service = SupportService(
    patient_repo=_global_patient_repo,
    user_repo=_global_user_repo,
    consent_repo=_global_consent_repo,
    audit_service=_global_audit_service,
)
_global_admin_service = AdminService(
    job_repo=_global_job_repo,
    audit_repo=_global_audit_repo,
    audit_service=_global_audit_service,
    incident_repo=_global_incident_repo,
    data_quality_repo=_global_data_quality_repo,
    reconciliation_repo=_global_reconciliation_repo,
)

# ---------------------------------------------------------------------------
# Phase 28: API Analytics & Usage Governance global singletons
# ---------------------------------------------------------------------------
_global_analytics_repo = AnalyticsRepository()
_global_analytics_service = AnalyticsService(
    repository=_global_analytics_repo,
    audit_repository=_global_audit_repo,
)

# ---------------------------------------------------------------------------
# Phase 29: Notification, Communication & Event Delivery System singletons
# ---------------------------------------------------------------------------
_global_notification_repo = NotificationRepository()
_global_notification_delivery_repo = NotificationDeliveryRepository()
_global_notification_preference_repo = NotificationPreferenceRepository()
_global_notification_template_service = NotificationTemplateService()
_global_notification_preference_service = NotificationPreferenceService(
    repository=_global_notification_preference_repo
)
_global_communication_service = CommunicationService(
    delivery_repository=_global_notification_delivery_repo,
    provider_registry=get_notification_provider_registry(),
)
_global_notification_service = NotificationService(
    notification_repository=_global_notification_repo,
    delivery_repository=_global_notification_delivery_repo,
    template_service=_global_notification_template_service,
    preference_service=_global_notification_preference_service,
    communication_service=_global_communication_service,
    audit_service=_global_audit_service,
    analytics_service=_global_analytics_service,
)

# ---------------------------------------------------------------------------
# Phase 31: Scheduling, Appointment & Clinical Access Management singletons
# ---------------------------------------------------------------------------
_global_appointment_repo = AppointmentRepository()
_global_availability_repo = AvailabilityRepository()
_global_schedule_repo = ScheduleRepository()

# ---------------------------------------------------------------------------
# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval singletons
# ---------------------------------------------------------------------------
_global_search_repo = SearchRepository()
_global_search_provider = PostgresSearchProvider(
    patient_repo=_global_patient_repo,
    document_repo=_global_document_repo,
    encounter_repo=_global_encounter_repo,
    prescription_repo=_global_prescription_repo,
    medication_repo=_global_medication_repo,
    care_plan_repo=_global_care_plan_repo,
    discharge_repo=_global_discharge_repo,
    clinical_note_repo=_global_clinical_note_repo,
    org_repo=_global_organization_repo,
    facility_repo=_global_facility_repo,
    transfer_repo=_global_transfer_repo,
    search_repo=_global_search_repo,
    appointment_repo=_global_appointment_repo,
)
_global_search_normalization_service = SearchNormalizationService()
_global_search_authorization_service = SearchAuthorizationService(patient_repo=_global_patient_repo)
_global_search_result_service = SearchResultService()
_global_search_service = SearchService(
    provider=_global_search_provider,
    normalization_service=_global_search_normalization_service,
    authorization_service=_global_search_authorization_service,
    result_service=_global_search_result_service,
    audit_service=_global_audit_service,
)

_global_scheduling_provider = LocalSchedulingProvider(
    appointment_repo=_global_appointment_repo,
    availability_repo=_global_availability_repo,
)
_global_appointment_validation_service = AppointmentValidationService()
_global_appointment_authorization_service = AppointmentAuthorizationService(patient_repo=_global_patient_repo)
_global_availability_service = AvailabilityService(
    provider=_global_scheduling_provider,
    validation_service=_global_appointment_validation_service,
    audit_service=_global_audit_service,
)
_global_appointment_service = AppointmentService(
    provider=_global_scheduling_provider,
    appointment_repo=_global_appointment_repo,
    validation_service=_global_appointment_validation_service,
    auth_service=_global_appointment_authorization_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
    analytics_service=_global_analytics_service,
)
_global_scheduling_service = SchedulingService(
    schedule_repo=_global_schedule_repo,
    availability_repo=_global_availability_repo,
    provider=_global_scheduling_provider,
)

# ---------------------------------------------------------------------------
# Phase 32: Billing, Payments & Financial Transaction Management singletons
# ---------------------------------------------------------------------------
_global_billing_repo = BillingRepository()
_global_invoice_repo = InvoiceRepository()
_global_payment_repo = PaymentRepository()
_global_refund_repo = RefundRepository()
_global_mock_payment_provider = MockPaymentProvider()
_global_payment_providers: dict[str, PaymentProvider] = {
    "MOCK": _global_mock_payment_provider,
}
_global_billing_validation_service = BillingValidationService()
_global_billing_authorization_service = BillingAuthorizationService(patient_repo=_global_patient_repo)
_global_invoice_service = InvoiceService(
    invoice_repo=_global_invoice_repo,
    billing_repo=_global_billing_repo,
    auth_service=_global_billing_authorization_service,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    analytics_service=_global_analytics_service,
)
_global_payment_service = PaymentService(
    payment_repo=_global_payment_repo,
    invoice_repo=_global_invoice_repo,
    invoice_service=_global_invoice_service,
    auth_service=_global_billing_authorization_service,
    provider=_global_mock_payment_provider,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    analytics_service=_global_analytics_service,
)
_global_refund_service = RefundService(
    refund_repo=_global_refund_repo,
    payment_repo=_global_payment_repo,
    invoice_service=_global_invoice_service,
    auth_service=_global_billing_authorization_service,
    provider=_global_mock_payment_provider,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    analytics_service=_global_analytics_service,
)
_global_payment_webhook_service = PaymentWebhookService(
    payment_repo=_global_payment_repo,
    invoice_service=_global_invoice_service,
    providers=_global_payment_providers,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    analytics_service=_global_analytics_service,
)
_global_payment_reconciliation_service = PaymentReconciliationService(
    payment_repo=_global_payment_repo,
    invoice_service=_global_invoice_service,
    provider=_global_mock_payment_provider,
    audit_service=_global_audit_service,
)

# ---------------------------------------------------------------------------
# Phase 33: Insurance, Claims & Payer Integration singletons
# ---------------------------------------------------------------------------
_global_insurance_repo = InsuranceRepository()
_global_eligibility_repo = EligibilityRepository()
_global_benefit_repo = BenefitRepository()
_global_authorization_repo = AuthorizationRepository()
_global_claim_repo = ClaimRepository()
_global_claim_reconciliation_repo = ClaimReconciliationRepository()
_global_payer_webhook_repo = PayerWebhookRepository()
_global_mock_payer_provider = MockPayerProvider()
_global_insurance_service = InsuranceService(repository=_global_insurance_repo)
_global_eligibility_service = EligibilityService(
    insurance_repo=_global_insurance_repo,
    eligibility_repo=_global_eligibility_repo,
    provider=_global_mock_payer_provider,
)
_global_benefit_service = BenefitService(
    insurance_repo=_global_insurance_repo,
    benefit_repo=_global_benefit_repo,
    provider=_global_mock_payer_provider,
)
_global_preauthorization_service = PreAuthorizationService(
    insurance_repo=_global_insurance_repo,
    auth_repo=_global_authorization_repo,
    provider=_global_mock_payer_provider,
)
_global_claim_service = ClaimService(
    insurance_repo=_global_insurance_repo,
    claim_repo=_global_claim_repo,
    auth_repo=_global_authorization_repo,
    provider=_global_mock_payer_provider,
)
_global_claim_response_service = ClaimResponseService(claim_repo=_global_claim_repo)
_global_claim_reconciliation_service = ClaimReconciliationService(
    claim_repo=_global_claim_repo,
    rec_repo=_global_claim_reconciliation_repo,
    provider=_global_mock_payer_provider,
)
_global_payer_webhook_service = PayerWebhookService(
    claim_repo=_global_claim_repo,
    auth_repo=_global_authorization_repo,
    webhook_repo=_global_payer_webhook_repo,
    provider=_global_mock_payer_provider,
)

# ---------------------------------------------------------------------------
# Phase 34: Laboratory, Diagnostic Orders & Result Management singletons
# ---------------------------------------------------------------------------
_settings = get_settings()
_global_diagnostic_catalog_repo = DiagnosticCatalogRepository()
_global_diagnostic_order_repo = DiagnosticOrderRepository()
_global_diagnostic_result_repo = DiagnosticResultRepository()
_global_diagnostic_report_repo = DiagnosticReportRepository()
_global_diagnostic_reconciliation_repo = DiagnosticReconciliationRepository()
_global_diagnostic_webhook_repo = DiagnosticWebhookRepository()
_global_mock_diagnostic_provider = MockDiagnosticProvider(
    provider_id="MOCK_LAB",
    secret=_settings.DIAGNOSTIC_PROVIDER_WEBHOOK_SECRET or "mock-diagnostic-webhook-secret-key-12345",
)
_global_diagnostic_validation_service = DiagnosticValidationService()
_global_diagnostic_authorization_service = DiagnosticAuthorizationService()
_global_diagnostic_catalog_service = DiagnosticCatalogService(
    catalog_repository=_global_diagnostic_catalog_repo,
    enabled=_settings.DIAGNOSTIC_CATALOG_ENABLED,
)
_global_diagnostic_order_service = DiagnosticOrderService(
    order_repository=_global_diagnostic_order_repo,
    catalog_repository=_global_diagnostic_catalog_repo,
    validation_service=_global_diagnostic_validation_service,
    authorization_service=_global_diagnostic_authorization_service,
    provider=_global_mock_diagnostic_provider if _settings.DIAGNOSTIC_PROVIDER_INTEGRATIONS_ENABLED else None,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    enabled=_settings.DIAGNOSTIC_ORDERING_ENABLED,
)
_global_diagnostic_result_service = DiagnosticResultService(
    result_repository=_global_diagnostic_result_repo,
    order_repository=_global_diagnostic_order_repo,
    validation_service=_global_diagnostic_validation_service,
    authorization_service=_global_diagnostic_authorization_service,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    enabled=_settings.DIAGNOSTIC_RESULT_PROCESSING_ENABLED,
    critical_notifications_enabled=_settings.CRITICAL_RESULT_NOTIFICATION_ENABLED,
)
_global_diagnostic_verification_service = DiagnosticVerificationService(
    result_repository=_global_diagnostic_result_repo,
    authorization_service=_global_diagnostic_authorization_service,
    audit_service=_global_audit_service,
)
_global_diagnostic_report_service = DiagnosticReportService(
    report_repository=_global_diagnostic_report_repo,
    authorization_service=_global_diagnostic_authorization_service,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
)
_global_diagnostic_reconciliation_service = DiagnosticReconciliationService(
    order_repository=_global_diagnostic_order_repo,
    result_repository=_global_diagnostic_result_repo,
    reconciliation_repository=_global_diagnostic_reconciliation_repo,
    audit_service=_global_audit_service,
)
_global_diagnostic_webhook_service = DiagnosticWebhookService(
    webhook_repository=_global_diagnostic_webhook_repo,
    order_repository=_global_diagnostic_order_repo,
    provider=_global_mock_diagnostic_provider,
    audit_service=_global_audit_service,
    secret=_settings.DIAGNOSTIC_PROVIDER_WEBHOOK_SECRET or "mock-diagnostic-webhook-secret-key-12345",
)

# ---------------------------------------------------------------------------
# Phase 35: Clinical Alerts & Escalation Management singletons
# ---------------------------------------------------------------------------
_global_alert_repo = AlertRepository()
_global_alert_escalation_repo = AlertEscalationRepository()
_global_alert_policy_repo = AlertPolicyRepository()
_global_local_alert_provider = LocalAlertProvider()
_global_alert_validation_service = AlertValidationService()
_global_alert_recipient_service = AlertRecipientService()
_global_alert_policy_service = AlertPolicyService(policy_repo=_global_alert_policy_repo)
_global_alert_escalation_service = AlertEscalationService(
    alert_repo=_global_alert_repo,
    escalation_repo=_global_alert_escalation_repo,
    recipient_service=_global_alert_recipient_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
    alert_provider=_global_local_alert_provider,
)
_global_alert_service = AlertService(
    alert_repo=_global_alert_repo,
    policy_service=_global_alert_policy_service,
    recipient_service=_global_alert_recipient_service,
    validation_service=_global_alert_validation_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
    alert_provider=_global_local_alert_provider,
)

# ---------------------------------------------------------------------------
# Phase 36: Clinical Tasks, Work Queues & Action Management singletons
# ---------------------------------------------------------------------------
_global_task_repo = TaskRepository()
_global_task_assignment_repo = TaskAssignmentRepository()
_global_task_validation_service = TaskValidationService()
_global_task_assignment_service = TaskAssignmentService(assignment_repo=_global_task_assignment_repo)
_global_task_dependency_service = TaskDependencyService(task_repo=_global_task_repo)
_global_task_escalation_service = TaskEscalationService(
    task_repo=_global_task_repo,
    alert_service=_global_alert_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
)
_global_task_service = TaskService(
    task_repo=_global_task_repo,
    assignment_repo=_global_task_assignment_repo,
    validation_service=_global_task_validation_service,
    assignment_service=_global_task_assignment_service,
    dependency_service=_global_task_dependency_service,
    alert_service=_global_alert_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
)

# ---------------------------------------------------------------------------
# Phase 37: Clinical Workflow Orchestration singletons
# ---------------------------------------------------------------------------
_global_workflow_repo = WorkflowRepository()
_global_workflow_step_repo = WorkflowStepRepository()
_global_workflow_def_service = WorkflowDefinitionService()
_global_workflow_val_service = WorkflowValidationService()
_global_workflow_step_service = WorkflowStepService(
    step_repo=_global_workflow_step_repo,
    val_service=_global_workflow_val_service,
    task_service=_global_task_service,
    alert_service=_global_alert_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
)
_global_workflow_approval_service = WorkflowApprovalService(
    workflow_repo=_global_workflow_repo,
    step_repo=_global_workflow_step_repo,
    val_service=_global_workflow_val_service,
    audit_service=_global_audit_service,
)
_global_workflow_service = WorkflowService(
    workflow_repo=_global_workflow_repo,
    step_repo=_global_workflow_step_repo,
    def_service=_global_workflow_def_service,
    step_service=_global_workflow_step_service,
    val_service=_global_workflow_val_service,
    approval_service=_global_workflow_approval_service,
    task_service=_global_task_service,
    alert_service=_global_alert_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
)

# Phase 38: Clinical Orders globals
_global_order_repo = OrderRepository()
_global_order_val_service = OrderValidationService()
_global_order_authz_service = OrderAuthorizationService()
_global_order_provider = MockOrderProvider()
_global_order_service = OrderService(
    order_repository=_global_order_repo,
    validation_service=_global_order_val_service,
    authorization_service=_global_order_authz_service,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    provider=_global_order_provider,
    enabled=_settings.CLINICAL_ORDERS_ENABLED,
)

# Phase 39: Clinical Order Sets globals
_global_order_set_repo = OrderSetRepository()
_global_order_set_val_service = OrderSetValidationService()
_global_order_set_authz_service = OrderSetAuthorizationService()
_global_order_set_service = OrderSetService(
    order_set_repository=_global_order_set_repo,
    validation_service=_global_order_set_val_service,
    authorization_service=_global_order_set_authz_service,
    order_service=_global_order_service,
    audit_service=_global_audit_service,
    enabled=_settings.ORDER_SETS_ENABLED,
    execution_enabled=_settings.ORDER_SET_EXECUTION_ENABLED,
    preview_enabled=_settings.ORDER_SET_PREVIEW_ENABLED,
    default_batch_policy=_settings.ORDER_SET_BATCH_POLICY,
)

# Phase 40: Clinical Order Review & Approvals globals
_global_approval_repo = ApprovalRepository()
_global_approval_policy_service = ApprovalPolicyService(enabled=_settings.APPROVALS_ENABLED)
_global_approval_authz_service = ApprovalAuthorizationService(
    user_repository=_global_user_repo,
    patient_repository=_global_patient_repo,
    enabled=_settings.APPROVALS_ENABLED,
)
_global_approval_service = ApprovalService(
    approval_repository=_global_approval_repo,
    policy_service=_global_approval_policy_service,
    authorization_service=_global_approval_authz_service,
    order_repository=_global_order_repo,
    order_service=_global_order_service,
    order_set_service=_global_order_set_service,
    task_service=_global_task_service,
    alert_service=_global_alert_service,
    notification_service=_global_notification_service,
    audit_service=_global_audit_service,
    enabled=_settings.APPROVALS_ENABLED,
    clinical_approvals_enabled=_settings.CLINICAL_APPROVALS_ENABLED,
    multi_approval_enabled=_settings.MULTI_APPROVAL_ENABLED,
    escalation_enabled=_settings.APPROVAL_ESCALATION_ENABLED,
    expiration_enabled=_settings.APPROVAL_EXPIRATION_ENABLED,
    delegation_enabled=_settings.APPROVAL_DELEGATION_ENABLED,
    tasks_enabled=_settings.APPROVAL_REVIEW_TASKS_ENABLED,
    default_expiration_hours=_settings.APPROVAL_DEFAULT_EXPIRATION_HOURS,
)

# Phase 41: Clinical Communication, Patient–Provider Messaging singletons
_global_conversation_repo = ConversationRepository()
_global_message_repo = MessageRepository()
_global_comm_provider = MockCommunicationProvider(name=_settings.COMMUNICATION_PROVIDER)
_global_conversation_authz_service = ConversationAuthorizationService(enabled=_settings.MESSAGING_ENABLED)
_global_comm_policy_service = CommunicationPolicyService(
    max_message_length=_settings.MESSAGE_MAX_LENGTH,
    max_attachment_size_bytes=_settings.MESSAGE_ATTACHMENT_MAX_SIZE_MB * 1024 * 1024,
    message_rate_limit=_settings.MESSAGE_RATE_LIMIT,
    conversation_rate_limit=_settings.CONVERSATION_RATE_LIMIT,
    enabled=_settings.MESSAGING_ENABLED,
)
_global_conversation_service = ConversationService(
    conversation_repository=_global_conversation_repo,
    authorization_service=_global_conversation_authz_service,
    policy_service=_global_comm_policy_service,
    audit_service=_global_audit_service,
    max_participants=_settings.CONVERSATION_MAX_PARTICIPANTS,
    enabled=_settings.MESSAGING_ENABLED,
)
_global_message_authz_service = MessageAuthorizationService(enabled=_settings.MESSAGING_ENABLED)
_global_message_delivery_service = MessageDeliveryService(
    message_repository=_global_message_repo,
    provider=_global_comm_provider,
    audit_service=_global_audit_service,
    webhook_secret=_settings.COMMUNICATION_WEBHOOK_SECRET,
    max_retries=_settings.MESSAGE_MAX_RETRIES,
    enabled=_settings.COMMUNICATION_PROVIDER_ENABLED,
)
_global_message_search_service = MessageSearchService(
    conversation_repository=_global_conversation_repo,
    message_repository=_global_message_repo,
    authorization_service=_global_conversation_authz_service,
    enabled=_settings.MESSAGING_ENABLED,
)
_global_message_service = MessageService(
    conversation_repository=_global_conversation_repo,
    message_repository=_global_message_repo,
    delivery_service=_global_message_delivery_service,
    conversation_authorization_service=_global_conversation_authz_service,
    message_authorization_service=_global_message_authz_service,
    policy_service=_global_comm_policy_service,
    audit_service=_global_audit_service,
    notification_service=_global_notification_service,
    task_service=_global_task_service,
    alert_service=_global_alert_service,
    workflow_service=_global_workflow_service,
    enabled=_settings.MESSAGING_ENABLED,
    ai_drafting_enabled=_settings.AI_MESSAGE_DRAFTING_ENABLED,
    translation_enabled=_settings.MESSAGE_TRANSLATION_ENABLED,
)


def get_user_repository() -> UserRepository:
    """Dependency provider for UserRepository."""
    return _global_user_repo


def get_auth_session_repository() -> AuthSessionRepository:
    """Dependency provider for AuthSessionRepository."""
    return _global_session_repo


# ---------------------------------------------------------------------------
# Phase 3: Repository providers
# ---------------------------------------------------------------------------

def get_consent_repository() -> ConsentRepository:
    """Dependency provider for ConsentRepository."""
    return _global_consent_repo


def get_audit_repository() -> AuditRepository:
    """Dependency provider for AuditRepository."""
    return _global_audit_repo


def get_permission_repository() -> PermissionRepository:
    """Dependency provider for PermissionRepository."""
    return _global_permission_repo


# ---------------------------------------------------------------------------
# Phase 4: Repository providers
# ---------------------------------------------------------------------------

def get_patient_repository() -> PatientRepository:
    """Dependency provider for PatientRepository."""
    return _global_patient_repo


def get_clinical_history_repository() -> ClinicalHistoryRepository:
    """Dependency provider for ClinicalHistoryRepository."""
    return _global_history_repo


def get_allergy_repository() -> AllergyRepository:
    """Dependency provider for AllergyRepository."""
    return _global_allergy_repo


def get_vitals_repository() -> VitalsRepository:
    """Dependency provider for VitalsRepository."""
    return _global_vitals_repo


def get_encounter_repository() -> EncounterRepository:
    """Dependency provider for EncounterRepository."""
    return _global_encounter_repo


# ---------------------------------------------------------------------------
# Phase 5: Repository & Integration providers
# ---------------------------------------------------------------------------

def get_document_repository() -> DocumentRepository:
    """Dependency provider for DocumentRepository."""
    return _global_document_repo


def get_document_storage() -> DocumentStorage:
    """Dependency provider for DocumentStorage."""
    return _global_document_storage


def get_security_scanner() -> DocumentSecurityScanner:
    """Dependency provider for DocumentSecurityScanner."""
    return _global_security_scanner


def get_processor_registry() -> DocumentProcessorRegistry:
    """Dependency provider for DocumentProcessorRegistry."""
    return _global_processor_registry


# ---------------------------------------------------------------------------
# Phase 6: Repository & Integration providers
# ---------------------------------------------------------------------------

def get_prescription_repository() -> PrescriptionRepository:
    """Dependency provider for PrescriptionRepository."""
    return _global_prescription_repo


def get_medication_repository() -> MedicationRepository:
    """Dependency provider for MedicationRepository."""
    return _global_medication_repo


def get_patient_medication_repository() -> PatientMedicationRepository:
    """Dependency provider for PatientMedicationRepository."""
    return _global_patient_medication_repo


def get_medication_terminology_provider() -> MedicationTerminologyProvider:
    """Dependency provider for MedicationTerminologyProvider."""
    settings = get_settings()
    if settings.MEDICATION_TERMINOLOGY_PROVIDER.lower() == "rxnorm":
        return RxNormProvider(
            base_url=settings.MEDICATION_TERMINOLOGY_BASE_URL or None,
            api_key=settings.MEDICATION_TERMINOLOGY_API_KEY or None,
            timeout_seconds=settings.MEDICATION_TERMINOLOGY_TIMEOUT_SECONDS,
            max_retries=settings.MEDICATION_NORMALIZATION_MAX_RETRIES,
        )
    return _global_medication_terminology_provider


def get_medication_safety_repository() -> MedicationSafetyRepository:
    """Dependency provider for MedicationSafetyRepository."""
    return _global_medication_safety_repo


def get_medication_safety_provider_dep() -> MedicationSafetyProvider:
    """Dependency provider for MedicationSafetyProvider."""
    return get_medication_safety_provider()


# ---------------------------------------------------------------------------
# Phase 8: Repository & Provider dependencies
# ---------------------------------------------------------------------------

def get_symptom_repository() -> SymptomRepository:
    """Dependency provider for SymptomRepository."""
    return _global_symptom_repo


def get_triage_repository() -> TriageRepository:
    """Dependency provider for TriageRepository."""
    return _global_triage_repo


def get_sbar_repository() -> SBARRepository:
    """Dependency provider for SBARRepository."""
    return _global_sbar_repo


def get_triage_engine() -> TriageRuleEngine:
    """Dependency provider for TriageRuleEngine."""
    return _global_triage_engine


def get_template_generator() -> ClinicalTextGenerator:
    """Dependency provider for TemplateClinicalTextGenerator."""
    return _global_template_generator


def get_ai_generator() -> ClinicalTextGenerator:
    """Dependency provider for AI ClinicalTextGenerator."""
    return _global_ai_generator


def get_sbar_validator() -> SBARFactValidator:
    """Dependency provider for SBARFactValidator."""
    return _global_sbar_validator


# ---------------------------------------------------------------------------
# Phase 9: Repository & Provider dependencies
# ---------------------------------------------------------------------------

def get_discharge_repository() -> DischargeRepository:
    """Dependency provider for DischargeRepository."""
    return _global_discharge_repo


def get_care_plan_repository() -> CarePlanRepository:
    """Dependency provider for CarePlanRepository."""
    return _global_care_plan_repo


def get_discharge_extractor() -> DischargeExtractor:
    """Dependency provider for DischargeExtractor."""
    return _global_discharge_extractor


# ---------------------------------------------------------------------------
# Phase 10: Repository providers
# ---------------------------------------------------------------------------

def get_clinical_note_repository() -> ClinicalNoteRepository:
    """Dependency provider for ClinicalNoteRepository."""
    return _global_clinical_note_repo


def get_clinical_assessment_repository() -> ClinicalAssessmentRepository:
    """Dependency provider for ClinicalAssessmentRepository."""
    return _global_clinical_assessment_repo


def get_clinical_plan_repository() -> ClinicalPlanRepository:
    """Dependency provider for ClinicalPlanRepository."""
    return _global_clinical_plan_repo


# ---------------------------------------------------------------------------
# Phase 1/2: Service providers
# ---------------------------------------------------------------------------

def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session_repo: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(user_repository=user_repo, session_repository=session_repo)


# ---------------------------------------------------------------------------
# Phase 3: Service providers
# ---------------------------------------------------------------------------

def get_audit_service(
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
) -> AuditService:
    """Dependency provider for AuditService."""
    return AuditService(audit_repository=audit_repo)


def get_consent_service(
    consent_repo: Annotated[ConsentRepository, Depends(get_consent_repository)],
) -> ConsentService:
    """Dependency provider for ConsentService."""
    return ConsentService(consent_repository=consent_repo)


def get_authorization_service(
    permission_repo: Annotated[PermissionRepository, Depends(get_permission_repository)] = None,
    consent_service: Annotated[ConsentService, Depends(get_consent_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> AuthorizationService:
    """Dependency provider for AuthorizationService."""
    return _global_authz_service


# ---------------------------------------------------------------------------
# Phase 4: Service providers
# ---------------------------------------------------------------------------

def get_patient_service(
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
) -> PatientService:
    """Dependency provider for PatientService."""
    return PatientService(patient_repository=patient_repo)


def get_clinical_record_service(
    history_repo: Annotated[ClinicalHistoryRepository, Depends(get_clinical_history_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    encounter_repo: Annotated[EncounterRepository, Depends(get_encounter_repository)],
) -> ClinicalRecordService:
    """Dependency provider for ClinicalRecordService."""
    return ClinicalRecordService(
        history_repo=history_repo,
        allergy_repo=allergy_repo,
        vitals_repo=vitals_repo,
        encounter_repo=encounter_repo,
    )


# ---------------------------------------------------------------------------
# Phase 5: Service providers
# ---------------------------------------------------------------------------

def get_document_service(
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    scanner: Annotated[DocumentSecurityScanner, Depends(get_security_scanner)],
) -> DocumentService:
    """Dependency provider for DocumentService."""
    settings = get_settings()
    return DocumentService(
        repository=doc_repo,
        storage=storage,
        scanner=scanner,
        max_size_bytes=settings.max_document_size_bytes,
    )


def get_document_processing_service(
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    registry: Annotated[DocumentProcessorRegistry, Depends(get_processor_registry)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentProcessingService:
    """Dependency provider for DocumentProcessingService."""
    settings = get_settings()
    return DocumentProcessingService(
        repository=doc_repo,
        storage=storage,
        registry=registry,
        audit_service=audit_service,
        max_retries=settings.MAX_PROCESSING_RETRIES,
    )


# ---------------------------------------------------------------------------
# Phase 6: Service providers
# ---------------------------------------------------------------------------

def get_medication_normalization_service(
    provider: Annotated[MedicationTerminologyProvider, Depends(get_medication_terminology_provider)],
    medication_repo: Annotated[MedicationRepository, Depends(get_medication_repository)],
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    prescription_repo: Annotated[PrescriptionRepository, Depends(get_prescription_repository)],
) -> MedicationNormalizationService:
    """Dependency provider for MedicationNormalizationService."""
    return MedicationNormalizationService(
        provider=provider,
        medication_repo=medication_repo,
        patient_medication_repo=patient_medication_repo,
        prescription_repo=prescription_repo,
    )


def get_prescription_service(
    prescription_repo: Annotated[PrescriptionRepository, Depends(get_prescription_repository)],
    medication_repo: Annotated[MedicationRepository, Depends(get_medication_repository)],
    document_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    normalization_service: Annotated[MedicationNormalizationService, Depends(get_medication_normalization_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> PrescriptionService:
    """Dependency provider for PrescriptionService."""
    return PrescriptionService(
        prescription_repo=prescription_repo,
        medication_repo=medication_repo,
        document_repo=document_repo,
        normalization_service=normalization_service,
        audit_service=audit_service,
    )


def get_medication_service(
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    medication_repo: Annotated[MedicationRepository, Depends(get_medication_repository)],
    provider: Annotated[MedicationTerminologyProvider, Depends(get_medication_terminology_provider)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> MedicationService:
    """Dependency provider for MedicationService."""
    return MedicationService(
        patient_medication_repo=patient_medication_repo,
        medication_repo=medication_repo,
        provider=provider,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# Phase 7: Medication Safety service provider
# ---------------------------------------------------------------------------

def get_medication_safety_service(
    safety_repo: Annotated[MedicationSafetyRepository, Depends(get_medication_safety_repository)],
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    medication_repo: Annotated[MedicationRepository, Depends(get_medication_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    clinical_history_repo: Annotated[ClinicalHistoryRepository, Depends(get_clinical_history_repository)],
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    provider: Annotated[MedicationSafetyProvider, Depends(get_medication_safety_provider_dep)],
) -> MedicationSafetyService:
    """Dependency provider for MedicationSafetyService."""
    return MedicationSafetyService(
        safety_repo=safety_repo,
        patient_medication_repo=patient_medication_repo,
        medication_repo=medication_repo,
        allergy_repo=allergy_repo,
        clinical_history_repo=clinical_history_repo,
        patient_repo=patient_repo,
        audit_service=audit_service,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Phase 8: Triage & SBAR service providers
# ---------------------------------------------------------------------------

def get_symptom_service(
    symptom_repo: Annotated[SymptomRepository, Depends(get_symptom_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> SymptomService:
    """Dependency provider for SymptomService."""
    return SymptomService(
        symptom_repo=symptom_repo,
        audit_service=audit_service,
    )


def get_triage_service(
    triage_repo: Annotated[TriageRepository, Depends(get_triage_repository)],
    symptom_repo: Annotated[SymptomRepository, Depends(get_symptom_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    rule_engine: Annotated[TriageRuleEngine, Depends(get_triage_engine)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
    clinical_history_repo: Annotated[ClinicalHistoryRepository, Depends(get_clinical_history_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
) -> TriageService:
    """Dependency provider for TriageService."""
    return TriageService(
        triage_repo=triage_repo,
        symptom_repo=symptom_repo,
        audit_service=audit_service,
        rule_engine=rule_engine,
        vitals_repo=vitals_repo,
        patient_repo=patient_repo,
        clinical_history_repo=clinical_history_repo,
        allergy_repo=allergy_repo,
        patient_medication_repo=patient_medication_repo,
    )


def get_sbar_service(
    sbar_repo: Annotated[SBARRepository, Depends(get_sbar_repository)],
    triage_repo: Annotated[TriageRepository, Depends(get_triage_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    template_generator: Annotated[ClinicalTextGenerator, Depends(get_template_generator)],
    ai_generator: Annotated[ClinicalTextGenerator, Depends(get_ai_generator)],
    validator: Annotated[SBARFactValidator, Depends(get_sbar_validator)],
    symptom_repo: Annotated[SymptomRepository, Depends(get_symptom_repository)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    clinical_history_repo: Annotated[ClinicalHistoryRepository, Depends(get_clinical_history_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    encounter_repo: Annotated[EncounterRepository, Depends(get_encounter_repository)],
) -> SBARService:
    """Dependency provider for SBARService."""
    return SBARService(
        sbar_repo=sbar_repo,
        triage_repo=triage_repo,
        audit_service=audit_service,
        template_generator=template_generator,
        ai_generator=ai_generator,
        validator=validator,
        symptom_repo=symptom_repo,
        vitals_repo=vitals_repo,
        clinical_history_repo=clinical_history_repo,
        allergy_repo=allergy_repo,
        patient_medication_repo=patient_medication_repo,
        encounter_repo=encounter_repo,
    )


# ---------------------------------------------------------------------------
# Phase 9: Service providers
# ---------------------------------------------------------------------------

def get_discharge_service(
    discharge_repo: Annotated[DischargeRepository, Depends(get_discharge_repository)],
    document_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    extractor: Annotated[DischargeExtractor, Depends(get_discharge_extractor)],
) -> DischargeService:
    """Dependency provider for DischargeService."""
    return DischargeService(
        discharge_repo=discharge_repo,
        document_repo=document_repo,
        audit_service=audit_service,
        extractor=extractor,
    )


def get_care_plan_service(
    care_plan_repo: Annotated[CarePlanRepository, Depends(get_care_plan_repository)],
    discharge_repo: Annotated[DischargeRepository, Depends(get_discharge_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> CarePlanService:
    """Dependency provider for CarePlanService."""
    return CarePlanService(
        care_plan_repo=care_plan_repo,
        discharge_repo=discharge_repo,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# Phase 10: Service providers
# ---------------------------------------------------------------------------

def get_clinical_note_service(
    note_repo: Annotated[ClinicalNoteRepository, Depends(get_clinical_note_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ClinicalNoteService:
    """Dependency provider for ClinicalNoteService."""
    return ClinicalNoteService(
        note_repo=note_repo,
        audit_service=audit_service,
    )


def get_clinical_assessment_service(
    assessment_repo: Annotated[ClinicalAssessmentRepository, Depends(get_clinical_assessment_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ClinicalAssessmentService:
    """Dependency provider for ClinicalAssessmentService."""
    return ClinicalAssessmentService(
        assessment_repo=assessment_repo,
        audit_service=audit_service,
    )


def get_clinical_plan_service(
    plan_repo: Annotated[ClinicalPlanRepository, Depends(get_clinical_plan_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ClinicalPlanService:
    """Dependency provider for ClinicalPlanService."""
    return ClinicalPlanService(
        plan_repo=plan_repo,
        audit_service=audit_service,
    )


def get_clinical_workspace_service(
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
    history_repo: Annotated[ClinicalHistoryRepository, Depends(get_clinical_history_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    encounter_repo: Annotated[EncounterRepository, Depends(get_encounter_repository)],
    document_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    prescription_repo: Annotated[PrescriptionRepository, Depends(get_prescription_repository)],
    patient_medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    safety_repo: Annotated[MedicationSafetyRepository, Depends(get_medication_safety_repository)],
    symptom_repo: Annotated[SymptomRepository, Depends(get_symptom_repository)],
    triage_repo: Annotated[TriageRepository, Depends(get_triage_repository)],
    sbar_repo: Annotated[SBARRepository, Depends(get_sbar_repository)],
    discharge_repo: Annotated[DischargeRepository, Depends(get_discharge_repository)],
    care_plan_repo: Annotated[CarePlanRepository, Depends(get_care_plan_repository)],
    note_repo: Annotated[ClinicalNoteRepository, Depends(get_clinical_note_repository)],
    assessment_repo: Annotated[ClinicalAssessmentRepository, Depends(get_clinical_assessment_repository)],
    plan_repo: Annotated[ClinicalPlanRepository, Depends(get_clinical_plan_repository)],
    note_service: Annotated[ClinicalNoteService, Depends(get_clinical_note_service)],
    assessment_service: Annotated[ClinicalAssessmentService, Depends(get_clinical_assessment_service)],
    plan_service: Annotated[ClinicalPlanService, Depends(get_clinical_plan_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ClinicalWorkspaceService:
    """Dependency provider for ClinicalWorkspaceService."""
    return ClinicalWorkspaceService(
        patient_repo=patient_repo,
        history_repo=history_repo,
        allergy_repo=allergy_repo,
        vitals_repo=vitals_repo,
        encounter_repo=encounter_repo,
        document_repo=document_repo,
        prescription_repo=prescription_repo,
        patient_medication_repo=patient_medication_repo,
        safety_repo=safety_repo,
        symptom_repo=symptom_repo,
        triage_repo=triage_repo,
        sbar_repo=sbar_repo,
        discharge_repo=discharge_repo,
        care_plan_repo=care_plan_repo,
        note_repo=note_repo,
        assessment_repo=assessment_repo,
        plan_repo=plan_repo,
        note_service=note_service,
        assessment_service=assessment_service,
        plan_service=plan_service,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# Phase 11: Repository providers
# ---------------------------------------------------------------------------

def get_organization_repository() -> OrganizationRepository:
    """Dependency provider for OrganizationRepository."""
    return _global_organization_repo


def get_facility_repository() -> FacilityRepository:
    """Dependency provider for FacilityRepository."""
    return _global_facility_repo


def get_department_repository() -> DepartmentRepository:
    """Dependency provider for DepartmentRepository."""
    return _global_department_repo


def get_directory_provider() -> HealthcareDirectoryProvider:
    """Dependency provider for HealthcareDirectoryProvider."""
    return _global_healthcare_directory_provider


# ---------------------------------------------------------------------------
# Phase 11: Service providers
# ---------------------------------------------------------------------------

def get_organization_access_service(
    org_repo: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> OrganizationAccessService:
    """Dependency provider for OrganizationAccessService."""
    return OrganizationAccessService(
        organization_repo=org_repo,
        audit_service=audit_service,
    )


def get_facility_access_service(
    facility_repo: Annotated[FacilityRepository, Depends(get_facility_repository)],
    org_repo: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> FacilityAccessService:
    """Dependency provider for FacilityAccessService."""
    return FacilityAccessService(
        facility_repo=facility_repo,
        organization_repo=org_repo,
        audit_service=audit_service,
    )


def get_organization_service(
    org_repo: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    facility_repo: Annotated[FacilityRepository, Depends(get_facility_repository)],
    org_access_service: Annotated[OrganizationAccessService, Depends(get_organization_access_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> OrganizationService:
    """Dependency provider for OrganizationService."""
    return OrganizationService(
        organization_repo=org_repo,
        facility_repo=facility_repo,
        organization_access_service=org_access_service,
        audit_service=audit_service,
    )


def get_facility_service(
    facility_repo: Annotated[FacilityRepository, Depends(get_facility_repository)],
    org_repo: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    dept_repo: Annotated[DepartmentRepository, Depends(get_department_repository)],
    facility_access_service: Annotated[FacilityAccessService, Depends(get_facility_access_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> FacilityService:
    """Dependency provider for FacilityService."""
    return FacilityService(
        facility_repo=facility_repo,
        organization_repo=org_repo,
        department_repo=dept_repo,
        facility_access_service=facility_access_service,
        audit_service=audit_service,
    )


def get_department_service(
    dept_repo: Annotated[DepartmentRepository, Depends(get_department_repository)],
    facility_repo: Annotated[FacilityRepository, Depends(get_facility_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> DepartmentService:
    """Dependency provider for DepartmentService."""
    return DepartmentService(
        department_repo=dept_repo,
        facility_repo=facility_repo,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# Phase 12: Repository & Service providers
# ---------------------------------------------------------------------------

def get_facility_discovery_repository() -> FacilityDiscoveryRepository:
    """Dependency provider for FacilityDiscoveryRepository."""
    return _global_facility_discovery_repo


def get_transfer_repository() -> TransferRepository:
    """Dependency provider for TransferRepository."""
    return _global_transfer_repo


def get_geographic_service() -> GeographicService:
    """Dependency provider for GeographicService."""
    return _global_geo_service


def get_facility_capability_service(
    discovery_repo: Annotated[FacilityDiscoveryRepository, Depends(get_facility_discovery_repository)],
) -> FacilityCapabilityService:
    """Dependency provider for FacilityCapabilityService."""
    return FacilityCapabilityService(discovery_repo=discovery_repo)


def get_facility_discovery_service(
    discovery_repo: Annotated[FacilityDiscoveryRepository, Depends(get_facility_discovery_repository)],
    capability_service: Annotated[FacilityCapabilityService, Depends(get_facility_capability_service)],
    geo_service: Annotated[GeographicService, Depends(get_geographic_service)],
    triage_repo: Annotated[TriageRepository, Depends(get_triage_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> FacilityDiscoveryService:
    """Dependency provider for FacilityDiscoveryService."""
    return FacilityDiscoveryService(
        discovery_repo=discovery_repo,
        capability_service=capability_service,
        geo_service=geo_service,
        triage_repo=triage_repo,
        audit_service=audit_service,
    )


def get_transfer_service(
    transfer_repo: Annotated[TransferRepository, Depends(get_transfer_repository)],
    facility_repo: Annotated[FacilityRepository, Depends(get_facility_repository)],
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
    encounter_repo: Annotated[EncounterRepository, Depends(get_encounter_repository)],
    consent_repo: Annotated[ConsentRepository, Depends(get_consent_repository)],
    sbar_repo: Annotated[SBARRepository, Depends(get_sbar_repository)],
    triage_repo: Annotated[TriageRepository, Depends(get_triage_repository)],
    symptom_repo: Annotated[SymptomRepository, Depends(get_symptom_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> TransferService:
    """Dependency provider for TransferService."""
    return TransferService(
        transfer_repo=transfer_repo,
        facility_repo=facility_repo,
        patient_repo=patient_repo,
        encounter_repo=encounter_repo,
        consent_repo=consent_repo,
        sbar_repo=sbar_repo,
        triage_repo=triage_repo,
        symptom_repo=symptom_repo,
        allergy_repo=allergy_repo,
        medication_repo=medication_repo,
        vitals_repo=vitals_repo,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# Phase 13: Repository & Service providers
# ---------------------------------------------------------------------------

def get_interoperability_repository() -> InteroperabilityRepository:
    """Dependency provider for InteroperabilityRepository."""
    return _global_interoperability_repo


def get_fhir_validator() -> FHIRValidator:
    """Dependency provider for FHIRValidator."""
    return _global_fhir_validator


def get_fhir_mapper() -> FHIRMapper:
    """Dependency provider for FHIRMapper."""
    return _global_fhir_mapper


def get_interoperability_provider() -> InteroperabilityProvider:
    """Dependency provider for InteroperabilityProvider."""
    return _global_interoperability_provider


def get_interoperability_service(
    interop_repo: Annotated[InteroperabilityRepository, Depends(get_interoperability_repository)],
    patient_repo: Annotated[PatientRepository, Depends(get_patient_repository)],
    allergy_repo: Annotated[AllergyRepository, Depends(get_allergy_repository)],
    medication_repo: Annotated[PatientMedicationRepository, Depends(get_patient_medication_repository)],
    vitals_repo: Annotated[VitalsRepository, Depends(get_vitals_repository)],
    encounter_repo: Annotated[EncounterRepository, Depends(get_encounter_repository)],
    document_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    consent_repo: Annotated[ConsentRepository, Depends(get_consent_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    fhir_mapper: Annotated[FHIRMapper, Depends(get_fhir_mapper)],
    fhir_validator: Annotated[FHIRValidator, Depends(get_fhir_validator)],
    provider: Annotated[InteroperabilityProvider, Depends(get_interoperability_provider)],
) -> InteroperabilityService:
    """Dependency provider for InteroperabilityService."""
    return InteroperabilityService(
        interop_repo=interop_repo,
        patient_repo=patient_repo,
        allergy_repo=allergy_repo,
        medication_repo=medication_repo,
        vitals_repo=vitals_repo,
        encounter_repo=encounter_repo,
        document_repo=document_repo,
        consent_repo=consent_repo,
        audit_service=audit_service,
        fhir_mapper=fhir_mapper,
        fhir_validator=fhir_validator,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Phase 2: Authentication dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedUserContext:
    """Reusable authentication dependency verifying JWT bearer tokens and caller context.

    Protected endpoints consume this dependency:
        current_user: AuthenticatedUserContext = Depends(get_current_user)
    """
    if credentials is None:
        raise UnauthorizedException("Authentication credentials were not provided.")

    if credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("Invalid authentication scheme. 'Bearer' required.")

    token = credentials.credentials
    if not token or not token.strip():
        raise UnauthorizedException("Invalid token format.")

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Token payload missing subject identifier.")

    user_context = await auth_service.get_user_context(str(user_id))
    return user_context


# ---------------------------------------------------------------------------
# Phase 3: Authorization dependencies
# ---------------------------------------------------------------------------

def require_permission(permission: Permission):
    """FastAPI dependency factory: require authenticated user to have a specific permission.

    Usage:
        @router.get("/resource")
        async def endpoint(
            _: None = Depends(require_permission(Permission.CLINICAL_RECORD_READ)),
            current_user: AuthenticatedUserContext = Depends(get_current_user),
        ):
            ...

    Note: This checks role → permission only. Ownership and consent are
    evaluated via require_resource_access() or AuthorizationService.authorize().
    """
    async def _dependency(
        current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
        authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    ) -> AuthenticatedUserContext:
        decision = await authz_service.check_permission(current_user, permission)
        if not decision.allowed:
            raise ForbiddenException("You do not have permission to perform this action.")
        return current_user

    return _dependency


def require_role(*roles: str):
    """FastAPI dependency factory: require authenticated user to have one of the given roles.

    Use sparingly. Prefer require_permission() for most authorization decisions.
    Use require_role() only when role-level gating is explicitly required by policy
    (e.g., only an ADMIN may invoke a specific management endpoint).

    Usage:
        @router.get("/admin/users")
        async def list_users(
            current_user: AuthenticatedUserContext = Depends(require_role("ADMIN")),
        ):
            ...
    """
    async def _dependency(
        current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ) -> AuthenticatedUserContext:
        if current_user.role.value not in {r.upper() for r in roles}:
            raise ForbiddenException("Your role does not permit this action.")
        return current_user

    return _dependency


def require_resource_access(
    action: str,
    resource_type: str | None = None,
    require_ownership: bool = False,
    require_relationship: bool = False,
    consent_purpose: str | None = None,
    consent_scope: str | None = None,
):
    """FastAPI dependency factory: full authorization evaluation for resource access.

    Evaluates the complete authorization pipeline:
      1. Authentication (get_current_user)
      2. Permission check (role → permission for action)
      3. Ownership check (if require_ownership=True)
      4. Relationship check (if require_relationship=True)
      5. Consent check (if consent_purpose + consent_scope provided)

    Resource-specific IDs (resource_id, resource_owner_id) must be passed
    at the route level because they are path parameters, not injectable at
    dependency creation time.

    Example — patient accesses their own profile (no consent required):
        Depends(require_resource_access("patient:read_self", require_ownership=True))

    Example — doctor reads a patient clinical record (needs relationship + consent):
        Depends(require_resource_access(
            "clinical_record:read",
            resource_type="clinical_record",
            require_relationship=True,
            consent_purpose="care_delivery",
            consent_scope="clinical_records",
        ))

    The returned dependency provides the AuthorizationContext so routes can
    pass resource-specific IDs to the service directly for more control.
    """
    async def _dependency(
        current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
        authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    ) -> AuthenticatedUserContext:
        # Build a base context — routes that need owner/resource IDs should
        # call authz_service.authorize_or_raise() directly for full control.
        context = AuthorizationContext(
            user_id=current_user.user_id,
            role=current_user.role.value,
            resource_type=resource_type,
        )
        await authz_service.authorize_or_raise(
            user=current_user,
            action=action,
            context=context,
            require_ownership=require_ownership,
            require_relationship=require_relationship,
            consent_purpose=consent_purpose,
            consent_scope=consent_scope,
        )
        return current_user

    return _dependency


# ---------------------------------------------------------------------------
# Phase 4: Patient access verification helper
# ---------------------------------------------------------------------------

async def verify_patient_access(
    patient_id: str,
    current_user: AuthenticatedUserContext,
    patient_service: PatientService,
    authz_service: AuthorizationService,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    consent_scope: str | None = "clinical_records",
) -> PatientResponse:
    """Evaluate patient access for current user.

    - PATIENT: verifies ownership (user_id matches patient record); raises NotFoundException if mismatch.
               evaluates authorize_or_raise with require_ownership=True.
    - DOCTOR: evaluates authorize_or_raise with require_relationship=True and consent.
    - ADMIN/OTHER: evaluates authorize_or_raise (will deny because admin has no clinical permissions).
    """
    if current_user.role == UserRole.PATIENT:
        patient = await patient_service.get_patient_record_for_user(current_user.user_id, patient_id)
        await authz_service.authorize_or_raise(
            user=current_user,
            action=action,
            context=AuthorizationContext(
                user_id=current_user.user_id,
                role=current_user.role.value,
                resource_type=resource_type,
                resource_id=resource_id or patient_id,
                resource_owner_id=current_user.user_id,
            ),
            require_ownership=True,
        )
        return patient

    elif current_user.role == UserRole.DOCTOR:
        patient = await patient_service.get_patient(patient_id)
        owner_id = patient.user_id or patient.id
        await authz_service.authorize_or_raise(
            user=current_user,
            action=action,
            context=AuthorizationContext(
                user_id=current_user.user_id,
                role=current_user.role.value,
                resource_type=resource_type,
                resource_id=resource_id or patient_id,
                resource_owner_id=owner_id,
            ),
            require_relationship=True,
            consent_purpose="care_delivery" if consent_scope is not None else None,
            consent_scope=consent_scope,
        )
        return patient

    else:
        await authz_service.authorize_or_raise(
            user=current_user,
            action=action,
            context=AuthorizationContext(
                user_id=current_user.user_id,
                role=current_user.role.value,
                resource_type=resource_type,
                resource_id=resource_id or patient_id,
            ),
        )
        return await patient_service.get_patient(patient_id)


# ---------------------------------------------------------------------------
# Phase 14: AI Intelligence Layer service provider
# ---------------------------------------------------------------------------

def get_ai_repository() -> AIRepository:
    """Dependency provider for AIRepository."""
    return _global_ai_repo


def get_ai_service(
    ai_repo: Annotated[AIRepository, Depends(get_ai_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> AIService:
    """Dependency provider for AIService (Phase 14 AI Orchestration)."""
    task_service = AITaskService(repository=ai_repo)
    validation_service = AIValidationService()
    provenance_service = AIProvenanceService()
    usage_service = AIUsageService(repository=ai_repo)
    return AIService(
        repository=ai_repo,
        audit_service=audit_service,
        task_service=task_service,
        validation_service=validation_service,
        provenance_service=provenance_service,
        usage_service=usage_service,
    )


# ---------------------------------------------------------------------------
# Phase 22: Asynchronous Workflow & Event-Driven service providers
# ---------------------------------------------------------------------------

def get_job_repository() -> JobRepository:
    """Dependency provider for JobRepository."""
    return _global_job_repo


def get_workflow_repository() -> WorkflowRepository:
    """Dependency provider for WorkflowRepository."""
    return _global_workflow_repo


def get_event_repository() -> EventRepository:
    """Dependency provider for EventRepository."""
    return _global_event_repo


def get_idempotency_repository() -> IdempotencyRepository:
    """Dependency provider for IdempotencyRepository."""
    return _global_idempotency_repo


def get_job_queue() -> JobQueueProvider:
    """Dependency provider for JobQueueProvider."""
    return get_job_queue_provider()


def get_event_bus() -> EventTransport:
    """Dependency provider for EventTransport."""
    return get_event_transport()


def get_idempotency_service(
    repo: Annotated[IdempotencyRepository, Depends(get_idempotency_repository)],
) -> IdempotencyService:
    """Dependency provider for IdempotencyService."""
    return IdempotencyService(repository=repo)


def get_event_service(
    repo: Annotated[EventRepository, Depends(get_event_repository)],
    transport: Annotated[EventTransport, Depends(get_event_bus)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> EventService:
    """Dependency provider for EventService."""
    return EventService(repository=repo, transport=transport, audit_service=audit_service)


def get_job_service(
    repo: Annotated[JobRepository, Depends(get_job_repository)],
    queue: Annotated[JobQueueProvider, Depends(get_job_queue)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> JobService:
    """Dependency provider for JobService."""
    return JobService(
        repository=repo,
        queue_provider=queue,
        idempotency_service=idempotency_service,
        audit_service=audit_service,
    )


def get_workflow_service(
    repo: Annotated[WorkflowRepository, Depends(get_workflow_repository)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> WorkflowService:
    """Dependency provider for WorkflowService."""
    return WorkflowService(repository=repo, audit_service=audit_service)


# ---------------------------------------------------------------------------
# Phase 24: Advanced Data Privacy & Governance dependency providers
# ---------------------------------------------------------------------------

def get_privacy_service() -> PrivacyService:
    """Dependency provider for PrivacyService."""
    return _global_privacy_service


def get_retention_service() -> RetentionService:
    """Dependency provider for RetentionService."""
    return _global_retention_service


def get_data_export_service() -> DataExportService:
    """Dependency provider for DataExportService."""
    return _global_data_export_service


def get_deidentification_service() -> DeidentificationService:
    """Dependency provider for DeidentificationService."""
    return _global_deidentification_service


def get_pseudonymization_service() -> PseudonymizationService:
    """Dependency provider for PseudonymizationService."""
    return _global_pseudonymization_service


# ---------------------------------------------------------------------------
# Phase 25: Feature Flags & Configuration Governance dependency providers
# ---------------------------------------------------------------------------

def get_feature_flag_service() -> FeatureFlagService:
    """Dependency provider for FeatureFlagService."""
    return _global_feature_flag_service


def get_configuration_service() -> ConfigurationService:
    """Dependency provider for ConfigurationService."""
    return _global_configuration_service


# ---------------------------------------------------------------------------
# Phase 26: Data Quality & Reconciliation dependency providers
# ---------------------------------------------------------------------------

def get_data_quality_repository() -> DataQualityRepository:
    """Dependency provider for DataQualityRepository."""
    return _global_data_quality_repo


def get_reconciliation_repository() -> ReconciliationRepository:
    """Dependency provider for ReconciliationRepository."""
    return _global_reconciliation_repo


def get_provenance_service() -> ProvenanceService:
    """Dependency provider for ProvenanceService."""
    return _global_provenance_service


def get_data_quality_service() -> DataQualityService:
    """Dependency provider for DataQualityService."""
    return _global_data_quality_service


def get_reconciliation_service() -> ReconciliationService:
    """Dependency provider for ReconciliationService."""
    return _global_reconciliation_service


# ---------------------------------------------------------------------------
# Phase 27: Administration, Support Operations & Backoffice dependency providers
# ---------------------------------------------------------------------------

def get_incident_repository() -> IncidentRepository:
    """Dependency provider for IncidentRepository."""
    return _global_incident_repo


def get_incident_service() -> IncidentService:
    """Dependency provider for IncidentService."""
    return _global_incident_service


def get_support_service() -> SupportService:
    """Dependency provider for SupportService."""
    return _global_support_service


def get_admin_service() -> AdminService:
    """Dependency provider for AdminService."""
    return _global_admin_service


# ---------------------------------------------------------------------------
# Phase 28: API Analytics, Usage Governance & Operational Intelligence providers
# ---------------------------------------------------------------------------

def get_analytics_repository() -> AnalyticsRepository:
    """Dependency provider for AnalyticsRepository."""
    return _global_analytics_repo


def get_analytics_service() -> AnalyticsService:
    """Dependency provider for AnalyticsService."""
    return _global_analytics_service


# ---------------------------------------------------------------------------
# Phase 29: Notification, Communication & Event Delivery System providers
# ---------------------------------------------------------------------------

def get_notification_repository() -> NotificationRepository:
    """Dependency provider for NotificationRepository."""
    return _global_notification_repo


def get_notification_delivery_repository() -> NotificationDeliveryRepository:
    """Dependency provider for NotificationDeliveryRepository."""
    return _global_notification_delivery_repo


def get_notification_preference_repository() -> NotificationPreferenceRepository:
    """Dependency provider for NotificationPreferenceRepository."""
    return _global_notification_preference_repo


def get_notification_template_service() -> NotificationTemplateService:
    """Dependency provider for NotificationTemplateService."""
    return _global_notification_template_service


def get_notification_preference_service() -> NotificationPreferenceService:
    """Dependency provider for NotificationPreferenceService."""
    return _global_notification_preference_service


def get_communication_service() -> CommunicationService:
    """Dependency provider for CommunicationService."""
    return _global_communication_service


def get_notification_service() -> NotificationService:
    """Dependency provider for NotificationService."""
    return _global_notification_service


# ---------------------------------------------------------------------------
# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval providers
# ---------------------------------------------------------------------------

def get_search_repository() -> SearchRepository:
    """Dependency provider for SearchRepository."""
    return _global_search_repo


def get_search_service() -> SearchService:
    """Dependency provider for SearchService."""
    return _global_search_service


# ---------------------------------------------------------------------------
# Phase 31: Scheduling, Appointment & Clinical Access Management providers
# ---------------------------------------------------------------------------

def get_appointment_repository() -> AppointmentRepository:
    """Dependency provider for AppointmentRepository."""
    return _global_appointment_repo


def get_availability_repository() -> AvailabilityRepository:
    """Dependency provider for AvailabilityRepository."""
    return _global_availability_repo


def get_schedule_repository() -> ScheduleRepository:
    """Dependency provider for ScheduleRepository."""
    return _global_schedule_repo


def get_scheduling_provider() -> SchedulingProvider:
    """Dependency provider for SchedulingProvider."""
    return _global_scheduling_provider


def get_appointment_validation_service() -> AppointmentValidationService:
    """Dependency provider for AppointmentValidationService."""
    return _global_appointment_validation_service


def get_appointment_authorization_service() -> AppointmentAuthorizationService:
    """Dependency provider for AppointmentAuthorizationService."""
    return _global_appointment_authorization_service


def get_availability_service() -> AvailabilityService:
    """Dependency provider for AvailabilityService."""
    return _global_availability_service


def get_appointment_service() -> AppointmentService:
    """Dependency provider for AppointmentService."""
    return _global_appointment_service


def get_scheduling_service() -> SchedulingService:
    """Dependency provider for SchedulingService."""
    return _global_scheduling_service


# ---------------------------------------------------------------------------
# Phase 32: Billing, Payments & Financial Transaction Management providers
# ---------------------------------------------------------------------------

def get_billing_repository() -> BillingRepository:
    """Dependency provider for BillingRepository."""
    return _global_billing_repo


def get_invoice_repository() -> InvoiceRepository:
    """Dependency provider for InvoiceRepository."""
    return _global_invoice_repo


def get_payment_repository() -> PaymentRepository:
    """Dependency provider for PaymentRepository."""
    return _global_payment_repo


def get_refund_repository() -> RefundRepository:
    """Dependency provider for RefundRepository."""
    return _global_refund_repo


def get_payment_provider() -> PaymentProvider:
    """Dependency provider for default PaymentProvider."""
    return _global_mock_payment_provider


def get_billing_authorization_service() -> BillingAuthorizationService:
    """Dependency provider for BillingAuthorizationService."""
    return _global_billing_authorization_service


def get_invoice_service() -> InvoiceService:
    """Dependency provider for InvoiceService."""
    return _global_invoice_service


def get_payment_service() -> PaymentService:
    """Dependency provider for PaymentService."""
    return _global_payment_service


def get_refund_service() -> RefundService:
    """Dependency provider for RefundService."""
    return _global_refund_service


def get_payment_webhook_service() -> PaymentWebhookService:
    """Dependency provider for PaymentWebhookService."""
    return _global_payment_webhook_service


def get_payment_reconciliation_service() -> PaymentReconciliationService:
    """Dependency provider for PaymentReconciliationService."""
    return _global_payment_reconciliation_service


# ---------------------------------------------------------------------------
# Phase 33: Insurance, Claims & Payer Integration providers
# ---------------------------------------------------------------------------

def get_insurance_repository() -> InsuranceRepository:
    """Dependency provider for InsuranceRepository."""
    return _global_insurance_repo


def get_eligibility_repository() -> EligibilityRepository:
    """Dependency provider for EligibilityRepository."""
    return _global_eligibility_repo


def get_benefit_repository() -> BenefitRepository:
    """Dependency provider for BenefitRepository."""
    return _global_benefit_repo


def get_authorization_repository() -> AuthorizationRepository:
    """Dependency provider for AuthorizationRepository."""
    return _global_authorization_repo


def get_claim_repository() -> ClaimRepository:
    """Dependency provider for ClaimRepository."""
    return _global_claim_repo


def get_claim_reconciliation_repository() -> ClaimReconciliationRepository:
    """Dependency provider for ClaimReconciliationRepository."""
    return _global_claim_reconciliation_repo


def get_payer_webhook_repository() -> PayerWebhookRepository:
    """Dependency provider for PayerWebhookRepository."""
    return _global_payer_webhook_repo


def get_payer_provider() -> PayerProvider:
    """Dependency provider for PayerProvider."""
    return _global_mock_payer_provider


def get_insurance_service() -> InsuranceService:
    """Dependency provider for InsuranceService."""
    return _global_insurance_service


def get_eligibility_service() -> EligibilityService:
    """Dependency provider for EligibilityService."""
    return _global_eligibility_service


def get_benefit_service() -> BenefitService:
    """Dependency provider for BenefitService."""
    return _global_benefit_service


def get_preauthorization_service() -> PreAuthorizationService:
    """Dependency provider for PreAuthorizationService."""
    return _global_preauthorization_service


def get_claim_service() -> ClaimService:
    """Dependency provider for ClaimService."""
    return _global_claim_service


def get_claim_response_service() -> ClaimResponseService:
    """Dependency provider for ClaimResponseService."""
    return _global_claim_response_service


def get_claim_reconciliation_service() -> ClaimReconciliationService:
    """Dependency provider for ClaimReconciliationService."""
    return _global_claim_reconciliation_service


def get_payer_webhook_service() -> PayerWebhookService:
    """Dependency provider for PayerWebhookService."""
    return _global_payer_webhook_service


# ---------------------------------------------------------------------------
# Phase 34: Laboratory, Diagnostic Orders & Result Management getters
# ---------------------------------------------------------------------------
def get_diagnostic_catalog_repository() -> DiagnosticCatalogRepository:
    """Dependency provider for DiagnosticCatalogRepository."""
    return _global_diagnostic_catalog_repo


def get_diagnostic_order_repository() -> DiagnosticOrderRepository:
    """Dependency provider for DiagnosticOrderRepository."""
    return _global_diagnostic_order_repo


def get_diagnostic_result_repository() -> DiagnosticResultRepository:
    """Dependency provider for DiagnosticResultRepository."""
    return _global_diagnostic_result_repo


def get_diagnostic_report_repository() -> DiagnosticReportRepository:
    """Dependency provider for DiagnosticReportRepository."""
    return _global_diagnostic_report_repo


def get_diagnostic_reconciliation_repository() -> DiagnosticReconciliationRepository:
    """Dependency provider for DiagnosticReconciliationRepository."""
    return _global_diagnostic_reconciliation_repo


def get_diagnostic_webhook_repository() -> DiagnosticWebhookRepository:
    """Dependency provider for DiagnosticWebhookRepository."""
    return _global_diagnostic_webhook_repo


def get_diagnostic_provider() -> DiagnosticProvider:
    """Dependency provider for DiagnosticProvider."""
    return _global_mock_diagnostic_provider


def get_diagnostic_validation_service() -> DiagnosticValidationService:
    """Dependency provider for DiagnosticValidationService."""
    return _global_diagnostic_validation_service


def get_diagnostic_authorization_service() -> DiagnosticAuthorizationService:
    """Dependency provider for DiagnosticAuthorizationService."""
    return _global_diagnostic_authorization_service


def get_diagnostic_catalog_service() -> DiagnosticCatalogService:
    """Dependency provider for DiagnosticCatalogService."""
    return _global_diagnostic_catalog_service


def get_diagnostic_order_service() -> DiagnosticOrderService:
    """Dependency provider for DiagnosticOrderService."""
    return _global_diagnostic_order_service


def get_diagnostic_result_service() -> DiagnosticResultService:
    """Dependency provider for DiagnosticResultService."""
    return _global_diagnostic_result_service


def get_diagnostic_verification_service() -> DiagnosticVerificationService:
    """Dependency provider for DiagnosticVerificationService."""
    return _global_diagnostic_verification_service


def get_diagnostic_report_service() -> DiagnosticReportService:
    """Dependency provider for DiagnosticReportService."""
    return _global_diagnostic_report_service


def get_diagnostic_reconciliation_service() -> DiagnosticReconciliationService:
    """Dependency provider for DiagnosticReconciliationService."""
    return _global_diagnostic_reconciliation_service


def get_diagnostic_webhook_service() -> DiagnosticWebhookService:
    """Dependency provider for DiagnosticWebhookService."""
    return _global_diagnostic_webhook_service


# ---------------------------------------------------------------------------
# Phase 35: Clinical Alerts & Escalation Getters
# ---------------------------------------------------------------------------

def get_alert_repository() -> AlertRepository:
    """Dependency provider for AlertRepository."""
    return _global_alert_repo


def get_alert_escalation_repository() -> AlertEscalationRepository:
    """Dependency provider for AlertEscalationRepository."""
    return _global_alert_escalation_repo


def get_alert_policy_repository() -> AlertPolicyRepository:
    """Dependency provider for AlertPolicyRepository."""
    return _global_alert_policy_repo


def get_alert_provider() -> AlertProvider:
    """Dependency provider for AlertProvider."""
    return _global_local_alert_provider


def get_alert_validation_service() -> AlertValidationService:
    """Dependency provider for AlertValidationService."""
    return _global_alert_validation_service


def get_alert_recipient_service() -> AlertRecipientService:
    """Dependency provider for AlertRecipientService."""
    return _global_alert_recipient_service


def get_alert_policy_service() -> AlertPolicyService:
    """Dependency provider for AlertPolicyService."""
    return _global_alert_policy_service


def get_alert_escalation_service() -> AlertEscalationService:
    """Dependency provider for AlertEscalationService."""
    return _global_alert_escalation_service


def get_alert_service() -> AlertService:
    """Dependency provider for AlertService."""
    return _global_alert_service


# ---------------------------------------------------------------------------
# Phase 36: Clinical Tasks & Work Queues Getters
# ---------------------------------------------------------------------------

def get_task_repository() -> TaskRepository:
    """Dependency provider for TaskRepository."""
    return _global_task_repo


def get_task_assignment_repository() -> TaskAssignmentRepository:
    """Dependency provider for TaskAssignmentRepository."""
    return _global_task_assignment_repo


def get_task_validation_service() -> TaskValidationService:
    """Dependency provider for TaskValidationService."""
    return _global_task_validation_service


def get_task_assignment_service() -> TaskAssignmentService:
    """Dependency provider for TaskAssignmentService."""
    return _global_task_assignment_service


def get_task_dependency_service() -> TaskDependencyService:
    """Dependency provider for TaskDependencyService."""
    return _global_task_dependency_service


def get_task_escalation_service() -> TaskEscalationService:
    """Dependency provider for TaskEscalationService."""
    return _global_task_escalation_service


def get_task_service() -> TaskService:
    """Dependency provider for TaskService."""
    return _global_task_service


# ---------------------------------------------------------------------------
# Phase 37: Clinical Workflow Orchestration Getters
# ---------------------------------------------------------------------------

def get_workflow_repository() -> WorkflowRepository:
    """Dependency provider for WorkflowRepository."""
    return _global_workflow_repo


def get_workflow_step_repository() -> WorkflowStepRepository:
    """Dependency provider for WorkflowStepRepository."""
    return _global_workflow_step_repo


def get_workflow_definition_service() -> WorkflowDefinitionService:
    """Dependency provider for WorkflowDefinitionService."""
    return _global_workflow_def_service


def get_workflow_validation_service() -> WorkflowValidationService:
    """Dependency provider for WorkflowValidationService."""
    return _global_workflow_val_service


def get_workflow_step_service() -> WorkflowStepService:
    """Dependency provider for WorkflowStepService."""
    return _global_workflow_step_service


def get_workflow_approval_service() -> WorkflowApprovalService:
    """Dependency provider for WorkflowApprovalService."""
    return _global_workflow_approval_service


def get_workflow_service() -> WorkflowService:
    """Dependency provider for WorkflowService."""
    return _global_workflow_service


# ---------------------------------------------------------------------------
# Phase 38: Clinical Orders, Results & Controlled Action Execution Getters
# ---------------------------------------------------------------------------

def get_order_repository() -> OrderRepository:
    """Dependency provider for OrderRepository."""
    return _global_order_repo


def get_order_validation_service() -> OrderValidationService:
    """Dependency provider for OrderValidationService."""
    return _global_order_val_service


def get_order_authorization_service() -> OrderAuthorizationService:
    """Dependency provider for OrderAuthorizationService."""
    return _global_order_authz_service


def get_order_provider() -> MockOrderProvider:
    """Dependency provider for OrderProvider."""
    return _global_order_provider


def get_order_service() -> OrderService:
    """Dependency provider for OrderService."""
    return _global_order_service


# ---------------------------------------------------------------------------
# Phase 39: Clinical Order Sets Getters
# ---------------------------------------------------------------------------

def get_order_set_repository() -> OrderSetRepository:
    """Dependency provider for OrderSetRepository."""
    return _global_order_set_repo


def get_order_set_validation_service() -> OrderSetValidationService:
    """Dependency provider for OrderSetValidationService."""
    return _global_order_set_val_service


def get_order_set_authorization_service() -> OrderSetAuthorizationService:
    """Dependency provider for OrderSetAuthorizationService."""
    return _global_order_set_authz_service


def get_order_set_service() -> OrderSetService:
    """Dependency provider for OrderSetService."""
    return _global_order_set_service


# ---------------------------------------------------------------------------
# Phase 40: Clinical Order Review & Approvals Getters
# ---------------------------------------------------------------------------

def get_approval_repository() -> ApprovalRepository:
    """Dependency provider for ApprovalRepository."""
    return _global_approval_repo


def get_approval_policy_service() -> ApprovalPolicyService:
    """Dependency provider for ApprovalPolicyService."""
    return _global_approval_policy_service


def get_approval_authorization_service() -> ApprovalAuthorizationService:
    """Dependency provider for ApprovalAuthorizationService."""
    return _global_approval_authz_service


def get_approval_service() -> ApprovalService:
    """Dependency provider for ApprovalService."""
    return _global_approval_service


# ---------------------------------------------------------------------------
# Phase 41: Clinical Communication, Patient–Provider Messaging Getters
# ---------------------------------------------------------------------------

def get_conversation_repository() -> ConversationRepository:
    """Dependency provider for ConversationRepository."""
    return _global_conversation_repo


def get_message_repository() -> MessageRepository:
    """Dependency provider for MessageRepository."""
    return _global_message_repo


def get_communication_provider() -> MockCommunicationProvider:
    """Dependency provider for CommunicationProvider."""
    return _global_comm_provider


def get_conversation_authorization_service() -> ConversationAuthorizationService:
    """Dependency provider for ConversationAuthorizationService."""
    return _global_conversation_authz_service


def get_communication_policy_service() -> CommunicationPolicyService:
    """Dependency provider for CommunicationPolicyService."""
    return _global_comm_policy_service


def get_conversation_service() -> ConversationService:
    """Dependency provider for ConversationService."""
    return _global_conversation_service


def get_message_authorization_service() -> MessageAuthorizationService:
    """Dependency provider for MessageAuthorizationService."""
    return _global_message_authz_service


def get_message_delivery_service() -> MessageDeliveryService:
    """Dependency provider for MessageDeliveryService."""
    return _global_message_delivery_service


def get_message_search_service() -> MessageSearchService:
    """Dependency provider for MessageSearchService."""
    return _global_message_search_service


def get_message_service() -> MessageService:
    """Dependency provider for MessageService."""
    return _global_message_service


