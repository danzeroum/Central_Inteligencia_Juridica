"""Modelos ORM da plataforma (Bloco 0 + Bloco B — fundação modular + canônico fiscal).

Tabelas criadas na fundação (Bloco 0):
  - tenant       : inquilino (empresa/escritório) multi-tenant
  - module       : módulo comercial registrável/licenciável
  - license      : licença que liga um tenant a um módulo
  - ledger_entry : trilha de decisões (backend Postgres do DecisionLedger)
  - fiscal_audit : trilha de operações fiscais (import/validate/generate/transmit)

Entidades canônicas (Bloco B — S-B.1):
  - periodo_fiscal     : período de competência (mensal/anual)
  - escrituracao_fiscal: escrituração canônica (SPED, XML, PDF, etc.)
  - registro_fiscal    : registro individual de escrituração SPED
  - documento_fiscal   : documento fiscal (NF-e, CT-e, NFS-e, DARF, guia)

Convenção LGPD: CNPJs e documentos são armazenados apenas na forma mascarada
(``document_masked`` / ``cnpj_masked``). O valor real nunca deve ser gravado.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String
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


# ─────────────────────────────────────────────────────────────────────────────
# Entidades canônicas — Bloco B (S-B.1)
# ─────────────────────────────────────────────────────────────────────────────


class PeriodoFiscal(Base):
    """Período de competência fiscal (mensal ou anual)."""

    __tablename__ = "periodo_fiscal"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    # mes = None → período anual
    mes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(
        String(16), nullable=False, default="mensal", server_default="mensal"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    escrituracoes: Mapped[List["EscrituracaoFiscal"]] = relationship(
        "EscrituracaoFiscal", back_populates="periodo"
    )

    __table_args__ = (Index("ix_periodo_fiscal_ano_mes", "ano", "mes"),)


class EscrituracaoFiscal(Base):
    """Escrituração fiscal canônica (SPED EFD-ICMS/IPI, EFD-Contrib., XML, PDF)."""

    __tablename__ = "escrituracao_fiscal"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("tenant.id"), nullable=True
    )
    periodo_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("periodo_fiscal.id"), nullable=False
    )
    # Tipo: efd_icms | efd_contrib | xml | pdf
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    # Origem: upload | api | worker
    origem: Mapped[str] = mapped_column(String(32), nullable=False)
    # Status: pendente | processando | concluido | erro
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pendente", server_default="pendente"
    )
    # Chave do arquivo no MinIO/S3
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # LGPD: somente o CNPJ mascarado
    cnpj_masked: Mapped[Optional[str]] = mapped_column(String(18), nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    periodo: Mapped["PeriodoFiscal"] = relationship(
        "PeriodoFiscal", back_populates="escrituracoes"
    )
    registros: Mapped[List["RegistroFiscal"]] = relationship(
        "RegistroFiscal", back_populates="escrituracao", cascade="all, delete-orphan"
    )
    documentos: Mapped[List["DocumentoFiscal"]] = relationship(
        "DocumentoFiscal", back_populates="escrituracao"
    )

    __table_args__ = (
        Index("ix_escrituracao_fiscal_tenant_id", "tenant_id"),
        Index("ix_escrituracao_fiscal_periodo_id", "periodo_id"),
        Index("ix_escrituracao_fiscal_tipo", "tipo"),
        Index("ix_escrituracao_fiscal_status", "status"),
        Index("ix_escrituracao_fiscal_created_at", "created_at"),
    )


class RegistroFiscal(Base):
    """Registro individual de uma escrituração SPED (linha parseada)."""

    __tablename__ = "registro_fiscal"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    escrituracao_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True),
        ForeignKey("escrituracao_fiscal.id"),
        nullable=False,
    )
    # Bloco SPED (ex: "0", "A", "C", "D", "E", "G", "H", "K")
    bloco: Mapped[str] = mapped_column(String(8), nullable=False)
    # Tipo de registro SPED (ex: "0000", "C100", "E110")
    tipo_registro: Mapped[str] = mapped_column(String(16), nullable=False)
    numero_linha: Mapped[int] = mapped_column(Integer, nullable=False)
    dados: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    escrituracao: Mapped["EscrituracaoFiscal"] = relationship(
        "EscrituracaoFiscal", back_populates="registros"
    )

    __table_args__ = (
        Index("ix_registro_fiscal_escrituracao_id", "escrituracao_id"),
        Index("ix_registro_fiscal_tipo_registro", "tipo_registro"),
        Index("ix_registro_fiscal_bloco", "bloco"),
    )


class DocumentoFiscal(Base):
    """Documento fiscal (NF-e, CT-e, NFS-e, DARF, guias, etc.)."""

    __tablename__ = "documento_fiscal"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    escrituracao_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SAUuid(as_uuid=True),
        ForeignKey("escrituracao_fiscal.id"),
        nullable=True,
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("tenant.id"), nullable=True
    )
    # Tipo: nfe | cte | nfse | darf | guia
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    numero_documento: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Chave de acesso NF-e/CT-e (44 dígitos)
    chave_acesso: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Status: pendente | processado | erro | cancelado
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pendente", server_default="pendente"
    )
    # Valor total como string para evitar perda de precisão float
    valor_total: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    escrituracao: Mapped[Optional["EscrituracaoFiscal"]] = relationship(
        "EscrituracaoFiscal", back_populates="documentos"
    )

    __table_args__ = (
        Index("ix_documento_fiscal_escrituracao_id", "escrituracao_id"),
        Index("ix_documento_fiscal_tenant_id", "tenant_id"),
        Index("ix_documento_fiscal_tipo", "tipo"),
        Index("ix_documento_fiscal_chave_acesso", "chave_acesso"),
        Index("ix_documento_fiscal_status", "status"),
    )
