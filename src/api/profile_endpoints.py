"""Endpoints de perfil de usuário — CIJ v1.1.0."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.rbac import Principal, current_principal
from src.profiles import (
    AreaJuridica,
    ClienteProfile,
    GenericUserProfile,
    ProfileRepository,
    Role,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

_repo = ProfileRepository()


# --- Request/Response models ---


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    oab_number: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_formality: Optional[str] = None
    nivel_tecnicidade: Optional[int] = None
    formato_saida_padrao: Optional[str] = None
    privacidade_enviar_llm: Optional[bool] = None
    notify_enabled: Optional[bool] = None
    especialidades: Optional[List[str]] = None


class AreaUpdateRequest(BaseModel):
    especialidades: List[str]


class ClienteCreateRequest(BaseModel):
    nome: str
    nivel_tecnicidade_saida: int = 3
    tipo_pessoa: str = "fisica"
    consentimento_lgpd: bool = False


# --- Helpers ---


def _profile_from_principal(principal: Principal) -> GenericUserProfile:
    return GenericUserProfile(
        user_id=principal.user_id,
        name=principal.user_id,
        role=Role.ADVOGADO,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


# --- Endpoints ---


@router.get("", response_model=Dict[str, Any])
async def get_profile(principal: Principal = Depends(current_principal)):
    profile = await _repo.get(principal.user_id)
    if profile is None:
        profile = _profile_from_principal(principal)
        await _repo.save(profile)
    return profile.model_dump()


@router.put("", response_model=Dict[str, Any])
async def update_profile(
    req: ProfileUpdateRequest,
    principal: Principal = Depends(current_principal),
):
    updates: Dict[str, Any] = {
        k: v for k, v in req.model_dump().items() if v is not None
    }
    if "especialidades" in updates:
        try:
            updates["especialidades"] = [
                AreaJuridica(a) for a in updates["especialidades"]
            ]
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Área inválida: {exc}"
            ) from exc

    profile = await _repo.update(principal.user_id, updates)
    if profile is None:
        base = _profile_from_principal(principal)
        for k, v in updates.items():
            setattr(base, k, v)
        await _repo.save(base)
        profile = base
    return profile.model_dump()


@router.get("/area", response_model=Dict[str, Any])
async def get_area(principal: Principal = Depends(current_principal)):
    profile = await _repo.get(principal.user_id)
    especialidades = profile.especialidades if profile else []
    return {"especialidades": [a.value for a in especialidades]}


@router.put("/area", response_model=Dict[str, Any])
async def update_area(
    req: AreaUpdateRequest,
    principal: Principal = Depends(current_principal),
):
    try:
        areas = [AreaJuridica(a) for a in req.especialidades]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Área inválida: {exc}") from exc

    profile = await _repo.update(principal.user_id, {"especialidades": areas})
    if profile is None:
        base = _profile_from_principal(principal)
        base.especialidades = areas
        await _repo.save(base)
        profile = base
    return {"especialidades": [a.value for a in profile.especialidades]}


@router.post("/clientes", response_model=Dict[str, Any], status_code=201)
async def create_cliente(
    req: ClienteCreateRequest,
    principal: Principal = Depends(current_principal),
):
    cliente = ClienteProfile(
        cliente_id=str(uuid.uuid4()),
        advogado_id=principal.user_id,
        nome=req.nome,
        nivel_tecnicidade_saida=req.nivel_tecnicidade_saida,
        tipo_pessoa=req.tipo_pessoa,
        consentimento_lgpd=req.consentimento_lgpd,
    )
    await _repo.save_client(cliente)
    return cliente.model_dump()


@router.get("/clientes", response_model=List[Dict[str, Any]])
async def list_clientes(principal: Principal = Depends(current_principal)):
    clientes = await _repo.list_clients(principal.user_id)
    return [c.model_dump() for c in clientes]


@router.get("/clientes/{cliente_id}", response_model=Dict[str, Any])
async def get_cliente(
    cliente_id: str,
    principal: Principal = Depends(current_principal),
):
    cliente = await _repo.get_client(principal.user_id, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente.model_dump()


@router.delete("", status_code=204)
async def delete_profile(principal: Principal = Depends(current_principal)):
    """LGPD Art. 18 — direito ao esquecimento."""
    deleted = await _repo.delete(principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")


__all__ = ["router"]
