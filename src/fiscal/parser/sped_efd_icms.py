"""Parser SPED EFD-ICMS/IPI (Escrita Fiscal Digital de ICMS e IPI).

Implementa o padrão Strategy: cada tipo de registro é tratado por um
handler específico registrado em SpedEfdIcmsParser._register_handlers().
Registros desconhecidos são preservados com a lista de campos raw.

Formato de linha SPED:
    |TIPO_REGISTRO|campo1|campo2|...|campoN|

Datas SPED: DDMMAAAA  →  convertidas para ISO YYYY-MM-DD
Decimais SPED: vírgula como separador decimal ("1234,56") — mantidos
               como string para preservar precisão.

Leiaute conferido contra: Guia Prático EFD ICMS/IPI v3.1.5 (jan/2025).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import RecordHandler, SpedParser

# ─────────────────────────────────────────────────────────────────────────────
# Helpers compartilhados entre handlers
# ─────────────────────────────────────────────────────────────────────────────


def _zip_campos(names: List[str], values: List[str]) -> Dict[str, Any]:
    """Map campo names to raw values, padding missing values with empty str."""
    result: Dict[str, Any] = {}
    for i, name in enumerate(names):
        result[name] = values[i].strip() if i < len(values) else ""
    return result


def _parse_date(s: str) -> Optional[str]:
    """Convert SPED date DDMMAAAA to ISO YYYY-MM-DD; None if empty/invalid."""
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[4:8]}-{s[2:4]}-{s[0:2]}"
    return s or None


def _dec(s: str) -> str:
    """Return decimal string as-is (SPED uses comma; avoid float precision loss)."""
    return s.strip()


def _apply_dates(d: Dict[str, Any], *keys: str) -> None:
    for k in keys:
        if k in d:
            d[k] = _parse_date(str(d[k]))


def _apply_dec(d: Dict[str, Any], *keys: str) -> None:
    for k in keys:
        if k in d:
            d[k] = _dec(str(d[k]))


# ─────────────────────────────────────────────────────────────────────────────
# Handlers genéricos
# ─────────────────────────────────────────────────────────────────────────────


def _handle_ind_mov(campos: List[str]) -> Dict[str, Any]:
    return {"ind_mov": campos[0].strip() if campos else ""}


def _handle_qt_lin(campos: List[str]) -> Dict[str, Any]:
    return {"qt_lin": campos[0].strip() if campos else ""}


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 0 — Abertura e Identificação
# ─────────────────────────────────────────────────────────────────────────────

_0000_CAMPOS = [
    "cod_ver",
    "cod_fin",
    "dt_ini",
    "dt_fin",
    "nome",
    "cnpj",
    "cpf",
    "uf",
    "ie",
    "cod_mun",
    "im",
    "suframa",
    "ind_perfil",
    "ind_ativ",
]


def _handle_0000(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_0000_CAMPOS, campos)
    _apply_dates(d, "dt_ini", "dt_fin")
    return d


_0150_CAMPOS = [
    "cod_part",
    "nome",
    "cod_pais",
    "cnpj",
    "cpf",
    "ie",
    "cod_mun",
    "suframa",
    "end",
    "num",
    "compl",
    "bairro",
]


def _handle_0150(campos: List[str]) -> Dict[str, Any]:
    return _zip_campos(_0150_CAMPOS, campos)


_0200_CAMPOS = [
    "cod_item",
    "descr_item",
    "cod_barra",
    "cod_ant_item",
    "unid_inv",
    "tipo_item",
    "cod_ncm",
    "ex_ipi",
    "cod_gen",
    "cod_lst",
    "aliq_icms",
    "cest",
]


def _handle_0200(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_0200_CAMPOS, campos)
    _apply_dec(d, "aliq_icms")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco C — Documentos Fiscais (Mercadorias — ICMS/IPI)
# ─────────────────────────────────────────────────────────────────────────────

_C100_CAMPOS = [
    "ind_oper",
    "ind_emit",
    "cod_part",
    "cod_mod",
    "cod_sit",
    "ser",
    "num_doc",
    "chv_nfe",
    "dt_doc",
    "dt_e_s",
    "vl_doc",
    "ind_pgto",
    "vl_desc",
    "vl_abat_nt",
    "vl_merc",
    "ind_frt",
    "vl_frt",
    "vl_seg",
    "vl_out_da",
    "vl_bc_icms",
    "vl_icms",
    "vl_bc_icms_st",
    "vl_icmsst",
    "vl_ipi",
    "vl_pis",
    "vl_cofins",
    "vl_pis_st",
    "vl_cofins_st",
]

_C100_DECIMAL_CAMPOS = [
    "vl_doc",
    "vl_desc",
    "vl_abat_nt",
    "vl_merc",
    "vl_frt",
    "vl_seg",
    "vl_out_da",
    "vl_bc_icms",
    "vl_icms",
    "vl_bc_icms_st",
    "vl_icmsst",
    "vl_ipi",
    "vl_pis",
    "vl_cofins",
    "vl_pis_st",
    "vl_cofins_st",
]


def _handle_c100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_C100_CAMPOS, campos)
    _apply_dates(d, "dt_doc", "dt_e_s")
    _apply_dec(d, *_C100_DECIMAL_CAMPOS)
    return d


_C170_CAMPOS = [
    "num_item",
    "cod_item",
    "descr_compl",
    "qtd",
    "unid",
    "vl_item",
    "vl_desc",
    "ind_mov",
    "cst_icms",
    "cfop",
    "cod_nat",
    "vl_bc_icms",
    "aliq_icms",
    "vl_icms",
    "vl_bc_icms_st",
    "aliq_st",
    "vl_icmsst",
    "ind_apur",
    "cst_ipi",
    "cod_enq",
    "vl_bc_ipi",
    "aliq_ipi",
    "vl_ipi",
    "cst_pis",
    "vl_bc_pis",
    "aliq_pis",
    "quant_bc_pis",
    "vl_pis",
    "cst_cofins",
    "vl_bc_cofins",
    "aliq_cofins",
    "quant_bc_cofins",
    "vl_cofins",
    "cod_cta",
    "vl_abat_nt",
]

_C170_DECIMAL_CAMPOS = [
    "qtd",
    "vl_item",
    "vl_desc",
    "vl_bc_icms",
    "aliq_icms",
    "vl_icms",
    "vl_bc_icms_st",
    "aliq_st",
    "vl_icmsst",
    "vl_bc_ipi",
    "aliq_ipi",
    "vl_ipi",
    "vl_bc_pis",
    "aliq_pis",
    "quant_bc_pis",
    "vl_pis",
    "vl_bc_cofins",
    "aliq_cofins",
    "quant_bc_cofins",
    "vl_cofins",
    "vl_abat_nt",
]


def _handle_c170(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_C170_CAMPOS, campos)
    _apply_dec(d, *_C170_DECIMAL_CAMPOS)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco D — Documentos Fiscais (Serviços — ICMS)
# ─────────────────────────────────────────────────────────────────────────────

_D100_CAMPOS = [
    "ind_oper",
    "ind_emit",
    "cod_part",
    "cod_mod",
    "cod_sit",
    "ser",
    "sub",
    "num_doc",
    "chv_cte",
    "dt_doc",
    "dt_a_p",
    "tp_ct_e",
    "chv_cte_ref",
    "vl_doc",
    "vl_desc",
    "ind_frt",
    "vl_serv",
    "vl_bc_icms",
    "vl_icms",
    "vl_nt",
    "cod_inf",
    "cod_cta",
    "ind_glb",
]


def _handle_d100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_D100_CAMPOS, campos)
    _apply_dates(d, "dt_doc", "dt_a_p")
    _apply_dec(d, "vl_doc", "vl_desc", "vl_serv", "vl_bc_icms", "vl_icms", "vl_nt")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco E — Apuração do ICMS e do IPI
# ─────────────────────────────────────────────────────────────────────────────

# E110 — Apuração ICMS (Guia Prático EFD ICMS/IPI v3.1.5)
_E110_CAMPOS = [
    "vl_tot_debitos",
    "vl_aj_debitos",
    "vl_tot_aj_debitos",
    "vl_estornos_cred",
    "vl_tot_creditos",
    "vl_aj_creditos",
    "vl_tot_aj_creditos",
    "vl_estornos_deb",
    "vl_sld_credor_ant",
    "vl_sld_apurado",
    "vl_tot_ded",
    "vl_icms_recolher",
    "vl_sld_credor_transp",
    "deb_esp",
]


def _handle_e110(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E110_CAMPOS, campos)
    _apply_dec(d, *_E110_CAMPOS)
    return d


# E200 — Período de apuração ICMS-ST por UF (Guia Prático EFD ICMS/IPI v3.1.5)
_E200_CAMPOS = ["uf", "dt_ini", "dt_fin"]


def _handle_e200(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E200_CAMPOS, campos)
    _apply_dates(d, "dt_ini", "dt_fin")
    return d


# E210 — Apuração ICMS-ST (Guia Prático EFD ICMS/IPI v3.1.5)
_E210_CAMPOS = [
    "ind_mov_st",
    "vl_sld_cred_ant_st",
    "vl_devol_st",
    "vl_ressarc_st",
    "vl_out_cred_st",
    "vl_aj_creditos_st",
    "vl_retencao_st",
    "vl_out_deb_st",
    "vl_aj_debitos_st",
    "vl_sld_dev_ant_st",
    "vl_deducoes_st",
    "vl_icms_recol_st",
    "vl_sld_cred_st_transportar",
    "deb_esp_st",
]

_E210_DECIMAL_CAMPOS = [
    "vl_sld_cred_ant_st",
    "vl_devol_st",
    "vl_ressarc_st",
    "vl_out_cred_st",
    "vl_aj_creditos_st",
    "vl_retencao_st",
    "vl_out_deb_st",
    "vl_aj_debitos_st",
    "vl_sld_dev_ant_st",
    "vl_deducoes_st",
    "vl_icms_recol_st",
    "vl_sld_cred_st_transportar",
    "deb_esp_st",
]


def _handle_e210(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E210_CAMPOS, campos)
    _apply_dec(d, *_E210_DECIMAL_CAMPOS)
    return d


# E520 — Apuração IPI (Guia Prático EFD ICMS/IPI v3.1.5)
_E520_CAMPOS = [
    "vl_sd_ant_ipi",
    "vl_deb_ipi",
    "vl_cred_ipi",
    "vl_od_ipi",
    "vl_oc_ipi",
    "vl_sc_ipi",
    "vl_sd_ipi",
]


def _handle_e520(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E520_CAMPOS, campos)
    _apply_dec(d, *_E520_CAMPOS)
    return d


# E530 — Ajustes IPI (Guia Prático EFD ICMS/IPI v3.1.5)
# IND_AJ: 0=débito, 1=crédito (natureza direta — não usar _decode_aj_apur)
_E530_CAMPOS = [
    "cod_aj",
    "ind_aj",
    "vl_aj_ipi",
    "cod_item",
    "num_da",
    "num_proc",
    "ind_proc",
    "descr_compl_aj",
    "cod_cta",
]


def _handle_e530(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E530_CAMPOS, campos)
    _apply_dec(d, "vl_aj_ipi")
    return d


_E111_CAMPOS = ["cod_aj_apur", "descr_compl_aj", "vl_aj_apur"]


def _handle_e111(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_E111_CAMPOS, campos)
    _apply_dec(d, "vl_aj_apur")
    return d


_E112_CAMPOS = ["cod_aj_apur", "num_da", "num_acj", "descr_compl", "valor"]


def _handle_e112(campos: List[str]) -> Dict[str, Any]:
    return _zip_campos(_E112_CAMPOS, campos)


_E113_CAMPOS = [
    "cod_aj_apur",
    "ser",
    "sub",
    "num_doc",
    "dt_doc",
    "cod_item",
    "vl_aj_item",
    "vl_bc_icms",
    "aliq_icms",
    "vl_icms",
    "vl_outros",
]


def _handle_e113(campos: List[str]) -> Dict[str, Any]:
    return _zip_campos(_E113_CAMPOS, campos)


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 9 — Controle e Encerramento
# ─────────────────────────────────────────────────────────────────────────────


def _handle_9900(campos: List[str]) -> Dict[str, Any]:
    return {
        "reg": campos[0].strip() if campos else "",
        "qt_reg_blc": campos[1].strip() if len(campos) > 1 else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parser principal
# ─────────────────────────────────────────────────────────────────────────────


class SpedEfdIcmsParser(SpedParser):
    """Parser para SPED EFD-ICMS/IPI.

    Usa padrão Strategy: cada tipo de registro possui um handler dedicado.
    Tipos desconhecidos são preservados com campos raw.
    """

    def __init__(self) -> None:
        super().__init__()
        self._register_handlers()

    def _register_handlers(self) -> None:
        # Bloco 0
        self.register_handler("0000", _handle_0000)
        self.register_handler("0001", _handle_ind_mov)
        self.register_handler("0150", _handle_0150)
        self.register_handler("0200", _handle_0200)
        self.register_handler("0990", _handle_qt_lin)
        # Bloco C
        self.register_handler("C001", _handle_ind_mov)
        self.register_handler("C100", _handle_c100)
        self.register_handler("C170", _handle_c170)
        self.register_handler("C990", _handle_qt_lin)
        # Bloco D
        self.register_handler("D001", _handle_ind_mov)
        self.register_handler("D100", _handle_d100)
        self.register_handler("D990", _handle_qt_lin)
        # Bloco E
        self.register_handler("E001", _handle_ind_mov)
        self.register_handler("E110", _handle_e110)
        self.register_handler("E111", _handle_e111)
        self.register_handler("E112", _handle_e112)
        self.register_handler("E113", _handle_e113)
        self.register_handler("E200", _handle_e200)
        self.register_handler("E210", _handle_e210)
        self.register_handler("E520", _handle_e520)
        self.register_handler("E530", _handle_e530)
        self.register_handler("E990", _handle_qt_lin)
        # Bloco 9
        self.register_handler("9001", _handle_ind_mov)
        self.register_handler("9900", _handle_9900)
        self.register_handler("9990", _handle_qt_lin)
        self.register_handler("9999", _handle_qt_lin)
