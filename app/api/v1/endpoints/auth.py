"""Authentication API endpoints for HealthSetu Phase 2."""

from datetime import date, datetime, timezone
import random
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import _global_patient_repo, get_auth_service, get_current_user
from app.core.logging import request_id_ctx_var
from app.core.security import hash_password
from app.core.user_profile_store import get_user_profile, save_user_profile
from app.repositories.patient_repository import PatientRecord
from app.repositories.user_repository import UserRecord
from app.schemas.auth import (
    AccountStatus,
    LoginRequest,
    LogoutRequest,
    LogoutResponseData,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponseData,
    UserRole,
)
from app.schemas.patient import BiologicalSex, PatientStatus
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext, UserIdentityResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


def _extract_request_id(request: Request) -> str:
    """Extract request correlation ID from request state or context variable."""
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "/login",
    response_model=StandardSuccessResponse[TokenResponseData],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": StandardErrorResponse,
            "description": "Invalid credentials or account inactive",
        },
        422: {
            "model": StandardErrorResponse,
            "description": "Request validation failed",
        },
    },
    summary="Authenticate with credentials",
    description=(
        "Authenticates a user using their identifier (email/username/phone) and password. "
        "Returns a short-lived access token and a rotatable refresh token."
    ),
)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> StandardSuccessResponse[TokenResponseData]:
    """Verify credentials and issue access and refresh tokens."""
    clean_id = payload.identifier.strip().lower()

    # Sync from persistent user profile store if user registered on another device/session and not yet in repo
    existing_user = await auth_service.user_repo.get_by_identifier(clean_id)
    if not existing_user:
        stored_profile = get_user_profile(clean_id)
        if stored_profile:
            pwd = payload.password or "StrongP@ssw0rd123!"
            role_enum = UserRole.PATIENT
            if stored_profile.get("role") == "doctor":
                role_enum = UserRole.DOCTOR
            elif stored_profile.get("role") == "hospital":
                role_enum = UserRole.ADMIN

            u_rec = UserRecord(
                id=stored_profile["id"],
                identifier=stored_profile.get("email") or clean_id,
                password_hash=hash_password(pwd),
                role=role_enum,
                status=AccountStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            auth_service.user_repo.register_in_memory_user(u_rec)
            auth_service.user_repo._local_users[stored_profile["id"].lower()] = u_rec
            if stored_profile.get("email"):
                auth_service.user_repo._local_users[stored_profile["email"].lower()] = u_rec

    token_data = await auth_service.authenticate(
        identifier=payload.identifier,
        password=payload.password,
    )
    req_id = _extract_request_id(request)
    return StandardSuccessResponse(data=token_data, request_id=req_id)


@router.post(
    "/register",
    response_model=StandardSuccessResponse[TokenResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Register user profile and mint unique HealthSetu ID",
    description="Registers a new Patient, Doctor, or Hospital Org identity, issuing a sovereign HealthSetu unique ID and session tokens.",
)
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> StandardSuccessResponse[TokenResponseData]:
    """Register identity, store in repository with unique ID, and return active tokens."""
    prefix_map = {
        "PATIENT": "HS-PAT",
        "DOCTOR": "HS-DOC",
        "ADMIN": "HS-HOSP",
    }
    role_key = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    unique_id = payload.unique_id or f"{prefix_map.get(role_key, 'HS-ID')}-{random.randint(1000, 9999)}"

    # Determine role string
    role_str = "patient"
    if role_key == "DOCTOR":
        role_str = "doctor"
    elif role_key in ("ADMIN", "HOSPITAL"):
        role_str = "hospital"

    # Create user record
    user_record = UserRecord(
        id=unique_id,
        identifier=payload.identifier,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status=AccountStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    auth_service.user_repo.register_in_memory_user(user_record)
    # Also register the unique ID as a valid login alias
    auth_service.user_repo._local_users[unique_id.lower()] = user_record

    # Save to cross-computer persistent profile store
    initials = "".join([part[0] for part in payload.name.split() if part])[:2].upper() or "HS"
    profile_data = {
        "id": unique_id,
        "name": payload.name,
        "role": role_str,
        "email": payload.identifier,
        "phone": payload.details.get("patient", {}).get("phone") if payload.details else None,
        "issuedAt": datetime.now(timezone.utc).strftime("%d %b %Y"),
        "avatarInitials": initials,
        "patientDetails": payload.details.get("patient") if payload.details else None,
        "doctorDetails": payload.details.get("doctor") if payload.details else None,
        "hospitalDetails": payload.details.get("hospital") if payload.details else None,
    }
    save_user_profile(profile_data)

    # If patient, create PatientRecord in _global_patient_repo
    if payload.role == UserRole.PATIENT:
        p_details = payload.details.get("patient", {}) if payload.details else {}
        name_parts = payload.name.strip().split()
        first_name = name_parts[0] if name_parts else "Patient"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        gender_raw = p_details.get("gender", "MALE").upper()
        sex = BiologicalSex.MALE if "MALE" in gender_raw else BiologicalSex.FEMALE if "FEMALE" in gender_raw else BiologicalSex.OTHER

        patient_rec = PatientRecord(
            id=unique_id,
            user_id=unique_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date(1990, 1, 1),
            sex=sex,
            status=PatientStatus.ACTIVE,
            phone=p_details.get("phone") or payload.identifier,
            email=payload.identifier if "@" in payload.identifier else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await _global_patient_repo.create(patient_rec)

    # Authenticate and issue token
    token_data = await auth_service.authenticate(
        identifier=payload.identifier,
        password=payload.password,
    )
    req_id = _extract_request_id(request)
    return StandardSuccessResponse(data=token_data, request_id=req_id)


@router.get(
    "/profile/{identifier}",
    summary="Look up user profile by sovereign unique ID or email",
    description="Cross-device endpoint allowing retrieval of registered user profile attributes.",
)
async def get_profile_by_identifier(
    identifier: str,
    request: Request,
) -> dict[str, Any]:
    """Retrieve full user profile by unique ID or email across computers."""
    profile = get_user_profile(identifier)
    if not profile:
        from app.core.exceptions import NotFoundException
        raise NotFoundException(f"Profile for '{identifier}' not found.")
    req_id = _extract_request_id(request)
    return {"success": True, "data": profile, "request_id": req_id}



@router.post(
    "/refresh",
    response_model=StandardSuccessResponse[TokenResponseData],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": StandardErrorResponse,
            "description": "Invalid, expired, or revoked refresh token",
        },
        422: {
            "model": StandardErrorResponse,
            "description": "Request validation failed",
        },
    },
    summary="Refresh access token",
    description=(
        "Validates the refresh token, executes token rotation, and issues a new access token "
        "and replacement refresh token."
    ),
)
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> StandardSuccessResponse[TokenResponseData]:
    """Rotate refresh token and issue new access token."""
    token_data = await auth_service.refresh_tokens(payload.refresh_token)
    req_id = _extract_request_id(request)
    return StandardSuccessResponse(data=token_data, request_id=req_id)


@router.post(
    "/logout",
    response_model=StandardSuccessResponse[LogoutResponseData],
    status_code=status.HTTP_200_OK,
    summary="Terminate session / logout",
    description="Revokes the specified refresh token session. Operation is idempotent.",
)
async def logout(
    request: Request,
    payload: LogoutRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> StandardSuccessResponse[LogoutResponseData]:
    """Terminate the authenticated session and invalidate refresh token."""
    logout_data = await auth_service.logout(refresh_token=payload.refresh_token)
    req_id = _extract_request_id(request)
    return StandardSuccessResponse(data=logout_data, request_id=req_id)


@router.get(
    "/me",
    response_model=StandardSuccessResponse[UserIdentityResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": StandardErrorResponse,
            "description": "Missing, invalid, or expired Bearer token",
        },
    },
    summary="Get current user identity",
    description="Returns the authenticated caller's identity, role, and operational account status.",
)
async def get_me(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[UserIdentityResponse]:
    """Return identity summary for the authenticated user."""
    identity = UserIdentityResponse(
        id=current_user.user_id,
        role=current_user.role,
        status=current_user.account_status,
    )
    req_id = _extract_request_id(request)
    return StandardSuccessResponse(data=identity, request_id=req_id)
