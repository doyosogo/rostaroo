from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, SecretStr

AustralianState = Literal["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]
MembershipRole = Literal["owner", "manager", "employee"]


def trimmed(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Use plain text without control characters.")
    return value


def normalised_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


NormalisedEmail = Annotated[EmailStr, BeforeValidator(normalised_email), Field(max_length=254)]
InvitationRole = Literal["manager", "employee"]


class LoginInput(BaseModel):
    email: NormalisedEmail
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class RegistrationInput(LoginInput):
    password: Annotated[SecretStr, Field(min_length=15, max_length=128)]


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str


class OrganisationInput(BaseModel):
    name: Annotated[str, BeforeValidator(trimmed), Field(min_length=2, max_length=100)]
    suburb: Annotated[str, BeforeValidator(trimmed), Field(min_length=2, max_length=80)]
    state: AustralianState


class OrganisationView(OrganisationInput):
    id: UUID
    role: MembershipRole


class TeamMemberView(UserView):
    role: MembershipRole


class InvitationInput(BaseModel):
    email: NormalisedEmail
    role: InvitationRole


class InvitationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invited_email: str
    invited_role: InvitationRole
    expires_at: datetime


class InvitationCreated(InvitationView):
    code: str


class InvitationAcceptance(BaseModel):
    code: Annotated[SecretStr, Field(max_length=128)]
