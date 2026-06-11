"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-11 00:00:00.000000

Cria as tabelas fundacionais da Onda 2:
  tenant, module, license, ledger_entry, fiscal_audit
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document_masked", sa.String(18), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "module",
        sa.Column("id", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "license",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("module_id", sa.String(128), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["module.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_license_tenant_id", "license", ["tenant_id"])
    op.create_index("ix_license_module_id", "license", ["module_id"])

    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("agent_type", sa.String(128), nullable=False),
        sa.Column("decision_type", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_readable", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_entry_agent_type", "ledger_entry", ["agent_type"])
    op.create_index("ix_ledger_entry_decision_type", "ledger_entry", ["decision_type"])
    op.create_index("ix_ledger_entry_timestamp", "ledger_entry", ["timestamp"])

    op.create_table(
        "fiscal_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_ref", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_audit_tenant_id", "fiscal_audit", ["tenant_id"])
    op.create_index("ix_fiscal_audit_operation", "fiscal_audit", ["operation"])
    op.create_index("ix_fiscal_audit_entity_ref", "fiscal_audit", ["entity_ref"])
    op.create_index("ix_fiscal_audit_status", "fiscal_audit", ["status"])
    op.create_index("ix_fiscal_audit_created_at", "fiscal_audit", ["created_at"])


def downgrade() -> None:
    op.drop_table("fiscal_audit")
    op.drop_index("ix_ledger_entry_timestamp", "ledger_entry")
    op.drop_index("ix_ledger_entry_decision_type", "ledger_entry")
    op.drop_index("ix_ledger_entry_agent_type", "ledger_entry")
    op.drop_table("ledger_entry")
    op.drop_index("ix_license_module_id", "license")
    op.drop_index("ix_license_tenant_id", "license")
    op.drop_table("license")
    op.drop_table("module")
    op.drop_table("tenant")
