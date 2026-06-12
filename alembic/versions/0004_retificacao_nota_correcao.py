"""retificacao nota correcao

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12 00:00:00.000000

S-D.2 — Retificação SPED ponta-a-ponta:
  escrituracao_fiscal.parent_id : rastreabilidade de versões retificadas
  nota_correcao                 : documenta motivo e resumo de mudanças
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "escrituracao_fiscal",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("escrituracao_fiscal.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_escrituracao_fiscal_parent_id",
        "escrituracao_fiscal",
        ["parent_id"],
    )

    op.create_table(
        "nota_correcao",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "escrituracao_original_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("escrituracao_fiscal.id"),
            nullable=False,
        ),
        sa.Column(
            "escrituracao_retificada_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("escrituracao_fiscal.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("motivo", sa.String(1000), nullable=False),
        sa.Column("resumo_mudancas", sa.JSON(), nullable=True),
        sa.Column("aprovado_por", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_nota_correcao_original_id",
        "nota_correcao",
        ["escrituracao_original_id"],
    )
    op.create_index(
        "ix_nota_correcao_retificada_id",
        "nota_correcao",
        ["escrituracao_retificada_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_nota_correcao_retificada_id", table_name="nota_correcao")
    op.drop_index("ix_nota_correcao_original_id", table_name="nota_correcao")
    op.drop_table("nota_correcao")
    op.drop_index(
        "ix_escrituracao_fiscal_parent_id", table_name="escrituracao_fiscal"
    )
    op.drop_column("escrituracao_fiscal", "parent_id")
