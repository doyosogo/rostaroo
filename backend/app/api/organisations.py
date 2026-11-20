from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import MembershipRole, OrganisationInput, OrganisationView
from app.api.security import DB, CurrentUser, require_trusted_origin
from app.models import Membership, Organisation, User

router = APIRouter(prefix="/organisations", tags=["organisations"])


def membership_query(user_id: UUID):
    return (
        select(Organisation, Membership.role)
        .join(Membership, Membership.organisation_id == Organisation.id)
        .where(Membership.user_id == user_id)
    )


def organisation_view(organisation: Organisation, role: str) -> OrganisationView:
    return OrganisationView.model_validate(
        {
            "id": organisation.id,
            "name": organisation.name,
            "suburb": organisation.suburb,
            "state": organisation.state,
            "role": role,
        }
    )


def lock_user_for_onboarding(db: Session, user_id: UUID) -> None:
    # Organisation creation and invitation acceptance share this membership guard.
    db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))


def require_no_membership(db: Session, user_id: UUID) -> None:
    if db.scalar(select(Membership.user_id).where(Membership.user_id == user_id).limit(1)):
        raise HTTPException(status_code=409, detail="You already belong to an organisation.")


@router.get("")
def list_organisations(user: CurrentUser, db: DB) -> list[OrganisationView]:
    rows = db.execute(membership_query(user.id).order_by(Organisation.created_at, Organisation.id))
    return [organisation_view(organisation, role) for organisation, role in rows]


@router.get("/{organisation_id}")
def get_organisation(organisation_id: UUID, user: CurrentUser, db: DB) -> OrganisationView:
    row = db.execute(
        membership_query(user.id).where(Organisation.id == organisation_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Organisation was not found.")
    organisation, role = row
    return organisation_view(organisation, role)


@router.post("", status_code=201, dependencies=[Depends(require_trusted_origin)])
def create_organisation(payload: OrganisationInput, user: CurrentUser, db: DB) -> OrganisationView:
    lock_user_for_onboarding(db, user.id)
    require_no_membership(db, user.id)

    organisation = Organisation(name=payload.name, suburb=payload.suburb, state=payload.state)
    db.add(organisation)
    db.flush()
    role: MembershipRole = "owner"
    db.add(Membership(user_id=user.id, organisation_id=organisation.id, role=role))
    db.commit()
    return organisation_view(organisation, role)
