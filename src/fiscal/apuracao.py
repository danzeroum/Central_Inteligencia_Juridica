"""Motor de apuração ICMS/PIS/COFINS (Bloco C — S-C.2 Parte B).

Stateless: recebe SpedRecords parseados e retorna ItemApuracao por tributo.
Confronto computado × declarado via E110 (ICMS) e M200/M600 (PIS/COFINS).

Uso:
    engine = get_apuracao_engine()
    resultado = engine.calcular(parse_result.records, tipo="efd_icms")
    for item in resultado.items:
        print(item.tributo, item.situacao, item.saldo_apurado)

TODO(S-C.5): ICMS-ST (E300..E316), IPI (E520..E530)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from .reconciliation import Severidade
from .parser.base import SpedRecord

# Documentos cancelados/denegados — ignorar na apuração
_SITUS_CANCELADOS: frozenset = frozenset(
    {"5", "6", "7", "8", "02", "05", "06", "07", "08"}
)

# Tolerância de R$ 1,00 para divergências computado × declarado
_TOLERANCIA = Decimal("1.00")


def _to_dec(value: Any) -> Decimal:
    """Convert SPED decimal string (vírgula) or XML decimal (ponto) to Decimal."""
    try:
        s = str(value or "").strip()
        if not s:
            return Decimal("0")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _load_apuracao_config() -> Dict[str, str]:
    import yaml
    from pathlib import Path

    cfg_path = (
        Path(__file__).parent.parent.parent
        / "config"
        / "fiscal"
        / "rules"
        / "base.yaml"
    )
    try:
        data = yaml.safe_load(cfg_path.read_text())
        return data.get("apuracao_config", {})
    except Exception:
        return {}


_apuracao_config: Dict[str, str] = {}


def _get_aliq(key: str, default: str) -> Decimal:
    global _apuracao_config
    if not _apuracao_config:
        _apuracao_config = _load_apuracao_config()
    return Decimal(_apuracao_config.get(key, default))


# ─────────────────────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DivergenciaApuracao:
    """Divergência entre valor computado (C100/E110/M200/M600) e declarado."""

    campo: str
    valor_computado: str
    valor_declarado: str
    diferenca: str
    severidade: Severidade

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campo": self.campo,
            "valor_computado": self.valor_computado,
            "valor_declarado": self.valor_declarado,
            "diferenca": self.diferenca,
            "severidade": self.severidade.value,
        }


@dataclass
class ItemApuracao:
    """Resultado de apuração de um tributo em um período."""

    tributo: str
    periodo: str
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_credor_anterior: Decimal
    saldo_apurado: Decimal
    situacao: str  # "devedor" | "credor" | "equilibrado"
    divergencias: List[DivergenciaApuracao] = field(default_factory=list)
    detalhes: Dict[str, Any] = field(default_factory=dict)
    ajustes_debito: Decimal = Decimal("0")
    ajustes_credito: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tributo": self.tributo,
            "periodo": self.periodo,
            "total_debitos": str(self.total_debitos),
            "total_creditos": str(self.total_creditos),
            "saldo_credor_anterior": str(self.saldo_credor_anterior),
            "saldo_apurado": str(self.saldo_apurado),
            "situacao": self.situacao,
            "divergencias": [d.to_dict() for d in self.divergencias],
            "detalhes": self.detalhes,
            "ajustes_debito": str(self.ajustes_debito),
            "ajustes_credito": str(self.ajustes_credito),
        }


@dataclass
class ResultadoApuracao:
    """Resultado da apuração de todos os tributos de uma escrituração."""

    aprovado: bool
    items: List[ItemApuracao] = field(default_factory=list)
    resumo: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aprovado": self.aprovado,
            "items": [i.to_dict() for i in self.items],
            "resumo": self.resumo,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Motor
# ─────────────────────────────────────────────────────────────────────────────


class ApuracaoEngine:
    """Motor de apuração fiscal ICMS/PIS/COFINS (stateless)."""

    def _periodo_from_records(self, records: List[SpedRecord]) -> str:
        for r in records:
            if r.tipo_registro == "0000":
                dt_ini = str(r.campos.get("dt_ini") or "")
                if dt_ini and len(dt_ini) >= 7:
                    return dt_ini[:7]
        return ""

    def calcular_icms(
        self,
        records: List[SpedRecord],
        saldo_credor_anterior: Decimal = Decimal("0"),
    ) -> ItemApuracao:
        """Apura ICMS a partir de C100/D100 e confronta com E110.

        ind_oper="1" (saída) → débito; ind_oper="0" (entrada) → crédito.
        Documentos cancelados (cod_sit 5-8) são ignorados.
        TODO(S-C.5): ICMS-ST (E300..E316), IPI (E520..E530)
        """
        debitos = Decimal("0")
        creditos = Decimal("0")
        e110: Optional[Dict[str, Any]] = None
        n_c100 = 0
        e110_found = False

        for record in records:
            if record.tipo_registro in ("C100", "D100"):
                n_c100 += 1
                campos = record.campos
                cod_sit = str(campos.get("cod_sit") or "").strip()
                if cod_sit in _SITUS_CANCELADOS:
                    continue
                ind_oper = str(campos.get("ind_oper") or "").strip()
                vl_icms = _to_dec(campos.get("vl_icms"))
                if ind_oper == "1":
                    debitos += vl_icms
                elif ind_oper == "0":
                    creditos += vl_icms
            elif record.tipo_registro == "E110":
                e110 = record.campos
                e110_found = True

        ajustes_debito = Decimal("0")
        ajustes_credito = Decimal("0")
        avisos_ajuste: List[str] = []
        e111_count = 0
        e112_count = 0
        e113_count = 0

        for record in records:
            if record.tipo_registro == "E111":
                e111_count += 1
                cod = str(record.campos.get("cod_aj_apur") or "")
                vl = _to_dec(record.campos.get("vl_aj_apur"))
                if len(cod) >= 3:
                    natureza = cod[2]
                    if natureza == "1":
                        ajustes_debito += vl
                    elif natureza == "2":
                        ajustes_credito += vl
                    else:
                        avisos_ajuste.append(cod)
                else:
                    avisos_ajuste.append(cod or "(vazio)")
            elif record.tipo_registro == "E112":
                e112_count += 1
            elif record.tipo_registro == "E113":
                e113_count += 1

        saldo_apurado = (
            debitos
            - creditos
            + ajustes_debito
            - ajustes_credito
            - saldo_credor_anterior
        )
        situacao = (
            "devedor"
            if saldo_apurado > 0
            else "credor" if saldo_apurado < 0 else "equilibrado"
        )

        divergencias: List[DivergenciaApuracao] = []

        if e111_count > 0 and not e110_found:
            divergencias.append(
                DivergenciaApuracao(
                    campo="E111",
                    valor_computado="E111 sem E110 correspondente",
                    valor_declarado="E110 obrigatório",
                    diferenca="estrutura",
                    severidade=Severidade.ERRO,
                )
            )

        for cod_inv in avisos_ajuste:
            divergencias.append(
                DivergenciaApuracao(
                    campo="E111.cod_aj_apur",
                    valor_computado=cod_inv,
                    valor_declarado="código com 3º char '1' ou '2'",
                    diferenca="código de ajuste desconhecido",
                    severidade=Severidade.AVISO,
                )
            )

        if e110 is not None:
            decl_debitos = _to_dec(e110.get("vl_tot_debitos"))
            decl_creditos = _to_dec(e110.get("vl_tot_creditos"))
            decl_saldo_ant = _to_dec(e110.get("vl_sld_credor_ant"))
            decl_saldo = _to_dec(e110.get("vl_sld_apurado"))

            diff_d = abs(debitos - decl_debitos)
            if diff_d > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="vl_tot_debitos",
                        valor_computado=str(debitos),
                        valor_declarado=str(decl_debitos),
                        diferenca=str(diff_d),
                        severidade=Severidade.ERRO,
                    )
                )

            diff_c = abs(creditos - decl_creditos)
            if diff_c > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="vl_tot_creditos",
                        valor_computado=str(creditos),
                        valor_declarado=str(decl_creditos),
                        diferenca=str(diff_c),
                        severidade=Severidade.ERRO,
                    )
                )

            computed_saldo_e110 = (
                debitos - creditos + ajustes_debito - ajustes_credito - decl_saldo_ant
            )
            diff_s = abs(computed_saldo_e110 - decl_saldo)
            if diff_s > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="vl_sld_apurado",
                        valor_computado=str(computed_saldo_e110),
                        valor_declarado=str(decl_saldo),
                        diferenca=str(diff_s),
                        severidade=Severidade.AVISO,
                    )
                )

        return ItemApuracao(
            tributo="ICMS",
            periodo=self._periodo_from_records(records),
            total_debitos=debitos,
            total_creditos=creditos,
            saldo_credor_anterior=saldo_credor_anterior,
            saldo_apurado=saldo_apurado,
            situacao=situacao,
            divergencias=divergencias,
            ajustes_debito=ajustes_debito,
            ajustes_credito=ajustes_credito,
            detalhes={
                "total_registros_c100_d100": n_c100,
                "e110_declarado": e110 is not None,
                "ajustes_debito": str(ajustes_debito),
                "ajustes_credito": str(ajustes_credito),
                "e111_count": e111_count,
                "e112_count": e112_count,
                "e113_count": e113_count,
            },
        )

    def calcular_pis(self, records: List[SpedRecord]) -> ItemApuracao:
        """Apura PIS a partir de M100 (cumulativo) ou M210 (não-cumulativo)."""
        m100_records = [r for r in records if r.tipo_registro == "M100"]
        if m100_records:
            return self._calcular_pis_cumulativo(records, m100_records)
        return self._calcular_pis_nao_cumulativo(records)

    def _calcular_pis_cumulativo(
        self, records: List[SpedRecord], m100_records: List[SpedRecord]
    ) -> ItemApuracao:
        """Apura PIS no regime cumulativo via M100."""
        aliq_default = _get_aliq("pis_cumulativo_aliq", "0.0065")
        total_pis = Decimal("0")
        creditos = Decimal("0")

        for r in m100_records:
            vl_cont = _to_dec(r.campos.get("vl_cont"))
            if vl_cont:
                total_pis += vl_cont
            else:
                vl_bc = _to_dec(r.campos.get("vl_bc"))
                aliq_str = r.campos.get("aliq_pis_ou_pasep")
                aliq = _to_dec(aliq_str) / 100 if aliq_str else aliq_default
                total_pis += vl_bc * aliq

        for r in records:
            if r.tipo_registro in ("M400", "M405"):
                creditos += _to_dec(r.campos.get("vl_cred"))

        saldo = total_pis - creditos
        situacao = "devedor" if saldo > 0 else "credor" if saldo < 0 else "equilibrado"

        return ItemApuracao(
            tributo="PIS",
            periodo=self._periodo_from_records(records),
            total_debitos=total_pis,
            total_creditos=creditos,
            saldo_credor_anterior=Decimal("0"),
            saldo_apurado=saldo,
            situacao=situacao,
            detalhes={"regime": "cumulativo", "total_m100_linhas": len(m100_records)},
        )

    def _calcular_pis_nao_cumulativo(self, records: List[SpedRecord]) -> ItemApuracao:
        """Apura PIS (não-cumulativo) a partir de M210 e confronta com M200.

        Soma vl_cont_apr de todos os M210; confronta com M200 vl_tot_cont_nc_per.
        """
        total_m210 = Decimal("0")
        m200: Optional[Dict[str, Any]] = None
        n_m210 = 0
        creditos = Decimal("0")

        for record in records:
            if record.tipo_registro == "M210":
                n_m210 += 1
                total_m210 += _to_dec(record.campos.get("vl_cont_apr"))
            elif record.tipo_registro == "M200":
                m200 = record.campos
            elif record.tipo_registro in ("M400", "M405"):
                creditos += _to_dec(record.campos.get("vl_cred"))

        divergencias: List[DivergenciaApuracao] = []

        if m200 is not None:
            decl_total = _to_dec(m200.get("vl_tot_cont_nc_per"))
            diff = abs(total_m210 - decl_total)
            if diff > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="vl_tot_cont_nc_per",
                        valor_computado=str(total_m210),
                        valor_declarado=str(decl_total),
                        diferenca=str(diff),
                        severidade=Severidade.ERRO,
                    )
                )

        saldo = total_m210 - creditos
        situacao = "devedor" if saldo > 0 else "credor" if saldo < 0 else "equilibrado"

        return ItemApuracao(
            tributo="PIS",
            periodo=self._periodo_from_records(records),
            total_debitos=total_m210,
            total_creditos=creditos,
            saldo_credor_anterior=Decimal("0"),
            saldo_apurado=saldo,
            situacao=situacao,
            divergencias=divergencias,
            detalhes={
                "m200_declarado": m200 is not None,
                "total_m210_linhas": n_m210,
            },
        )

    def calcular_cofins(self, records: List[SpedRecord]) -> ItemApuracao:
        """Apura COFINS a partir de M500 (cumulativo) ou M610 (não-cumulativo)."""
        m500_records = [r for r in records if r.tipo_registro == "M500"]
        if m500_records:
            return self._calcular_cofins_cumulativo(records, m500_records)
        return self._calcular_cofins_nao_cumulativo(records)

    def _calcular_cofins_cumulativo(
        self, records: List[SpedRecord], m500_records: List[SpedRecord]
    ) -> ItemApuracao:
        """Apura COFINS no regime cumulativo via M500."""
        aliq_default = _get_aliq("cofins_cumulativo_aliq", "0.03")
        total_cofins = Decimal("0")
        creditos = Decimal("0")

        for r in m500_records:
            vl_cont = _to_dec(r.campos.get("vl_cont"))
            if vl_cont:
                total_cofins += vl_cont
            else:
                vl_bc = _to_dec(r.campos.get("vl_bc"))
                aliq_str = r.campos.get("aliq_cofins")
                aliq = _to_dec(aliq_str) / 100 if aliq_str else aliq_default
                total_cofins += vl_bc * aliq

        for r in records:
            if r.tipo_registro == "M800":
                creditos += _to_dec(r.campos.get("vl_cred"))

        saldo = total_cofins - creditos
        situacao = "devedor" if saldo > 0 else "credor" if saldo < 0 else "equilibrado"

        return ItemApuracao(
            tributo="COFINS",
            periodo=self._periodo_from_records(records),
            total_debitos=total_cofins,
            total_creditos=creditos,
            saldo_credor_anterior=Decimal("0"),
            saldo_apurado=saldo,
            situacao=situacao,
            detalhes={"regime": "cumulativo", "total_m500_linhas": len(m500_records)},
        )

    def _calcular_cofins_nao_cumulativo(
        self, records: List[SpedRecord]
    ) -> ItemApuracao:
        """Apura COFINS (não-cumulativo) a partir de M610 e confronta com M600.

        Soma vl_cont_apr de todos os M610; confronta com M600 vl_tot_cont_nc_per.
        """
        total_m610 = Decimal("0")
        m600: Optional[Dict[str, Any]] = None
        n_m610 = 0
        creditos = Decimal("0")

        for record in records:
            if record.tipo_registro == "M610":
                n_m610 += 1
                total_m610 += _to_dec(record.campos.get("vl_cont_apr"))
            elif record.tipo_registro == "M600":
                m600 = record.campos
            elif record.tipo_registro == "M800":
                creditos += _to_dec(record.campos.get("vl_cred"))

        divergencias: List[DivergenciaApuracao] = []

        if m600 is not None:
            decl_total = _to_dec(m600.get("vl_tot_cont_nc_per"))
            diff = abs(total_m610 - decl_total)
            if diff > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="vl_tot_cont_nc_per",
                        valor_computado=str(total_m610),
                        valor_declarado=str(decl_total),
                        diferenca=str(diff),
                        severidade=Severidade.ERRO,
                    )
                )

        saldo = total_m610 - creditos
        situacao = "devedor" if saldo > 0 else "credor" if saldo < 0 else "equilibrado"

        return ItemApuracao(
            tributo="COFINS",
            periodo=self._periodo_from_records(records),
            total_debitos=total_m610,
            total_creditos=creditos,
            saldo_credor_anterior=Decimal("0"),
            saldo_apurado=saldo,
            situacao=situacao,
            divergencias=divergencias,
            detalhes={
                "m600_declarado": m600 is not None,
                "total_m610_linhas": n_m610,
            },
        )

    def calcular(
        self,
        records: List[SpedRecord],
        tipo: str = "efd_icms",
        saldo_credor_anterior_icms: Decimal = Decimal("0"),
    ) -> ResultadoApuracao:
        """Calcula apuração completa para uma lista de SpedRecords.

        Args:
            records: Saída de ``SpedParser.parse().records``.
            tipo: ``"efd_icms"`` ou ``"efd_contrib"``.
            saldo_credor_anterior_icms: Saldo credor ICMS do período anterior.
        """
        items: List[ItemApuracao] = []

        if tipo in ("efd_icms", "efd_icms_ipi"):
            items.append(self.calcular_icms(records, saldo_credor_anterior_icms))
        elif tipo in ("efd_contrib", "efd_contribuicoes"):
            items.append(self.calcular_pis(records))
            items.append(self.calcular_cofins(records))
        else:
            items.append(self.calcular_icms(records, saldo_credor_anterior_icms))
            items.append(self.calcular_pis(records))
            items.append(self.calcular_cofins(records))

        total_divs = sum(len(i.divergencias) for i in items)
        aprovado = not any(
            d.severidade == Severidade.ERRO for i in items for d in i.divergencias
        )
        resumo = (
            "Apuração concluída sem divergências"
            if total_divs == 0
            else f"Apuração: {total_divs} divergência(s) encontrada(s)"
        )

        return ResultadoApuracao(aprovado=aprovado, items=items, resumo=resumo)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


def get_apuracao_engine() -> ApuracaoEngine:
    """Retorna instância do motor de apuração fiscal."""
    return ApuracaoEngine()
