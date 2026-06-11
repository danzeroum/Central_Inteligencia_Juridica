"""canonical fiscal entities

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11 00:00:00.000000

Entidades canônicas do domínio fiscal (Bloco B — S-B.1):
  periodo_fiscal      : período de competência mensal/anual
  escrituracao_fiscal : escrituração canônica (SPED, XML, PDF)
  registro_fiscal     : registro individual de escrituração SPED
  documento_fiscal    : documento fiscal (NF-e, CT-e, NFS-e, DARF, guia)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "periodo_fiscal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(16), nullable=False, server_default="mensal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_periodo_fiscal_ano_mes", "periodo_fiscal", ["ano", "mes"])

    op.create_table(
        "escrituracao_fiscal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("periodo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("origem", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pendente",
        ),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("cnpj_masked", sa.String(18), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["periodo_id"], ["periodo_fiscal.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_escrituracao_fiscal_tenant_id", "escrituracao_fiscal", ["tenant_id"]
    )
    op.create_index(
        "ix_escrituracao_fiscal_periodo_id", "escrituracao_fiscal", ["periodo_id"]
    )
    op.create_index("ix_escrituracao_fiscal_tipo", "escrituracao_fiscal", ["tipo"])
    op.create_index("ix_escrituracao_fiscal_status", "escrituracao_fiscal", ["status"])
    op.create_index(
        "ix_escrituracao_fiscal_created_at", "escrituracao_fiscal", ["created_at"]
    )

    op.create_table(
        "registro_fiscal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("escrituracao_id", sa.Uuid(), nullable=False),
        sa.Column("bloco", sa.String(8), nullable=False),
        sa.Column("tipo_registro", sa.String(16), nullable=False),
        sa.Column("numero_linha", sa.Integer(), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escrituracao_id"], ["escrituracao_fiscal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registro_fiscal_escrituracao_id", "registro_fiscal", ["escrituracao_id"]
    )
    op.create_index(
        "ix_registro_fiscal_tipo_registro", "registro_fiscal", ["tipo_registro"]
    )
    op.create_index("ix_registro_fiscal_bloco", "registro_fiscal", ["bloco"])

    op.create_table(
        "documento_fiscal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("escrituracao_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("numero_documento", sa.String(64), nullable=True),
        sa.Column("chave_acesso", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pendente",
        ),
        sa.Column("valor_total", sa.String(20), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escrituracao_id"], ["escrituracao_fiscal.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documento_fiscal_escrituracao_id",
        "documento_fiscal",
        ["escrituracao_id"],
    )
    op.create_index("ix_documento_fiscal_tenant_id", "documento_fiscal", ["tenant_id"])
    op.create_index("ix_documento_fiscal_tipo", "documento_fiscal", ["tipo"])
    op.create_index(
        "ix_documento_fiscal_chave_acesso", "documento_fiscal", ["chave_acesso"]
    )
    op.create_index("ix_documento_fiscal_status", "documento_fiscal", ["status"])


def downgrade() -> None:
    op.drop_index("ix_documento_fiscal_status", "documento_fiscal")
    op.drop_index("ix_documento_fiscal_chave_acesso", "documento_fiscal")
    op.drop_index("ix_documento_fiscal_tipo", "documento_fiscal")
    op.drop_index("ix_documento_fiscal_tenant_id", "documento_fiscal")
    op.drop_index("ix_documento_fiscal_escrituracao_id", "documento_fiscal")
    op.drop_table("documento_fiscal")

    op.drop_index("ix_registro_fiscal_bloco", "registro_fiscal")
    op.drop_index("ix_registro_fiscal_tipo_registro", "registro_fiscal")
    op.drop_index("ix_registro_fiscal_escrituracao_id", "registro_fiscal")
    op.drop_table("registro_fiscal")

    op.drop_index("ix_escrituracao_fiscal_created_at", "escrituracao_fiscal")
    op.drop_index("ix_escrituracao_fiscal_status", "escrituracao_fiscal")
    op.drop_index("ix_escrituracao_fiscal_tipo", "escrituracao_fiscal")
    op.drop_index("ix_escrituracao_fiscal_periodo_id", "escrituracao_fiscal")
    op.drop_index("ix_escrituracao_fiscal_tenant_id", "escrituracao_fiscal")
    op.drop_table("escrituracao_fiscal")

    op.drop_index("ix_periodo_fiscal_ano_mes", "periodo_fiscal")
    op.drop_table("periodo_fiscal")
