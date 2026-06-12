"""K-anonimato para dados de saúde agregados.

Suprime células com contagem < k, substituindo o valor por None (NaN) e
adicionando a coluna `suprimido=True`.  O badge 🔒 é responsabilidade da
camada de apresentação (ver frontend).

Referência: resolução CNS 510/2016 (dados de saúde); k≥5 recomendado para
dados de morbidade hospitalar (SIH-RD, SIA-SUS).
"""

from __future__ import annotations

_DEFAULT_K = 5


def suppress_k(df, *, col: str, k: int = _DEFAULT_K):
    """Suprime contagens < k no DataFrame Polars.

    Args:
        df: polars.DataFrame com uma coluna numérica de contagem.
        col: nome da coluna de contagem.
        k: limiar.  Células com valor < k são suprimidas.

    Returns:
        polars.DataFrame com coluna ``col`` substituída por None quando
        suprimida e nova coluna booleana ``suprimido``.
    """
    try:
        import polars as pl
    except ImportError as e:
        raise ImportError("pip install polars") from e

    return df.with_columns(
        pl.when(pl.col(col) < k).then(None).otherwise(pl.col(col)).alias(col),
        (pl.col(col) < k).alias("suprimido"),
    )


def is_suppressed(value) -> bool:
    """Retorna True se o valor foi suprimido (None ou NaN)."""
    if value is None:
        return True
    try:
        import math

        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False
