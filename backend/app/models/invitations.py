from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganisationInvitation(Base):
    __tablename__ = "organisation_invitations"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_invitations_token_digest"),
        Index("ix_invitations_organisation_email", "organisation_id", "invited_email"),
        CheckConstraint("invited_role IN ('manager', 'employee')", name="ck_invitations_role"),
        CheckConstraint("expires_at > created_at", name="ck_invitations_expiry"),
        CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL", name="ck_invitations_terminal_state"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    invited_email: Mapped[str] = mapped_column(String(254))
    invited_role: Mapped[str] = mapped_column(String(8))
    token_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
