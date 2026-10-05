"""API Version 1 Router."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    ai,
    allergies,
    auth,
    care_plans,
    clinical_history,
    clinical_workflow,
    configuration,
    consents,
    data_quality,
    department,
    discharge,
    documents,
    encounters,
    facility,
    facility_discovery,
    health,
    interoperability,
    jobs,
    medications,
    medication_safety,
    metrics,
    organization,
    patients,
    prescriptions,
    privacy,
    sbar,
    symptoms,
    transfers,
    triage,
    vitals,
    admin,
    analytics,
    notifications,
    search,
    appointments,
    availability,
    invoices,
    payments,
    refunds,
    payment_webhooks,
    insurance,
    eligibility,
    benefits,
    authorizations,
    claims,
    payer_webhooks,
    diagnostic_catalog,
    diagnostic_orders,
    diagnostic_results,
    diagnostic_reports,
    diagnostic_webhooks,
    alerts,
    tasks,
    workflows,
    orders,
    order_sets,
)

v1_router = APIRouter()

# Register Phase 1 health and diagnostic endpoints
v1_router.include_router(health.router)

# Register Phase 2 identity & authentication endpoints
v1_router.include_router(auth.router)

# Register Phase 3 consent management endpoints
v1_router.include_router(consents.router)

# Register Phase 4 patient clinical record endpoints
v1_router.include_router(patients.router)
v1_router.include_router(clinical_history.router)
v1_router.include_router(allergies.router)
v1_router.include_router(vitals.router)
v1_router.include_router(encounters.router)

# Register Phase 5 medical document endpoints
v1_router.include_router(documents.router)

# Register Phase 6 prescription and medication endpoints
v1_router.include_router(prescriptions.router)
v1_router.include_router(medications.router)

# Register Phase 7 medication safety endpoints
v1_router.include_router(medication_safety.router)

# Register Phase 8 triage and SBAR endpoints
v1_router.include_router(symptoms.router)
v1_router.include_router(triage.router)
v1_router.include_router(sbar.router)

# Register Phase 9 care plan and discharge endpoints
v1_router.include_router(discharge.router)
v1_router.include_router(care_plans.router)

# Register Phase 10 doctor clinical workflow endpoints
v1_router.include_router(clinical_workflow.router)

# Register Phase 12 facility discovery (must be before facility detail router to avoid shadowing /facilities/discover)
v1_router.include_router(facility_discovery.router)

# Register Phase 11 hospital & organization network endpoints
v1_router.include_router(organization.router)
v1_router.include_router(facility.router)
v1_router.include_router(department.router)

# Register Phase 12 transfer endpoints
v1_router.include_router(transfers.router)

# Register Phase 13 interoperability & data exchange endpoints
v1_router.include_router(interoperability.router)

# Register Phase 14 AI Intelligence Layer endpoints
v1_router.include_router(ai.router)

# Register Phase 18 Observability & Metrics endpoint
v1_router.include_router(metrics.router)

# Register Phase 22 Asynchronous Job Orchestration endpoints
v1_router.include_router(jobs.router)

# Register Phase 24 Privacy, Retention & Data Governance endpoints
v1_router.include_router(privacy.router)

# Register Phase 25 Feature Flags & Configuration Governance endpoints
v1_router.include_router(configuration.router)

# Register Phase 26 Data Quality & Clinical Reconciliation endpoints
v1_router.include_router(data_quality.router)

# Register Phase 27 Administration, Support Operations & Controlled Backoffice endpoints
v1_router.include_router(admin.router)

# Register Phase 28 API Analytics, Usage Governance & Operational Intelligence endpoints
v1_router.include_router(analytics.router)

# Register Phase 29 Notification, Communication & Event Delivery endpoints
v1_router.include_router(notifications.router)

# Register Phase 30 Authorized Search, Indexing & Clinical Resource Retrieval endpoints
v1_router.include_router(search.router)

# Register Phase 31 Scheduling, Appointment & Clinical Access Management endpoints
v1_router.include_router(availability.router)
v1_router.include_router(appointments.router)

# Register Phase 32 Billing, Payments & Financial Transaction Management endpoints
v1_router.include_router(invoices.router)
v1_router.include_router(payments.router)
v1_router.include_router(refunds.router)
v1_router.include_router(payment_webhooks.router)

# Register Phase 33 Insurance, Claims & Payer Integration endpoints
v1_router.include_router(insurance.router)
v1_router.include_router(eligibility.router)
v1_router.include_router(benefits.router)
v1_router.include_router(authorizations.router)
v1_router.include_router(claims.router)
v1_router.include_router(payer_webhooks.router)

# Register Phase 34 Laboratory, Diagnostic Orders & Result Management endpoints
v1_router.include_router(diagnostic_catalog.router)
v1_router.include_router(diagnostic_orders.router)
v1_router.include_router(diagnostic_results.router)
v1_router.include_router(diagnostic_reports.router)
v1_router.include_router(diagnostic_webhooks.router)

# Register Phase 35 Clinical Alerts, Safety Notifications & Escalation Management endpoints
v1_router.include_router(alerts.router)

# Register Phase 36 Clinical Tasks, Work Queues & Action Management endpoints
v1_router.include_router(tasks.router)

# Register Phase 37 Clinical Workflow Orchestration & Order Management endpoints
v1_router.include_router(workflows.router)

# Register Phase 38 Clinical Orders, Results & Controlled Action Execution endpoints
v1_router.include_router(orders.router)
v1_router.include_router(orders.admin_router)

# Register Phase 39 Clinical Order Sets, Protocol Templates & Controlled Order Composition endpoints
v1_router.include_router(order_sets.router)
v1_router.include_router(order_sets.admin_router)
v1_router.include_router(order_sets.execution_router)


