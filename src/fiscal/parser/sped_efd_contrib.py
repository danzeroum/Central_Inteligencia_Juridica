"""Parser SPED EFD-Contribuições (PIS/COFINS).

Implementa o padrão Strategy: handlers por tipo_registro registrados em
SpedEfdContribParser._register_handlers(). Registros desconhecidos são
preservados com campos raw.

Diferenças do EFD-ICMS:
- Registro 0000 com ind_natur_pj (sem cpf/im/ind_perfil)
- Registro 0110: regime de apuração
- Bloco A: documentos de serviços ISS
- Bloco F: outras operações
- Bloco M: apuração PIS/COFINS (M100/M200/M210/M500/M600/M610)
- Bloco P: contribuição previdenciária sobre receita bruta
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import RecordHandler, SpedParser

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _zip_campos(names: List[str], values: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for i, name in enumerate(names):
        result[name] = values[i].strip() if i < len(values) else ""
    return result


def _parse_date(s: str) -> Optional[str]:
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[4:8]}-{s[2:4]}-{s[0:2]}"
    return s or None


def _apply_dates(d: Dict[str, Any], *keys: str) -> None:
    for k in keys:
        if k in d:
            d[k] = _parse_date(str(d[k]))


def _apply_dec(d: Dict[str, Any], *keys: str) -> None:
    for k in keys:
        if k in d:
            d[k] = d[k].strip() if isinstance(d[k], str) else d[k]


def _handle_ind_mov(campos: List[str]) -> Dict[str, Any]:
    return {"ind_mov": campos[0].strip() if campos else ""}


def _handle_qt_lin(campos: List[str]) -> Dict[str, Any]:
    return {"qt_lin": campos[0].strip() if campos else ""}


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 0
# ─────────────────────────────────────────────────────────────────────────────

_0000_CAMPOS = [
    "cod_ver",
    "cod_fin",
    "dt_ini",
    "dt_fin",
    "nome",
    "cnpj",
    "uf",
    "ie",
    "cod_mun",
    "suframa",
    "ind_natur_pj",
    "ind_ativ",
]


def _handle_0000(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_0000_CAMPOS, campos)
    _apply_dates(d, "dt_ini", "dt_fin")
    return d


_0110_CAMPOS = ["cod_inc_trib", "ind_apro_cred", "cod_tipo_cont", "ind_reg_cum"]


def _handle_0110(campos: List[str]) -> Dict[str, Any]:
    return _zip_campos(_0110_CAMPOS, campos)


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
]


def _handle_0200(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_0200_CAMPOS, campos)
    _apply_dec(d, "aliq_icms")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco A — Documentos Fiscais de Serviço (ISS)
# ─────────────────────────────────────────────────────────────────────────────

_A100_CAMPOS = [
    "ind_oper",
    "ind_emit",
    "cod_part",
    "cod_sit",
    "ser",
    "sub",
    "num_doc",
    "chv_nfse",
    "dt_doc",
    "dt_exc",
    "vl_doc",
    "vl_desc",
    "vl_bc_pis",
    "aliq_pis",
    "vl_pis",
    "vl_bc_cofins",
    "aliq_cofins",
    "vl_cofins",
    "vl_bc_pis_ret",
    "vl_pis_ret",
    "vl_bc_cofins_ret",
    "vl_cofins_ret",
]

_A100_DEC = [
    "vl_doc",
    "vl_desc",
    "vl_bc_pis",
    "aliq_pis",
    "vl_pis",
    "vl_bc_cofins",
    "aliq_cofins",
    "vl_cofins",
    "vl_bc_pis_ret",
    "vl_pis_ret",
    "vl_bc_cofins_ret",
    "vl_cofins_ret",
]


def _handle_a100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_A100_CAMPOS, campos)
    _apply_dates(d, "dt_doc", "dt_exc")
    _apply_dec(d, *_A100_DEC)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco C — Documentos Fiscais I (Mercadorias — NF-e/CF-e)
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

_C100_DEC = [
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
    _apply_dec(d, *_C100_DEC)
    return d


_C181_CAMPOS = [
    "cst_pis",
    "cfop",
    "vl_item",
    "vl_desc",
    "vl_bc_pis",
    "aliq_pis",
    "quant_bc_pis",
    "aliq_pis_qt",
    "vl_pis",
]


def _handle_c181(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_C181_CAMPOS, campos)
    _apply_dec(
        d,
        "vl_item",
        "vl_desc",
        "vl_bc_pis",
        "aliq_pis",
        "quant_bc_pis",
        "aliq_pis_qt",
        "vl_pis",
    )
    return d


_C185_CAMPOS = [
    "cst_cofins",
    "cfop",
    "vl_item",
    "vl_desc",
    "vl_bc_cofins",
    "aliq_cofins",
    "quant_bc_cofins",
    "aliq_cofins_qt",
    "vl_cofins",
]


def _handle_c185(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_C185_CAMPOS, campos)
    _apply_dec(
        d,
        "vl_item",
        "vl_desc",
        "vl_bc_cofins",
        "aliq_cofins",
        "quant_bc_cofins",
        "aliq_cofins_qt",
        "vl_cofins",
    )
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco D — Documentos Fiscais II (Serviços — CT-e)
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
]


def _handle_d100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_D100_CAMPOS, campos)
    _apply_dates(d, "dt_doc", "dt_a_p")
    _apply_dec(d, "vl_doc", "vl_desc", "vl_serv", "vl_bc_icms", "vl_icms", "vl_nt")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco F — Demais Documentos e Operações
# ─────────────────────────────────────────────────────────────────────────────

_F100_CAMPOS = [
    "ind_oper",
    "cod_part",
    "cod_item",
    "dt_oper",
    "vl_oper",
    "cst_pis",
    "vl_bc_pis",
    "aliq_pis",
    "vl_pis",
    "cst_cofins",
    "vl_bc_cofins",
    "aliq_cofins",
    "vl_cofins",
    "nat_bc_cred",
    "ind_orig_cred",
    "cod_cta",
    "cod_cent_cust",
    "desc_doc_oper",
]


def _handle_f100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_F100_CAMPOS, campos)
    _apply_dates(d, "dt_oper")
    _apply_dec(
        d,
        "vl_oper",
        "vl_bc_pis",
        "aliq_pis",
        "vl_pis",
        "vl_bc_cofins",
        "aliq_cofins",
        "vl_cofins",
    )
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco M — Apuração da Contribuição do PIS/PASEP e COFINS
# ─────────────────────────────────────────────────────────────────────────────

_M100_CAMPOS = [
    "cod_cred",
    "ind_cred_ori",
    "vl_bc_pis",
    "aliq_pis",
    "quant_bc_pis_t",
    "aliq_pis_t",
    "vl_cred",
    "vl_cred_aut_anu",
    "vl_cred_desc_pa_ant",
    "vl_cred_apr",
    "vl_cred_infor_pr_ant",
    "vl_tot_cred_rec",
    "vl_cred_desc_pa",
    "vl_cred_desc_pa_inf",
    "vl_cred_sub",
    "vl_cred_ced",
    "vl_cred_ori_f",
]

_M100_DEC = [c for c in _M100_CAMPOS if c.startswith(("vl_", "aliq_", "quant_"))]


def _handle_m100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M100_CAMPOS, campos)
    _apply_dec(d, *_M100_DEC)
    return d


_M200_CAMPOS = [
    "vl_tot_cont_nc_per",
    "vl_tot_cred_desc",
    "vl_tot_cred_desc_nao_apr",
    "vl_tot_cred_mantenr",
    "vl_tot_cred_a_desc",
    "vl_tot_cred_desc_ant",
    "vl_tot_cred_desc_per",
    "vl_cred_fin_aprop",
    "vl_ret_nc",
    "vl_out_ded_nc",
    "vl_cont_nc_rec",
    "vl_cred_ref",
    "vl_tot_cont_nc_dev",
    "vl_ret_nc_dev",
    "vl_out_ded_nc_dev",
    "vl_cont_nc_rec_dev",
    "vl_cred_ref_dev",
]


def _handle_m200(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M200_CAMPOS, campos)
    _apply_dec(d, *_M200_CAMPOS)
    return d


_M210_CAMPOS = [
    "cod_cont",
    "vl_rec_brt",
    "vl_bc_cont",
    "aliq_pis_cont",
    "quant_bc_pis_cont",
    "aliq_pis_cont_t",
    "vl_cont_apr",
    "vl_cred_exc_apur",
    "vl_cont_per_apur",
    "vl_exc",
]

_M210_DEC = [c for c in _M210_CAMPOS if c != "cod_cont"]


def _handle_m210(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M210_CAMPOS, campos)
    _apply_dec(d, *_M210_DEC)
    return d


_M500_CAMPOS = [
    "cod_cred",
    "ind_cred_ori",
    "vl_bc_cofins",
    "aliq_cofins",
    "quant_bc_cofins_t",
    "aliq_cofins_t",
    "vl_cred",
    "vl_cred_aut_anu",
    "vl_cred_desc_pa_ant",
    "vl_cred_apr",
    "vl_cred_infor_pr_ant",
    "vl_tot_cred_rec",
    "vl_cred_desc_pa",
    "vl_cred_desc_pa_inf",
    "vl_cred_sub",
    "vl_cred_ced",
    "vl_cred_ori_f",
]

_M500_DEC = [c for c in _M500_CAMPOS if c.startswith(("vl_", "aliq_", "quant_"))]


def _handle_m500(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M500_CAMPOS, campos)
    _apply_dec(d, *_M500_DEC)
    return d


_M600_CAMPOS = [
    "vl_tot_cont_nc_per",
    "vl_tot_cred_desc",
    "vl_tot_cred_desc_nao_apr",
    "vl_tot_cred_mantenr",
    "vl_tot_cred_a_desc",
    "vl_tot_cred_desc_ant",
    "vl_tot_cred_desc_per",
    "vl_cred_fin_aprop",
    "vl_ret_nc",
    "vl_out_ded_nc",
    "vl_cont_nc_rec",
    "vl_cred_ref",
    "vl_tot_cont_nc_dev",
    "vl_ret_nc_dev",
    "vl_out_ded_nc_dev",
    "vl_cont_nc_rec_dev",
    "vl_cred_ref_dev",
]


def _handle_m600(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M600_CAMPOS, campos)
    _apply_dec(d, *_M600_CAMPOS)
    return d


_M610_CAMPOS = [
    "cod_cont",
    "vl_rec_brt",
    "vl_bc_cont",
    "aliq_cofins_cont",
    "quant_bc_cofins_cont",
    "aliq_cofins_cont_t",
    "vl_cont_apr",
    "vl_cred_exc_apur",
    "vl_cont_per_apur",
    "vl_exc",
]

_M610_DEC = [c for c in _M610_CAMPOS if c != "cod_cont"]


def _handle_m610(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_M610_CAMPOS, campos)
    _apply_dec(d, *_M610_DEC)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco P — Contribuição Previdenciária sobre Receita Bruta
# ─────────────────────────────────────────────────────────────────────────────

_P010_CAMPOS = ["cnpj"]


def _handle_p010(campos: List[str]) -> Dict[str, Any]:
    return _zip_campos(_P010_CAMPOS, campos)


_P100_CAMPOS = [
    "dt_ini",
    "dt_fin",
    "vl_rec_tot_est",
    "cod_ativ_econ",
    "vl_rec_ativ_estab_princ",
    "vl_rec_demais_ativ",
    "aliq_princ",
    "val_contrib_aprop",
    "vl_contrib_previdenc",
]


def _handle_p100(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_P100_CAMPOS, campos)
    _apply_dates(d, "dt_ini", "dt_fin")
    _apply_dec(
        d,
        "vl_rec_tot_est",
        "vl_rec_ativ_estab_princ",
        "vl_rec_demais_ativ",
        "aliq_princ",
        "val_contrib_aprop",
        "vl_contrib_previdenc",
    )
    return d


_P200_CAMPOS = [
    "per_ref",
    "vl_cont_apurada",
    "vl_ded_folha",
    "vl_out_ded",
    "vl_cont_dev",
    "vl_out_rec",
]


def _handle_p200(campos: List[str]) -> Dict[str, Any]:
    d = _zip_campos(_P200_CAMPOS, campos)
    _apply_dec(
        d,
        "vl_cont_apurada",
        "vl_ded_folha",
        "vl_out_ded",
        "vl_cont_dev",
        "vl_out_rec",
    )
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 9
# ─────────────────────────────────────────────────────────────────────────────


def _handle_9900(campos: List[str]) -> Dict[str, Any]:
    return {
        "reg": campos[0].strip() if campos else "",
        "qt_reg_blc": campos[1].strip() if len(campos) > 1 else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parser principal
# ─────────────────────────────────────────────────────────────────────────────


class SpedEfdContribParser(SpedParser):
    """Parser para SPED EFD-Contribuições (PIS/COFINS)."""

    def __init__(self) -> None:
        super().__init__()
        self._register_handlers()

    def _register_handlers(self) -> None:
        # Bloco 0
        self.register_handler("0000", _handle_0000)
        self.register_handler("0001", _handle_ind_mov)
        self.register_handler("0110", _handle_0110)
        self.register_handler("0150", _handle_0150)
        self.register_handler("0200", _handle_0200)
        self.register_handler("0990", _handle_qt_lin)
        # Bloco A
        self.register_handler("A001", _handle_ind_mov)
        self.register_handler("A100", _handle_a100)
        self.register_handler("A990", _handle_qt_lin)
        # Bloco C
        self.register_handler("C001", _handle_ind_mov)
        self.register_handler("C100", _handle_c100)
        self.register_handler("C181", _handle_c181)
        self.register_handler("C185", _handle_c185)
        self.register_handler("C990", _handle_qt_lin)
        # Bloco D
        self.register_handler("D001", _handle_ind_mov)
        self.register_handler("D100", _handle_d100)
        self.register_handler("D990", _handle_qt_lin)
        # Bloco F
        self.register_handler("F001", _handle_ind_mov)
        self.register_handler("F100", _handle_f100)
        self.register_handler("F990", _handle_qt_lin)
        # Bloco M
        self.register_handler("M001", _handle_ind_mov)
        self.register_handler("M100", _handle_m100)
        self.register_handler("M200", _handle_m200)
        self.register_handler("M210", _handle_m210)
        self.register_handler("M500", _handle_m500)
        self.register_handler("M600", _handle_m600)
        self.register_handler("M610", _handle_m610)
        self.register_handler("M990", _handle_qt_lin)
        # Bloco P
        self.register_handler("P001", _handle_ind_mov)
        self.register_handler("P010", _handle_p010)
        self.register_handler("P100", _handle_p100)
        self.register_handler("P200", _handle_p200)
        self.register_handler("P990", _handle_qt_lin)
        # Bloco 9
        self.register_handler("9001", _handle_ind_mov)
        self.register_handler("9900", _handle_9900)
        self.register_handler("9990", _handle_qt_lin)
        self.register_handler("9999", _handle_qt_lin)
