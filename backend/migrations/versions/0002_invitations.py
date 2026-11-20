"""Create organisation invitations."""

import sqlalchemy as sa
from alembic import op

revision = "0002_invitations"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organisation_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organisation_id",
            sa.Uuid(),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_email", sa.String(254), nullable=False),
        sa.Column("invited_role", sa.String(8), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_digest", name="uq_invitations_token_digest"),
        sa.CheckConstraint("invited_role IN ('manager', 'employee')", name="ck_invitations_role"),
        sa.CheckConstraint("expires_at > created_at", name="ck_invitations_expiry"),
        sa.CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL", name="ck_invitations_terminal_state"
        ),
    )
    op.create_index(
        "ix_invitations_organisation_email",
        "organisation_invitations",
        ["organisation_id", "invited_email"],
    )


def downgrade() -> None:
    op.drop_table("organisation_invitations")
