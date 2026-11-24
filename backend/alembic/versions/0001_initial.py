from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("active_organization_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_organization_id"], ["organizations.id"], name=op.f("fk_users_active_organization_id_organizations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_organization_members_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_organization_members_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_members")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index(
        "ix_organization_members_org_role",
        "organization_members",
        ["organization_id", "role"],
        unique=False,
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_organization_invitations_organization_id_organizations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_invitations")),
        sa.UniqueConstraint("organization_id", "email", name="uq_org_invitations_org_email"),
        sa.UniqueConstraint("token", name="uq_org_invitations_token"),
    )
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("connection_status", sa.String(length=32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("permissions", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_integrations_organization_id_organizations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrations")),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_account_id",
            name="uq_integrations_org_provider_account",
        ),
    )
    op.create_index(
        "ix_integrations_org_provider",
        "integrations",
        ["organization_id", "provider"],
        unique=False,
    )
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_integration_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("deal_value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_data", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_leads_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["source_integration_id"], ["integrations.id"], name=op.f("fk_leads_source_integration_id_integrations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint(
            "organization_id",
            "source_integration_id",
            "external_id",
            name="uq_leads_org_source_external",
        ),
    )
    op.create_index("ix_leads_org_activity", "leads", ["organization_id", "last_activity_at"], unique=False)
    op.create_index("ix_leads_org_stage", "leads", ["organization_id", "stage"], unique=False)
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("initiated_by", sa.Uuid(), nullable=False),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("input_data", json_type, nullable=False),
        sa.Column("result", json_type, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["initiated_by"], ["users.id"], name=op.f("fk_agent_tasks_initiated_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_agent_tasks_organization_id_organizations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tasks")),
    )
    op.create_index(
        "ix_agent_tasks_org_created", "agent_tasks", ["organization_id", "created_at"], unique=False
    )
    op.create_table(
        "agent_task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_agent_task_events_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["agent_tasks.id"], name=op.f("fk_agent_task_events_task_id_agent_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_task_events")),
    )
    op.create_index(
        "ix_agent_task_events_task_created",
        "agent_task_events",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("finding_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("proposed_action", json_type, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_recommendations_lead_id_leads")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_recommendations_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["agent_tasks.id"], name=op.f("fk_recommendations_task_id_agent_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
    )
    op.create_index(
        "ix_recommendations_task_created", "recommendations", ["task_id", "created_at"], unique=False
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("action_payload", json_type, nullable=False),
        sa.Column("action_hash", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_approvals_approved_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_approvals_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendations.id"], name=op.f("fk_approvals_recommendation_id_recommendations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    op.create_index("ix_approvals_org_status", "approvals", ["organization_id", "status"], unique=False)
    op.create_table(
        "action_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_payload", json_type, nullable=False),
        sa.Column("response_payload", json_type, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_id"], ["approvals.id"], name=op.f("fk_action_executions_approval_id_approvals")
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["integrations.id"], name=op.f("fk_action_executions_integration_id_integrations")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_action_executions_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendations.id"], name=op.f("fk_action_executions_recommendation_id_recommendations")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["agent_tasks.id"], name=op.f("fk_action_executions_task_id_agent_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_executions")),
        sa.UniqueConstraint("idempotency_key", name="uq_action_executions_idempotency_key"),
    )
    op.create_index(
        "ix_action_executions_org_status", "action_executions", ["organization_id", "status"], unique=False
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_audit_logs_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_org_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_action_executions_org_status", table_name="action_executions")
    op.drop_table("action_executions")
    op.drop_index("ix_approvals_org_status", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_recommendations_task_created", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_agent_task_events_task_created", table_name="agent_task_events")
    op.drop_table("agent_task_events")
    op.drop_index("ix_agent_tasks_org_created", table_name="agent_tasks")
    op.drop_table("agent_tasks")
    op.drop_index("ix_leads_org_stage", table_name="leads")
    op.drop_index("ix_leads_org_activity", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_integrations_org_provider", table_name="integrations")
    op.drop_table("integrations")
    op.drop_table("organization_invitations")
    op.drop_index("ix_organization_members_org_role", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_table("users")
    op.drop_table("organizations")
