"""SPED TXT writer — gera arquivo retificado a partir de registros canônicos.

Leiaute conferido contra Guia Prático EFD ICMS/IPI v3.1.5 (jan/2025).

Formato de saída:
    |TIPO_REGISTRO|campo1|campo2|...|campoN|<CRLF>

Retificação: registro 0000.cod_fin="1" (original="0").
Totalizador: registro 9999.qdt_lins = total de linhas do arquivo.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class SpedWriter:
    """Gera bytes de arquivo SPED EFD-ICMS/IPI a partir de registros canônicos."""

    def gerar(
        self,
        records: List[Dict[str, Any]],
        ind_ret: bool = True,
    ) -> bytes:
        """Serializa lista de registros canônicos em bytes SPED (CRLF).

        Args:
            records: lista de dicts com chaves ``tipo_registro`` e ``dados``.
                     ``dados`` pode conter ``_raw`` (lista de valores brutos)
                     ou campos nomeados em ordem de inserção.
            ind_ret: se True, seta 0000.cod_fin="1" (arquivo de retificação).

        Returns:
            Bytes UTF-8 com linhas separadas por ``\\r\\n``.
        """
        lines: List[str] = []
        idx_9999: Optional[int] = None

        for i, rec in enumerate(records):
            tipo = rec["tipo_registro"]
            dados: Dict[str, Any] = dict(rec.get("dados") or {})

            if tipo == "0000" and ind_ret and "cod_fin" in dados:
                dados = {**dados, "cod_fin": "1"}

            if tipo == "9999":
                idx_9999 = i

            lines.append(self._to_line(tipo, dados))

        total = len(lines)

        if idx_9999 is not None:
            dados_9999: Dict[str, Any] = dict(records[idx_9999].get("dados") or {})
            if "_raw" in dados_9999:
                dados_9999 = {"_raw": [str(total)]}
            else:
                keys = list(dados_9999.keys())
                key = keys[0] if keys else "qdt_lins"
                dados_9999 = {key: str(total)}
            lines[idx_9999] = self._to_line("9999", dados_9999)

        return "\r\n".join(lines).encode("utf-8")

    @staticmethod
    def _to_line(tipo_registro: str, dados: Dict[str, Any]) -> str:
        """Converte um registro canônico em linha SPED pipe-delimited.

        Se ``dados`` contiver ``_raw``, usa a lista diretamente (preserva
        registros desconhecidos sem reinterpretação de campos).
        """
        if "_raw" in dados:
            campos = [str(v) for v in dados["_raw"]]
        else:
            campos = [str(v) if v is not None else "" for v in dados.values()]
        return "|" + "|".join([tipo_registro] + campos) + "|"
