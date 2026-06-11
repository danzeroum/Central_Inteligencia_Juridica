"""apuracao fiscal

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-11 00:00:00.000000

Apuração fiscal computada (Bloco C — S-C.2):
  apuracao_fiscal : resultado ICMS/PIS/COFINS por escrituração, com
                    totais, saldo, situação e divergências computado×declarado.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "apuracao_fiscal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("escrituracao_id", sa.Uuid(), nullable=False),
        sa.Column("periodo_id", sa.Uuid(), nullable=False),
        sa.Column("tributo", sa.String(16), nullable=False),
        sa.Column("periodo_competencia", sa.String(7), nullable=True),
        sa.Column("total_debitos", sa.String(24), nullable=False, server_default="0"),
        sa.Column("total_creditos", sa.String(24), nullable=False, server_default="0"),
        sa.Column(
            "saldo_credor_anterior", sa.String(24), nullable=False, server_default="0"
        ),
        sa.Column("saldo_apurado", sa.String(24), nullable=False, server_default="0"),
        sa.Column(
            "situacao",
            sa.String(16),
            nullable=False,
            server_default="equilibrado",
        ),
        sa.Column("divergencias", sa.JSON(), nullable=True),
        sa.Column("detalhes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escrituracao_id"], ["escrituracao_fiscal.id"]),
        sa.ForeignKeyConstraint(["periodo_id"], ["periodo_fiscal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_apuracao_fiscal_escrituracao_id", "apuracao_fiscal", ["escrituracao_id"]
    )
    op.create_index(
        "ix_apuracao_fiscal_periodo_id", "apuracao_fiscal", ["periodo_id"]
    )
    op.create_index("ix_apuracao_fiscal_tributo", "apuracao_fiscal", ["tributo"])
    op.create_index("ix_apuracao_fiscal_situacao", "apuracao_fiscal", ["situacao"])
    op.create_index(
        "ix_apuracao_fiscal_created_at", "apuracao_fiscal", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_apuracao_fiscal_created_at", "apuracao_fiscal")
    op.drop_index("ix_apuracao_fiscal_situacao", "apuracao_fiscal")
    op.drop_index("ix_apuracao_fiscal_tributo", "apuracao_fiscal")
    op.drop_index("ix_apuracao_fiscal_periodo_id", "apuracao_fiscal")
    op.drop_index("ix_apuracao_fiscal_escrituracao_id", "apuracao_fiscal")
    op.drop_table("apuracao_fiscal")
