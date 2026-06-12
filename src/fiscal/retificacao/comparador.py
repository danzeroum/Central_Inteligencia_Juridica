"""Comparador antes/depois de escriturações SPED retificadas (S-D.2).

Dado dois conjuntos de registros canônicos (original e retificado), produz
um resumo estruturado das diferenças: registros adicionados, removidos e
modificados.  A comparação é feita por ``tipo_registro + numero_linha``
como chave de identificação.

Não depende de banco de dados — opera sobre listas de dicts canônicos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _chave(rec: Dict[str, Any]) -> str:
    tipo = str(rec.get("tipo_registro", "")).upper()
    linha = rec.get("numero_linha", rec.get("linha", 0))
    return f"{tipo}:{linha}"


def _campos_diff(
    dados_orig: Optional[Dict[str, Any]],
    dados_ret: Optional[Dict[str, Any]],
) -> Dict[str, Tuple[Any, Any]]:
    """Retorna {campo: (valor_original, valor_retificado)} para campos que mudaram."""
    orig = dados_orig or {}
    ret = dados_ret or {}
    todos_campos = set(orig) | set(ret)
    return {
        c: (orig.get(c), ret.get(c)) for c in todos_campos if orig.get(c) != ret.get(c)
    }


@dataclass
class DiferencaRegistro:
    tipo_registro: str
    numero_linha: int
    campos_alterados: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class ComparacaoRetificacao:
    """Resultado da comparação entre escrituração original e retificada."""

    adicionados: List[Dict[str, Any]] = field(default_factory=list)
    removidos: List[Dict[str, Any]] = field(default_factory=list)
    modificados: List[DiferencaRegistro] = field(default_factory=list)

    @property
    def tem_diferencas(self) -> bool:
        return bool(self.adicionados or self.removidos or self.modificados)

    @property
    def total_alteracoes(self) -> int:
        return len(self.adicionados) + len(self.removidos) + len(self.modificados)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tem_diferencas": self.tem_diferencas,
            "total_alteracoes": self.total_alteracoes,
            "adicionados": self.adicionados,
            "removidos": self.removidos,
            "modificados": [
                {
                    "tipo_registro": d.tipo_registro,
                    "numero_linha": d.numero_linha,
                    "campos_alterados": {
                        campo: {"original": vals[0], "retificado": vals[1]}
                        for campo, vals in d.campos_alterados.items()
                    },
                }
                for d in self.modificados
            ],
        }

    def resumo_mudancas(self) -> Dict[str, Any]:
        """Resumo compacto apto para gravação em ``nota_correcao.resumo_mudancas``."""
        return {
            "total_adicionados": len(self.adicionados),
            "total_removidos": len(self.removidos),
            "total_modificados": len(self.modificados),
            "tipos_afetados": sorted(
                {r.get("tipo_registro", "") for r in self.adicionados + self.removidos}
                | {d.tipo_registro for d in self.modificados}
            ),
        }


def comparar_registros(
    originais: List[Dict[str, Any]],
    retificados: List[Dict[str, Any]],
) -> ComparacaoRetificacao:
    """Compara dois conjuntos de registros canônicos e retorna as diferenças.

    Cada registro deve ter pelo menos ``tipo_registro`` e ``numero_linha``
    (ou ``linha``). Registros são identificados pela chave composta
    ``tipo_registro:numero_linha``.
    """
    orig_map: Dict[str, Dict[str, Any]] = {_chave(r): r for r in originais}
    ret_map: Dict[str, Dict[str, Any]] = {_chave(r): r for r in retificados}

    chaves_orig = set(orig_map)
    chaves_ret = set(ret_map)

    adicionados = [ret_map[k] for k in sorted(chaves_ret - chaves_orig)]
    removidos = [orig_map[k] for k in sorted(chaves_orig - chaves_ret)]

    modificados: List[DiferencaRegistro] = []
    for chave in sorted(chaves_orig & chaves_ret):
        r_orig = orig_map[chave]
        r_ret = ret_map[chave]
        diff = _campos_diff(r_orig.get("dados"), r_ret.get("dados"))
        if diff:
            tipo = str(r_orig.get("tipo_registro", "")).upper()
            linha = int(r_orig.get("numero_linha", r_orig.get("linha", 0)))
            modificados.append(
                DiferencaRegistro(
                    tipo_registro=tipo,
                    numero_linha=linha,
                    campos_alterados=diff,
                )
            )

    return ComparacaoRetificacao(
        adicionados=adicionados,
        removidos=removidos,
        modificados=modificados,
    )
