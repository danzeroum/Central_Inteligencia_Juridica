"""Validador de layout EFD ICMS/IPI para arquivos SPED retificados (S-D.2).

Valida que cada registro do arquivo retificado respeita o leiaute oficial
(Guia Prático EFD ICMS/IPI v3.1.5, jan/2025): quantidade de campos esperada
por tipo de registro.

Abordagem minimalista: registros desconhecidos são aceitos com aviso, não
rejeitados, para não bloquear arquivos com versões de leiaute futuras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Quantidade de campos esperada (incluindo o campo TIPO_REGISTRO).
# Fonte: Guia Prático EFD ICMS/IPI v3.1.5 (jan/2025).
_CAMPOS_ESPERADOS: Dict[str, int] = {
    # Bloco 0 — Abertura e identificação
    "0000": 16,
    "0001": 2,
    "0002": 3,
    "0005": 11,
    "0015": 3,
    "0100": 11,
    "0150": 10,
    "0175": 5,
    "0190": 3,
    "0200": 14,
    "0205": 4,
    "0206": 2,
    "0210": 4,
    "0220": 3,
    "0300": 9,
    "0305": 4,
    "0400": 3,
    "0450": 3,
    "0460": 3,
    "0500": 7,
    "0600": 6,
    "0990": 2,
    # Bloco C — Documentos fiscais I
    "C001": 2,
    "C100": 26,
    "C101": 3,
    "C105": 3,
    "C110": 3,
    "C111": 2,
    "C112": 7,
    "C113": 7,
    "C114": 6,
    "C115": 3,
    "C116": 2,
    "C120": 10,
    "C130": 10,
    "C140": 6,
    "C141": 3,
    "C160": 6,
    "C165": 4,
    "C170": 24,
    "C172": 4,
    "C173": 7,
    "C174": 6,
    "C175": 11,
    "C176": 9,
    "C177": 3,
    "C178": 5,
    "C179": 9,
    "C180": 9,
    "C181": 8,
    "C185": 8,
    "C186": 8,
    "C190": 8,
    "C195": 3,
    "C197": 6,
    "C990": 2,
    # Bloco D — Documentos fiscais II
    "D001": 2,
    "D100": 24,
    "D990": 2,
    # Bloco E — Apuração do ICMS e IPI
    "E001": 2,
    "E100": 3,
    "E110": 15,
    "E111": 5,
    "E112": 4,
    "E113": 7,
    "E115": 4,
    "E116": 7,
    "E200": 3,
    "E210": 14,
    "E220": 5,
    "E230": 5,
    "E240": 7,
    "E250": 7,
    "E300": 3,
    "E310": 15,
    "E311": 5,
    "E312": 4,
    "E313": 7,
    "E316": 7,
    "E500": 3,
    "E510": 6,
    "E520": 8,
    "E530": 6,
    "E990": 2,
    # Bloco G — Controle do crédito ICMS do Ativo Permanente
    "G001": 2,
    "G110": 7,
    "G125": 9,
    "G126": 8,
    "G130": 7,
    "G140": 4,
    "G990": 2,
    # Bloco H — Inventário
    "H001": 2,
    "H005": 4,
    "H010": 10,
    "H020": 5,
    "H030": 4,
    "H990": 2,
    # Bloco K — Controle da produção e do estoque
    "K001": 2,
    "K010": 3,
    "K100": 3,
    "K200": 6,
    "K210": 4,
    "K215": 4,
    "K220": 4,
    "K230": 5,
    "K235": 4,
    "K250": 4,
    "K255": 4,
    "K260": 6,
    "K265": 4,
    "K270": 5,
    "K275": 4,
    "K280": 5,
    "K290": 5,
    "K291": 4,
    "K292": 4,
    "K300": 4,
    "K301": 3,
    "K302": 4,
    "K990": 2,
    # Bloco 1 — Outras informações
    "1001": 2,
    "1010": 15,
    "1100": 10,
    "1105": 5,
    "1110": 5,
    "1200": 6,
    "1210": 4,
    "1250": 4,
    "1255": 4,
    "1300": 5,
    "1310": 3,
    "1320": 3,
    "1350": 4,
    "1360": 4,
    "1370": 4,
    "1390": 3,
    "1391": 3,
    "1400": 5,
    "1500": 10,
    "1510": 4,
    "1520": 4,
    "1600": 5,
    "1601": 4,
    "1700": 8,
    "1710": 5,
    "1800": 7,
    "1809": 2,
    "1900": 8,
    "1910": 3,
    "1920": 8,
    "1921": 3,
    "1922": 3,
    "1923": 3,
    "1925": 3,
    "1926": 3,
    "1960": 7,
    "1970": 6,
    "1975": 4,
    "1980": 4,
    "1990": 2,
    # Bloco 9 — Encerramento
    "9001": 2,
    "9900": 3,
    "9990": 2,
    "9999": 2,
}


@dataclass
class ErroLayout:
    tipo_registro: str
    numero_linha: int
    mensagem: str
    campos_encontrados: Optional[int] = None
    campos_esperados: Optional[int] = None


@dataclass
class ResultadoValidacaoLayout:
    valido: bool
    erros: List[ErroLayout] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    total_registros: int = 0
    registros_validados: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valido": self.valido,
            "total_registros": self.total_registros,
            "registros_validados": self.registros_validados,
            "erros": [
                {
                    "tipo_registro": e.tipo_registro,
                    "numero_linha": e.numero_linha,
                    "mensagem": e.mensagem,
                    "campos_encontrados": e.campos_encontrados,
                    "campos_esperados": e.campos_esperados,
                }
                for e in self.erros
            ],
            "avisos": self.avisos,
        }


def validar_layout(
    records: List[Dict[str, Any]],
) -> ResultadoValidacaoLayout:
    """Valida lista de registros canônicos contra o leiaute EFD ICMS/IPI v3.1.5.

    Cada registro deve ter ``tipo_registro`` (str) e ``dados`` (dict ou None).
    Campo ``_raw`` em dados é aceito como lista de valores brutos.

    Registros com tipo desconhecido geram aviso, não erro.
    """
    erros: List[ErroLayout] = []
    avisos: List[str] = []
    validados = 0

    for i, rec in enumerate(records, start=1):
        tipo = str(rec.get("tipo_registro", "")).upper()
        dados = rec.get("dados") or {}

        if tipo not in _CAMPOS_ESPERADOS:
            avisos.append(
                f"Linha {i}: tipo '{tipo}' não reconhecido no leiaute v3.1.5 — ignorado."
            )
            continue

        esperado = _CAMPOS_ESPERADOS[tipo]

        # Conta campos: _raw tem valores brutos; senão conta chaves do dict
        if "_raw" in dados:
            raw = dados["_raw"]
            encontrado = len(raw) if isinstance(raw, list) else None
        else:
            # +1 para incluir o campo TIPO_REGISTRO implícito
            encontrado = len(dados) + 1 if dados else 1

        if encontrado is not None and encontrado != esperado:
            erros.append(
                ErroLayout(
                    tipo_registro=tipo,
                    numero_linha=i,
                    mensagem=(
                        f"Registro {tipo} na linha {i}: "
                        f"esperado {esperado} campos, encontrado {encontrado}."
                    ),
                    campos_encontrados=encontrado,
                    campos_esperados=esperado,
                )
            )

        validados += 1

    return ResultadoValidacaoLayout(
        valido=len(erros) == 0,
        erros=erros,
        avisos=avisos,
        total_registros=len(records),
        registros_validados=validados,
    )
