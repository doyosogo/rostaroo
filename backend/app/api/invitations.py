import re
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.organisations import lock_user_for_onboarding, organisation_view, require_no_membership
from app.api.schemas import (
    InvitationAcceptance,
    InvitationCreated,
    InvitationInput,
    InvitationView,
    OrganisationView,
    TeamMemberView,
)
from app.api.security import DB, CurrentUser, require_trusted_origin
from app.models import Membership, Organisation, OrganisationInvitation, User
from app.services.auth import token_digest

router = APIRouter(tags=["team"])
trusted_origin = [Depends(require_trusted_origin)]
org_path = "/organisations/{organisation_id}"
INVITATION_LIFETIME = timedelta(days=7)


def team_management_role(organisation_id: UUID, user: CurrentUser, db: DB) -> str:
    role = db.scalar(
        select(Membership.role).where(
            Membership.organisation_id == organisation_id, Membership.user_id == user.id
        )
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Organisation was not found.")
    if role not in {"owner", "manager"}:
        raise HTTPException(status_code=403, detail="Team management requires an owner or manager.")
    return role


TeamManagement = Annotated[str, Depends(team_management_role)]


def pending_invitations(now: datetime):
    return (
        OrganisationInvitation.accepted_at.is_(None),
        OrganisationInvitation.revoked_at.is_(None),
        OrganisationInvitation.expires_at > now,
    )


def lock_organisation(db: Session, organisation_id: UUID) -> None:
    db.execute(
        select(Organisation.id)
        .where(Organisation.id == organisation_id)
        .with_for_update(key_share=True)
    )


def invalid_invitation() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="This invitation is invalid or no longer available. Check the code and signed-in email.",
    )


@router.get(f"{org_path}/members")
def list_members(organisation_id: UUID, _role: TeamManagement, db: DB) -> list[TeamMemberView]:
    rows = db.execute(
        select(User.id, User.email, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organisation_id == organisation_id)
        .order_by(User.email)
    )
    return [TeamMemberView.model_validate(row._mapping) for row in rows]


@router.post(f"{org_path}/invitations", status_code=201, dependencies=trusted_origin)
def create_invitation(
    organisation_id: UUID, payload: InvitationInput, role: TeamManagement, user: CurrentUser, db: DB
) -> InvitationCreated:
    if role == "manager" and payload.role != "employee":
        raise HTTPException(status_code=403, detail="Managers can only invite employees.")

    # Creation and acceptance in this organisation cannot race past the membership check.
    lock_organisation(db, organisation_id)
    existing_member = db.scalar(
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organisation_id == organisation_id, User.email == payload.email)
    )
    if existing_member is not None:
        raise HTTPException(status_code=409, detail="This email already belongs to the team.")

    now = datetime.now(UTC)
    pending = db.scalar(
        select(OrganisationInvitation.id).where(
            OrganisationInvitation.organisation_id == organisation_id,
            OrganisationInvitation.invited_email == payload.email,
            *pending_invitations(now),
        )
    )
    if pending is not None:
        raise HTTPException(
            status_code=409, detail="A pending invitation already exists for this email."
        )

    code = token_urlsafe(32)
    invitation = OrganisationInvitation(
        organisation_id=organisation_id,
        created_by_user_id=user.id,
        invited_email=payload.email,
        invited_role=payload.role,
        token_digest=token_digest(code),
        created_at=now,
        expires_at=now + INVITATION_LIFETIME,
    )
    db.add(invitation)
    db.commit()
    return InvitationCreated(**InvitationView.model_validate(invitation).model_dump(), code=code)


@router.get(f"{org_path}/invitations")
def list_invitations(organisation_id: UUID, role: TeamManagement, db: DB) -> list[InvitationView]:
    query = select(OrganisationInvitation).where(
        OrganisationInvitation.organisation_id == organisation_id,
        *pending_invitations(datetime.now(UTC)),
    )
    if role == "manager":
        query = query.where(OrganisationInvitation.invited_role == "employee")
    invitations = db.scalars(
        query.order_by(OrganisationInvitation.created_at.desc(), OrganisationInvitation.id)
    )
    return [InvitationView.model_validate(invitation) for invitation in invitations]


@router.post(
    f"{org_path}/invitations/{{invitation_id}}/revoke", status_code=204, dependencies=trusted_origin
)
def revoke_invitation(
    organisation_id: UUID, invitation_id: UUID, role: TeamManagement, db: DB
) -> None:
    query = select(OrganisationInvitation).where(
        OrganisationInvitation.organisation_id == organisation_id,
        OrganisationInvitation.id == invitation_id,
    )
    if role == "manager":
        query = query.where(OrganisationInvitation.invited_role == "employee")
    invitation = db.scalar(query.with_for_update())
    now = datetime.now(UTC)
    if invitation is None or not is_pending(invitation, now):
        raise HTTPException(status_code=404, detail="Pending invitation was not found.")
    invitation.revoked_at = now
    db.commit()


def is_pending(invitation: OrganisationInvitation, now: datetime) -> bool:
    return (
        invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > now
    )


@router.post("/invitations/accept", dependencies=trusted_origin)
def accept_invitation(payload: InvitationAcceptance, user: CurrentUser, db: DB) -> OrganisationView:
    code = payload.code.get_secret_value().strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", code) is None:
        raise invalid_invitation()

    match = (
        OrganisationInvitation.token_digest == token_digest(code),
        OrganisationInvitation.invited_email == user.email,
    )
    organisation_id = db.scalar(select(OrganisationInvitation.organisation_id).where(*match))
    if organisation_id is None:
        raise invalid_invitation()

    lock_user_for_onboarding(db, user.id)
    lock_organisation(db, organisation_id)
    invitation = db.scalar(select(OrganisationInvitation).where(*match).with_for_update())
    now = datetime.now(UTC)
    if invitation is None or not is_pending(invitation, now):
        raise invalid_invitation()
    require_no_membership(db, user.id)
    organisation = db.get(Organisation, invitation.organisation_id)
    if organisation is None:
        raise invalid_invitation()

    db.add(
        Membership(organisation_id=organisation.id, user_id=user.id, role=invitation.invited_role)
    )
    invitation.accepted_at = now
    db.commit()
    return organisation_view(organisation, invitation.invited_role)
