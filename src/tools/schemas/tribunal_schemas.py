"""Pydantic schemas para validação de respostas das APIs dos tribunais."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TribunalStatusResponse(BaseModel):
    """Schema para resposta de status do tribunal."""

    status: Literal["operacional", "instabilidade", "degradado", "offline"]
    ultima_atualizacao: str
    mensagem: str
    tempo_resposta: Optional[str] = None
    servicos_ativos: Optional[int] = Field(None, ge=0, le=100)

    @field_validator("ultima_atualizacao")
    @classmethod
    def validate_datetime_format(cls, v: str) -> str:
        """Valida que data está em formato ISO."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:  # pragma: no cover - pydantic handles message
            raise ValueError(f"Invalid datetime format: {v}") from exc
        return v


class ProcessoMovimentacao(BaseModel):
    """Schema para uma movimentação processual."""

    data: str
    descricao: str
    tipo: Optional[str] = None

    @field_validator("data")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Valida formato de data."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:  # pragma: no cover - pydantic handles message
            raise ValueError(f"Invalid date format: {v}") from exc
        return v


class ProcessoResponse(BaseModel):
    """Schema para resposta de consulta processual."""

    numero_processo: str
    situacao: str
    classe_processual: Optional[str] = None
    assunto: Optional[str] = None
    ultima_movimentacao: Optional[str] = None
    orgao_julgador: Optional[str] = None
    valor_causa: Optional[str] = None
    partes: Optional[List[Dict[str, Any]]] = None
    movimentacoes: Optional[List[ProcessoMovimentacao]] = None

    @field_validator("numero_processo")
    @classmethod
    def validate_process_number(cls, v: str) -> str:
        """Valida formato básico do número do processo."""
        if not v or len(v) < 5:
            raise ValueError("Invalid process number")
        return v


class ProcessoMovimentacoesResponse(BaseModel):
    """Schema para resposta de movimentações processuais."""

    numero_processo: str
    movimentacoes: List[ProcessoMovimentacao]
    total_movimentacoes: int = Field(ge=0)

    @field_validator("total_movimentacoes")
    @classmethod
    def validate_count_matches(cls, v: int, info) -> int:
        """Valida que total bate com número de movimentações."""
        movimentacoes = info.data.get("movimentacoes", [])
        if v != len(movimentacoes):
            raise ValueError(
                f"total_movimentacoes ({v}) doesn't match "
                f"movimentacoes length ({len(movimentacoes)})"
            )
        return v


if __name__ == "__main__":  # pragma: no cover
    # Teste de validação
    status = TribunalStatusResponse(
        status="operacional",
        ultima_atualizacao="2025-09-29T20:00:00Z",
        mensagem="Sistema funcionando",
        servicos_ativos=95,
    )
    print(f"✅ Status válido: {status.model_dump_json(indent=2)}")

    # Teste de validação que falha
    try:
        TribunalStatusResponse(
            status="operacional",
            ultima_atualizacao="invalid-date",  # ❌ Vai falhar
            mensagem="Test",
        )
    except ValueError as exc:
        print(f"✅ Validação funcionou: {exc}")
