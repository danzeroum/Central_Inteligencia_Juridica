"""Prometheus metrics específicas do módulo fiscal (S-E.1).

Complementam as métricas de agentes/integrações com visibilidade do pipeline
de escrituração: uploads, apurações, achados e retificações.
"""

from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram

    _ENABLED = True
except ImportError:  # pragma: no cover
    _ENABLED = False

if _ENABLED:
    escrituracoes_processadas = Counter(
        "fiscal_escrituracoes_processadas_total",
        "Escriturações processadas pelo pipeline SPED",
        ["tipo", "status"],
    )
    apuracoes_realizadas = Counter(
        "fiscal_apuracoes_realizadas_total",
        "Apurações fiscais calculadas",
        ["tributo", "situacao"],
    )
    achados_registrados = Counter(
        "fiscal_achados_registrados_total",
        "Achados de regra registrados",
        ["severidade", "regra_id"],
    )
    retificacoes_geradas = Counter(
        "fiscal_retificacoes_geradas_total",
        "Arquivos SPED retificados gerados",
        ["tipo"],
    )
    lotes_aprovados = Counter(
        "fiscal_lotes_hitl_aprovados_total",
        "Lotes aprovados via HITL",
    )
    escrituracoes_pendentes = Gauge(
        "fiscal_escrituracoes_pendentes",
        "Escriturações com status processando",
    )
    saldo_apurado_abs = Histogram(
        "fiscal_saldo_apurado_abs",
        "Valor absoluto do saldo apurado (ignora sinal)",
        ["tributo"],
        buckets=[0, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000],
    )
else:  # pragma: no cover - sem prometheus_client instalado

    class _Noop:
        def labels(self, **_):
            return self

        def inc(self, *_, **__):
            pass

        def set(self, *_, **__):
            pass

        def observe(self, *_, **__):
            pass

    escrituracoes_processadas = _Noop()
    apuracoes_realizadas = _Noop()
    achados_registrados = _Noop()
    retificacoes_geradas = _Noop()
    lotes_aprovados = _Noop()
    escrituracoes_pendentes = _Noop()
    saldo_apurado_abs = _Noop()


def record_escrituracao(tipo: str, status: str) -> None:
    escrituracoes_processadas.labels(tipo=tipo, status=status).inc()


def record_apuracao(tributo: str, situacao: str, saldo: float = 0.0) -> None:
    apuracoes_realizadas.labels(tributo=tributo, situacao=situacao).inc()
    saldo_apurado_abs.labels(tributo=tributo).observe(abs(saldo))


def record_achados(resultados: list) -> None:
    for r in resultados:
        achados_registrados.labels(
            severidade=getattr(r, "severidade", "?"),
            regra_id=getattr(r, "regra_id", "?"),
        ).inc()


def record_retificacao(tipo: str) -> None:
    retificacoes_geradas.labels(tipo=tipo).inc()


def record_lote_aprovado() -> None:
    lotes_aprovados.inc()
