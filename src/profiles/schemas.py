"""Schemas de perfil de usuário e área jurídica (DOCX v1.1.0)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AreaJuridica(str, enum.Enum):
    TRABALHISTA = "trabalhista"
    PREVIDENCIARIO = "previdenciario"
    TRIBUTARIO = "tributario"
    CIVIL = "civil"
    PENAL = "penal"
    EMPRESARIAL = "empresarial"
    CONSUMIDOR = "consumidor"
    AMBIENTAL = "ambiental"
    ADMINISTRATIVO = "administrativo"
    CONSTITUCIONAL = "constitucional"
    FAMILIA_SUCESSOES = "familia_sucessoes"
    IMOBILIARIO = "imobiliario"
    CONTRATUAL = "contratual"
    DIGITAL = "digital"
    SERVIDOR_PUBLICO = "servidor_publico"
    SAUDE = "saude"
    JURIDICO_GENERICO = "juridico_generico"


class Role(str, enum.Enum):
    ADVOGADO = "advogado"
    PARALEGAL = "paralegal"
    ESTUDANTE = "estudante"
    CONSULTOR = "consultor"
    ADMIN = "admin"
    VIEWER = "viewer"


class GenericUserProfile(BaseModel):
    user_id: str
    profile_version: int = 1
    name: str
    oab_number: Optional[str] = None
    role: Role = Role.ADVOGADO
    preferred_language: str = "pt-BR"
    preferred_formality: Literal["formal", "accessible", "technical"] = "accessible"
    nivel_tecnicidade: int = Field(ge=1, le=5, default=3)
    formato_saida_padrao: str = "texto"
    privacidade_enviar_llm: bool = False
    notify_enabled: bool = True
    especialidades: List[AreaJuridica] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("nivel_tecnicidade")
    @classmethod
    def _check_tecnicidade(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("nivel_tecnicidade must be between 1 and 5")
        return v


class LegalAreaProfile(BaseModel):
    area_key: AreaJuridica
    name: str
    persona_prompt: str
    autores_referencia: List[str] = Field(default_factory=list)
    legislacao_principal: List[str] = Field(default_factory=list)
    tribunal_preferencial: Optional[str] = None
    analise_info: List[str] = Field(default_factory=list)
    interaction_style_default: Literal["detailed", "concise", "step_by_step"] = (
        "detailed"
    )
    response_format_hints: List[str] = Field(default_factory=list)


class ClienteProfile(BaseModel):
    cliente_id: str
    advogado_id: str
    nome: str
    nivel_tecnicidade_saida: int = Field(ge=1, le=5, default=3)
    tipo_pessoa: Literal["fisica", "juridica"] = "fisica"
    consentimento_lgpd: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("nivel_tecnicidade_saida")
    @classmethod
    def _check_tecnicidade(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("nivel_tecnicidade_saida must be between 1 and 5")
        return v


__all__ = [
    "AreaJuridica",
    "Role",
    "GenericUserProfile",
    "LegalAreaProfile",
    "ClienteProfile",
]
