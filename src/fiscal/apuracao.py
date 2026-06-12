"""Motor de apuração ICMS/PIS/COFINS/ICMS-ST/IPI (Bloco C — S-C.2 Parte B).

Stateless: recebe SpedRecords parseados e retorna ItemApuracao por tributo.
Confronto computado × declarado via E110 (ICMS), E210 (ICMS-ST), E520 (IPI)
e M200/M600 (PIS/COFINS).

Uso:
    engine = get_apuracao_engine()
    resultado = engine.calcular(parse_result.records, tipo="efd_icms")
    for item in resultado.items:
        print(item.tributo, item.situacao, item.saldo_apurado)

COD_AJ_APUR — tabela 5.1.1 do Guia Prático EFD ICMS/IPI (4º caractere, índice 3):
    0 = outros débitos        → ajustes_debito
    1 = estorno de créditos   → ajustes_debito
    2 = outros créditos       → ajustes_credito
    3 = estorno de débitos    → ajustes_credito
    4 = deduções              → abate pós-saldo (detalhes["deducoes"])
    5 = débitos especiais     → fora do saldo   (detalhes["debitos_especiais"])
    outro / código curto      → AVISO
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


def _decode_aj_apur(cod: str):
    """Decodifica a natureza do ajuste pelo 4º caractere (índice 3) — tab. 5.1.1.

    Retorna (natureza, aviso_str):
      natureza in {'0','1','2','3','4','5'} → reconhecido
      natureza == '' → código curto/inválido; aviso_str descreve o problema.
    """
    if len(cod) >= 4:
        nat = cod[3]
        if nat in ("0", "1", "2", "3", "4", "5"):
            return nat, ""
        return "", cod
    return "", cod or "(vazio)"


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
        deducoes = Decimal("0")
        debitos_especiais = Decimal("0")
        avisos_ajuste: List[str] = []
        e111_count = 0
        e112_count = 0
        e113_count = 0

        for record in records:
            if record.tipo_registro == "E111":
                e111_count += 1
                cod = str(record.campos.get("cod_aj_apur") or "")
                vl = _to_dec(record.campos.get("vl_aj_apur"))
                nat, aviso = _decode_aj_apur(cod)
                if nat in ("0", "1"):
                    ajustes_debito += vl
                elif nat in ("2", "3"):
                    ajustes_credito += vl
                elif nat == "4":
                    deducoes += vl
                elif nat == "5":
                    debitos_especiais += vl
                else:
                    avisos_ajuste.append(aviso)
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

        # Deduções abatem só saldo devedor; excedente não converte em credor.
        deducao_excedente = Decimal("0")
        if deducoes > 0:
            if saldo_apurado > 0:
                if deducoes >= saldo_apurado:
                    deducao_excedente = deducoes - saldo_apurado
                    saldo_apurado = Decimal("0")
                else:
                    saldo_apurado -= deducoes
            else:
                deducao_excedente = deducoes

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
                    valor_declarado="código real ≥4 chars, 4º char in '0'-'5' (tab.5.1.1)",
                    diferenca="código de ajuste não reconhecido",
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

        det: Dict[str, Any] = {
            "total_registros_c100_d100": n_c100,
            "e110_declarado": e110 is not None,
            "ajustes_debito": str(ajustes_debito),
            "ajustes_credito": str(ajustes_credito),
            "e111_count": e111_count,
            "e112_count": e112_count,
            "e113_count": e113_count,
        }
        if deducoes:
            det["deducoes"] = str(deducoes)
        if debitos_especiais:
            det["debitos_especiais"] = str(debitos_especiais)
        if deducao_excedente:
            det["deducao_excedente"] = str(deducao_excedente)
            divergencias.append(
                DivergenciaApuracao(
                    campo="E111.deducoes",
                    valor_computado=str(deducao_excedente),
                    valor_declarado="0",
                    diferenca=str(deducao_excedente),
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
            detalhes=det,
        )

    def calcular_icms_st(
        self,
        records: List[SpedRecord],
        saldo_credor_anterior: Decimal = Decimal("0"),
    ) -> ItemApuracao:
        """Apura ICMS-ST a partir de C100/D100 (vl_icmsst) e confronta com E200/E210.

        E210 débitos declarados = vl_retencao_st + vl_out_deb_st + vl_aj_debitos_st.
        E210 créditos declarados = vl_devol_st + vl_ressarc_st + vl_out_cred_st + vl_aj_creditos_st.
        E210 sem E200 → ERRO estrutural. Sem dados ST → situacao='ausente'.
        Detalhes incluem breakdown por UF (campo 'uf' do E200 pai).
        """
        debitos_st = Decimal("0")
        creditos_st = Decimal("0")
        n_c100 = 0

        # Coleta pares (e200_campos, e210_campos) em ordem sequencial de arquivo.
        e200_e210_pairs: List[tuple] = []
        current_e200: Optional[Dict[str, Any]] = None
        e210_sem_e200 = False

        for record in records:
            if record.tipo_registro in ("C100", "D100"):
                n_c100 += 1
                campos = record.campos
                cod_sit = str(campos.get("cod_sit") or "").strip()
                if cod_sit in _SITUS_CANCELADOS:
                    continue
                ind_oper = str(campos.get("ind_oper") or "").strip()
                vl_st = _to_dec(campos.get("vl_icmsst"))
                if ind_oper == "1":
                    debitos_st += vl_st
                elif ind_oper == "0":
                    creditos_st += vl_st
            elif record.tipo_registro == "E200":
                current_e200 = record.campos
            elif record.tipo_registro == "E210":
                if current_e200 is None:
                    e210_sem_e200 = True
                else:
                    e200_e210_pairs.append((current_e200, record.campos))

        sem_dados = (
            debitos_st == Decimal("0")
            and creditos_st == Decimal("0")
            and not e200_e210_pairs
            and not e210_sem_e200
        )
        if sem_dados:
            return ItemApuracao(
                tributo="ICMS-ST",
                periodo=self._periodo_from_records(records),
                total_debitos=Decimal("0"),
                total_creditos=Decimal("0"),
                saldo_credor_anterior=Decimal("0"),
                saldo_apurado=Decimal("0"),
                situacao="ausente",
                detalhes={"e200_count": 0, "e210_declarado": False},
            )

        divergencias: List[DivergenciaApuracao] = []

        if e210_sem_e200:
            divergencias.append(
                DivergenciaApuracao(
                    campo="E210",
                    valor_computado="E210 sem E200 correspondente",
                    valor_declarado="E200 obrigatório",
                    diferenca="estrutura",
                    severidade=Severidade.ERRO,
                )
            )

        saldo_apurado = debitos_st - creditos_st - saldo_credor_anterior
        situacao = (
            "devedor"
            if saldo_apurado > 0
            else "credor" if saldo_apurado < 0 else "equilibrado"
        )

        ufs: Dict[str, Any] = {}
        for e200_campos, e210_campos in e200_e210_pairs:
            uf = str(e200_campos.get("uf") or "").strip()

            # Débitos declarados = retenção + outros débitos + ajuste débitos
            decl_debitos = (
                _to_dec(e210_campos.get("vl_retencao_st"))
                + _to_dec(e210_campos.get("vl_out_deb_st"))
                + _to_dec(e210_campos.get("vl_aj_debitos_st"))
            )
            # Créditos declarados = devoluções + ressarcimento + outros créditos + ajuste créditos
            decl_creditos = (
                _to_dec(e210_campos.get("vl_devol_st"))
                + _to_dec(e210_campos.get("vl_ressarc_st"))
                + _to_dec(e210_campos.get("vl_out_cred_st"))
                + _to_dec(e210_campos.get("vl_aj_creditos_st"))
            )
            decl_saldo_ant = _to_dec(e210_campos.get("vl_sld_cred_ant_st"))
            decl_recol = _to_dec(e210_campos.get("vl_icms_recol_st"))

            diff_d = abs(debitos_st - decl_debitos)
            if diff_d > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo=f"E210.debitos_st[{uf}]",
                        valor_computado=str(debitos_st),
                        valor_declarado=str(decl_debitos),
                        diferenca=str(diff_d),
                        severidade=Severidade.ERRO,
                    )
                )

            diff_c = abs(creditos_st - decl_creditos)
            if diff_c > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo=f"E210.creditos_st[{uf}]",
                        valor_computado=str(creditos_st),
                        valor_declarado=str(decl_creditos),
                        diferenca=str(diff_c),
                        severidade=Severidade.ERRO,
                    )
                )

            computed_saldo = debitos_st - creditos_st - decl_saldo_ant
            diff_s = abs(computed_saldo - decl_recol)
            if diff_s > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo=f"E210.vl_icms_recol_st[{uf}]",
                        valor_computado=str(computed_saldo),
                        valor_declarado=str(decl_recol),
                        diferenca=str(diff_s),
                        severidade=Severidade.AVISO,
                    )
                )

            if uf:
                ufs[uf] = {
                    "vl_icms_recol_st": str(decl_recol),
                    "vl_sld_cred_st_transportar": str(
                        _to_dec(e210_campos.get("vl_sld_cred_st_transportar"))
                    ),
                }

        return ItemApuracao(
            tributo="ICMS-ST",
            periodo=self._periodo_from_records(records),
            total_debitos=debitos_st,
            total_creditos=creditos_st,
            saldo_credor_anterior=saldo_credor_anterior,
            saldo_apurado=saldo_apurado,
            situacao=situacao,
            divergencias=divergencias,
            detalhes={
                "e200_count": len(e200_e210_pairs),
                "e210_declarado": bool(e200_e210_pairs) or e210_sem_e200,
                "ufs": ufs,
            },
        )

    def calcular_ipi(self, records: List[SpedRecord]) -> ItemApuracao:
        """Apura IPI a partir de C100/D100 (vl_ipi) e confronta com E520.

        E520 usa leiaute real: vl_deb_ipi, vl_cred_ipi, vl_od_ipi, vl_oc_ipi, vl_sd_ipi.
        E530 usa ind_aj diretamente: '0'=débito, '1'=crédito (não usa _decode_aj_apur).
        Sem dados IPI → situacao='ausente'.
        """
        debitos = Decimal("0")
        creditos = Decimal("0")
        e520: Optional[Dict[str, Any]] = None
        ajustes_debito = Decimal("0")
        ajustes_credito = Decimal("0")
        e530_details: List[Dict[str, Any]] = []
        n_c100 = 0

        for record in records:
            if record.tipo_registro in ("C100", "D100"):
                n_c100 += 1
                campos = record.campos
                cod_sit = str(campos.get("cod_sit") or "").strip()
                if cod_sit in _SITUS_CANCELADOS:
                    continue
                ind_oper = str(campos.get("ind_oper") or "").strip()
                vl_ipi = _to_dec(campos.get("vl_ipi"))
                if ind_oper == "1":
                    debitos += vl_ipi
                elif ind_oper == "0":
                    creditos += vl_ipi
            elif record.tipo_registro == "E520":
                e520 = record.campos
            elif record.tipo_registro == "E530":
                ind_aj = str(record.campos.get("ind_aj") or "").strip()
                vl = _to_dec(record.campos.get("vl_aj_ipi"))
                cod = str(record.campos.get("cod_aj") or "")
                if ind_aj == "0":
                    ajustes_debito += vl
                elif ind_aj == "1":
                    ajustes_credito += vl
                e530_details.append({"cod_aj": cod, "ind_aj": ind_aj, "vl": str(vl)})

        sem_dados = (
            debitos == Decimal("0") and creditos == Decimal("0") and e520 is None
        )
        if sem_dados:
            return ItemApuracao(
                tributo="IPI",
                periodo=self._periodo_from_records(records),
                total_debitos=Decimal("0"),
                total_creditos=Decimal("0"),
                saldo_credor_anterior=Decimal("0"),
                saldo_apurado=Decimal("0"),
                situacao="ausente",
                detalhes={"e520_declarado": False},
            )

        saldo_apurado = debitos - creditos + ajustes_debito - ajustes_credito
        situacao = (
            "devedor"
            if saldo_apurado > 0
            else "credor" if saldo_apurado < 0 else "equilibrado"
        )

        divergencias: List[DivergenciaApuracao] = []

        if e520 is not None:
            # E520 real: vl_deb_ipi, vl_cred_ipi, vl_od_ipi (outros deb), vl_oc_ipi (outros cred)
            decl_debitos = _to_dec(e520.get("vl_deb_ipi"))
            decl_creditos = _to_dec(e520.get("vl_cred_ipi"))
            decl_od = _to_dec(e520.get("vl_od_ipi"))
            decl_oc = _to_dec(e520.get("vl_oc_ipi"))
            decl_sd_ipi = _to_dec(e520.get("vl_sd_ipi"))

            diff_d = abs(debitos - decl_debitos)
            if diff_d > _TOLERANCIA:
                divergencias.append(
                    DivergenciaApuracao(
                        campo="E520.vl_deb_ipi",
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
                        campo="E520.vl_cred_ipi",
                        valor_computado=str(creditos),
                        valor_declarado=str(decl_creditos),
                        diferenca=str(diff_c),
                        severidade=Severidade.ERRO,
                    )
                )

            if saldo_apurado > 0:
                diff_s = abs(saldo_apurado - decl_sd_ipi)
                if diff_s > _TOLERANCIA:
                    divergencias.append(
                        DivergenciaApuracao(
                            campo="E520.vl_sd_ipi",
                            valor_computado=str(saldo_apurado),
                            valor_declarado=str(decl_sd_ipi),
                            diferenca=str(diff_s),
                            severidade=Severidade.AVISO,
                        )
                    )

        return ItemApuracao(
            tributo="IPI",
            periodo=self._periodo_from_records(records),
            total_debitos=debitos,
            total_creditos=creditos,
            saldo_credor_anterior=Decimal("0"),
            saldo_apurado=saldo_apurado,
            situacao=situacao,
            divergencias=divergencias,
            ajustes_debito=ajustes_debito,
            ajustes_credito=ajustes_credito,
            detalhes={
                "e520_declarado": e520 is not None,
                "ajustes_debito": str(ajustes_debito),
                "ajustes_credito": str(ajustes_credito),
                "e530_ajustes": e530_details,
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
            for sub in (self.calcular_icms_st(records), self.calcular_ipi(records)):
                if sub.situacao != "ausente":
                    items.append(sub)
        elif tipo in ("efd_contrib", "efd_contribuicoes"):
            items.append(self.calcular_pis(records))
            items.append(self.calcular_cofins(records))
        else:
            items.append(self.calcular_icms(records, saldo_credor_anterior_icms))
            for sub in (self.calcular_icms_st(records), self.calcular_ipi(records)):
                if sub.situacao != "ausente":
                    items.append(sub)
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
