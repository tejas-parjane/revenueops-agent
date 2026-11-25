from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_oauth_and_execution_safety"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("redirect_uri", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_oauth_states_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_states_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_states")),
        sa.UniqueConstraint("state_hash", name="uq_oauth_states_state_hash"),
    )
    op.create_index(
        "ix_oauth_states_org_provider_expires",
        "oauth_states",
        ["organization_id", "provider", "expires_at"],
        unique=False,
    )
    op.create_index("ix_leads_org_email", "leads", ["organization_id", "email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_org_email", table_name="leads")
    op.drop_index("ix_oauth_states_org_provider_expires", table_name="oauth_states")
    op.drop_table("oauth_states")
