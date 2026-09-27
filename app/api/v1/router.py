"""API Version 1 Router."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    ai,
    allergies,
    auth,
    care_plans,
    clinical_history,
    clinical_workflow,
    consents,
    department,
    discharge,
    documents,
    encounters,
    facility,
    facility_discovery,
    health,
    interoperability,
    medications,
    medication_safety,
    metrics,
    organization,
    patients,
    prescriptions,
    sbar,
    symptoms,
    transfers,
    triage,
    vitals,
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
