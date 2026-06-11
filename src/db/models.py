"""Modelos ORM iniciais (Bloco 0 — fundação modular).

Tabelas criadas neste sprint:
  - tenant       : inquilino (empresa/escritório) multi-tenant
  - module       : módulo comercial registrável/licenciável
  - license      : licença que liga um tenant a um módulo
  - ledger_entry : trilha de decisões (backend Postgres do DecisionLedger)
  - fiscal_audit : trilha de operações fiscais (import/validate/generate/transmit)

Convenção LGPD: CNPJs e documentos são armazenados apenas na forma mascarada
(``document_masked``). O valor real nunca deve ser gravado nesta tabela.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """Inquilino (empresa ou escritório de advocacia) no modelo multi-tenant."""

    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # LGPD: apenas o CNPJ/CPF mascarado é armazenado (ex.: **.***.***/****-**)
    document_masked: Mapped[str] = mapped_column(String(18), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    licenses: Mapped[List["License"]] = relationship(
        "License", back_populates="tenant", cascade="all, delete-orphan"
    )
    fiscal_audits: Mapped[List["FiscalAudit"]] = relationship(
        "FiscalAudit", back_populates="tenant"
    )


class Module(Base):
    """Módulo comercial registrável/licenciável (ex.: 'inteligencia_juridica')."""

    __tablename__ = "module"

    # ID legível por humanos, corresponde ao manifest.module_id
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    licenses: Mapped[List["License"]] = relationship("License", back_populates="module")


class License(Base):
    """Licença que habilita um tenant a usar um módulo."""

    __tablename__ = "license"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    module_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("module.id"), nullable=False, index=True
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # None = licença perpétua
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="licenses")
    module: Mapped["Module"] = relationship("Module", back_populates="licenses")


class LedgerEntry(Base):
    """Entrada da trilha de decisões de agentes (backend Postgres do DecisionLedger).

    Espelha o formato de dict gravado pelos backends file/redis:
      id, agent_type, decision_type, metadata, timestamp, timestamp_readable
    """

    __tablename__ = "ledger_entry"

    # Mantém o formato original "decision_NNNNNN" para compat com file/redis
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_type: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # "metadata" é palavra reservada em alguns dialetos; coluna mapeada como metadata_
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_readable: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_ledger_entry_agent_type", "agent_type"),
        Index("ix_ledger_entry_decision_type", "decision_type"),
        Index("ix_ledger_entry_timestamp", "timestamp"),
    )


class FiscalAudit(Base):
    """Trilha imutável de operações fiscais (import → validate → calculate → generate → transmit).

    Reservada para uso nos Blocos B–F da Onda 2. Criada aqui para fixar o
    schema desde o sprint fundacional e permitir testes de migração.
    """

    __tablename__ = "fiscal_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # None quando o evento é de sistema (sem tenant específico)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("tenant.id"), nullable=True
    )
    # Etapa do pipeline: import | validate | calculate | generate | transmit
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    # Tipo de entidade: efd_icms | efd_contrib | xml | pdf | per_dcomp
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Referência de correlação (correlation_id do job / upload)
    entity_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # pending | processing | completed | failed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    tenant: Mapped[Optional["Tenant"]] = relationship(
        "Tenant", back_populates="fiscal_audits"
    )

    __table_args__ = (
        Index("ix_fiscal_audit_tenant_id", "tenant_id"),
        Index("ix_fiscal_audit_operation", "operation"),
        Index("ix_fiscal_audit_entity_ref", "entity_ref"),
        Index("ix_fiscal_audit_status", "status"),
        Index("ix_fiscal_audit_created_at", "created_at"),
    )
