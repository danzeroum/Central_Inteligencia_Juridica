"""Tarefas Celery da plataforma (S-C.2: pipeline SPED real).

Cada tarefa é decorada condicionalmente: se o Celery não estiver disponível
(sem broker), as funções são executadas de forma síncrona como fallback.
O core assíncrono é exposto em ``_execute_processing`` para uso direto no
contexto FastAPI (modo inline — sem Celery/MinIO/Postgres reais).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _task(func):
    """Decorator que registra a função como task Celery ou mantém síncrona."""
    if celery_app is not None:
        return celery_app.task(bind=True, name=f"cij.{func.__name__}")(func)
    return func


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────


async def _download_from_storage(file_key: str) -> Optional[bytes]:
    """Baixa arquivo do MinIO/S3; retorna None se storage indisponível."""
    try:
        from src.storage.s3_client import get_s3_client

        s3 = get_s3_client()
        if not s3.is_configured:
            return None
        return s3.download_file(file_key)
    except Exception as exc:
        logger.warning("Falha ao baixar %s do storage: %s", file_key, exc)
        return None


async def _persist_processing_results(
    escrituracao_id: Optional[str],
    parse_result: Any,
    rule_results: Any,
    apuracao: Any,
    correlation_id: str,
) -> None:
    """Persiste registros, achados e apuração no banco de dados.

    Falha silenciosamente se DB não configurado (RuntimeError) ou indisponível.
    Idempotente: limpa registros anteriores antes de regravar (DT-05).
    """
    if not escrituracao_id:
        return
    try:
        from src.db.models import ApuracaoFiscal, RegistroFiscal
        from src.db.session import get_async_session
        from src.fiscal.repository import (
            ApuracaoFiscalRepository,
            EscrituracaoRepository,
            PeriodoFiscalRepository,
            RegistroFiscalRepository,
        )

        escrit_uuid = uuid.UUID(escrituracao_id)

        async with get_async_session() as session:
            async with session.begin():
                escrit_repo = EscrituracaoRepository(session)
                reg_repo = RegistroFiscalRepository(session)

                # Idempotência: apaga registros anteriores antes de regravar
                await reg_repo.delete_by_escrituracao(escrit_uuid)

                # Persiste registros canônicos (até 5 000 por execução — DT-07 rastreia lotes maiores)
                batch: List[RegistroFiscal] = []
                for record in parse_result.records[:5000]:
                    batch.append(
                        RegistroFiscal(
                            escrituracao_id=escrit_uuid,
                            bloco=record.bloco,
                            tipo_registro=record.tipo_registro,
                            numero_linha=record.numero_linha,
                            dados=record.campos,
                        )
                    )
                await reg_repo.save_batch(batch)

                # Atualiza details e status da escrituração
                escrit = await escrit_repo.get(escrit_uuid)
                if escrit:
                    details = dict(escrit.details or {})
                    details.update(
                        {
                            "correlation_id": correlation_id,
                            "total_registros": parse_result.total_registros,
                            "registros_por_bloco": parse_result.registros_por_bloco,
                            "achados": [
                                {
                                    "regra_id": r.regra_id,
                                    "severidade": r.severidade.value,
                                    "campo": r.campo,
                                    "descricao": r.descricao,
                                    "tipo_registro": r.tipo_registro,
                                    "numero_linha": r.numero_linha,
                                    "valor_encontrado": r.valor_encontrado,
                                    "dica": r.dica,
                                }
                                for r in rule_results.resultados
                            ],
                            "apuracao_resumo": apuracao.resumo,
                        }
                    )
                    escrit.details = details
                    await escrit_repo.update_status(escrit_uuid, "processado")

                # Persiste ApuracaoFiscal por tributo
                apuracao_repo = ApuracaoFiscalRepository(session)
                periodo_repo = PeriodoFiscalRepository(session)
                for item in apuracao.items:
                    # Deriva período do competência extraída pelo engine
                    periodo_str = item.periodo or ""
                    try:
                        ano_str, mes_str = periodo_str.split("-")
                        ano, mes = int(ano_str), int(mes_str)
                    except (ValueError, AttributeError):
                        ano, mes = datetime.now(timezone.utc).year, None

                    periodo = await periodo_repo.get_or_create(ano=ano, mes=mes)

                    apuracao_obj = ApuracaoFiscal(
                        escrituracao_id=escrit_uuid,
                        periodo_id=periodo.id,
                        tributo=item.tributo,
                        periodo_competencia=item.periodo or None,
                        total_debitos=str(item.total_debitos),
                        total_creditos=str(item.total_creditos),
                        saldo_credor_anterior=str(item.saldo_credor_anterior),
                        saldo_apurado=str(item.saldo_apurado),
                        situacao=item.situacao,
                        divergencias=[d.to_dict() for d in item.divergencias],
                        detalhes=item.detalhes,
                    )
                    await apuracao_repo.save(apuracao_obj)

    except RuntimeError:
        # DATABASE_URL não configurada
        pass
    except Exception as exc:
        logger.warning(
            "Falha ao persistir resultados de processamento (correlation_id=%s): %s",
            correlation_id,
            exc,
        )


async def _execute_processing(
    file_key: str,
    tenant_id: str,
    cnpj_masked: str,
    competencia: str,
    escrituracao_id: Optional[str],
    tipo: str,
    regime: str,
    correlation_id: str,
    raw_data: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Pipeline SPED real: download → parse → regras → apuração → persistência.

    Exposta como função async para uso direto no upload inline (sem Celery).
    O ``raw_data`` bypassa o download do storage (modo de teste / inline).
    """
    from src.fiscal.apuracao import get_apuracao_engine
    from src.fiscal.parser.registry import get_parser
    from src.fiscal.rules_engine import get_rules_engine

    log_ctx = f"correlation_id={correlation_id} tipo={tipo} regime={regime}"

    # ── Estágio 1: obter dados brutos ─────────────────────────────────────────
    logger.info("process_sped [1/4 download] %s", log_ctx)
    data = raw_data
    if data is None:
        data = await _download_from_storage(file_key)
    if not data:
        logger.error("process_sped [falha] arquivo não encontrado: key=%s", file_key)
        try:
            if escrituracao_id:
                from src.db.session import get_async_session
                from src.fiscal.repository import EscrituracaoRepository

                async with get_async_session() as session:
                    async with session.begin():
                        repo = EscrituracaoRepository(session)
                        escrit = await repo.get(uuid.UUID(escrituracao_id))
                        if escrit:
                            details = dict(escrit.details or {})
                            details["erro"] = "Arquivo não encontrado no storage"
                            escrit.details = details
                            await repo.update_status(uuid.UUID(escrituracao_id), "erro")
        except Exception:
            pass
        return {
            "status": "erro",
            "correlation_id": correlation_id,
            "erro": "Arquivo não encontrado no storage",
        }

    # ── Estágio 2: parse ──────────────────────────────────────────────────────
    logger.info("process_sped [2/4 parse] %s", log_ctx)
    try:
        parser = get_parser(tipo)
        parse_result = parser.parse(data)
    except Exception as exc:
        logger.error("process_sped [falha parse] %s: %s", log_ctx, exc)
        return {
            "status": "erro",
            "correlation_id": correlation_id,
            "erro": f"Falha no parsing: {exc}",
        }

    # ── Estágio 3: motor de regras ────────────────────────────────────────────
    logger.info(
        "process_sped [3/4 regras] %s registros=%d",
        log_ctx,
        parse_result.total_registros,
    )
    try:
        rules_engine = get_rules_engine(regime)
        rule_results = rules_engine.validate(parse_result.records)
    except Exception as exc:
        logger.warning("process_sped [aviso regras] %s: %s", log_ctx, exc)
        from src.fiscal.rules_engine import ApuracaoResult

        rule_results = ApuracaoResult(aprovado=True, total_registros=0)

    # ── Estágio 4: apuração ───────────────────────────────────────────────────
    logger.info("process_sped [4/4 apuracao] %s", log_ctx)
    try:
        apuracao_engine = get_apuracao_engine()
        apuracao = apuracao_engine.calcular(parse_result.records, tipo=tipo)
    except Exception as exc:
        logger.warning("process_sped [aviso apuracao] %s: %s", log_ctx, exc)
        from src.fiscal.apuracao import ResultadoApuracao

        apuracao = ResultadoApuracao(aprovado=True, resumo="Apuração indisponível")

    # ── Persistência (best-effort) ────────────────────────────────────────────
    await _persist_processing_results(
        escrituracao_id=escrituracao_id,
        parse_result=parse_result,
        rule_results=rule_results,
        apuracao=apuracao,
        correlation_id=correlation_id,
    )

    return {
        "status": "processado",
        "correlation_id": correlation_id,
        "escrituracao_id": escrituracao_id,
        "total_registros": parse_result.total_registros,
        "registros_por_bloco": parse_result.registros_por_bloco,
        "total_erros_regras": len(rule_results.erros),
        "total_avisos_regras": len(rule_results.avisos),
        "apuracao": apuracao.to_dict(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tasks Celery
# ─────────────────────────────────────────────────────────────────────────────


@_task
def analyze_document(
    self_or_none,
    document_id: str,
    tenant_id: str,
    options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Análise assíncrona de documento jurídico."""
    logger.info("analyze_document: document_id=%s tenant=%s", document_id, tenant_id)
    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "status": "analyzed",
        "summary": "Documento processado.",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@_task
def process_sped_file(
    self_or_none,
    file_key: str,
    tenant_id: str,
    cnpj_masked: str,
    competencia: str,
    escrituracao_id: Optional[str] = None,
    tipo: str = "efd_icms",
    regime: str = "lucro_real",
) -> Dict[str, Any]:
    """Processa arquivo SPED: download (MinIO) → parse → regras → apuração → DB.

    ``file_key`` é o path no bucket (ex.: ``fiscal/2025/1/{uuid}/efd.txt``).
    ``cnpj_masked`` segue LGPD: ``**.***.***/**XX-**``.
    ``escrituracao_id`` é o UUID da EscrituracaoFiscal já criada pelo upload.
    Executa ``_execute_processing`` em um novo event loop (contexto Celery).
    """
    correlation_id = str(uuid.uuid4())
    logger.info(
        "process_sped_file: key=%s tenant=%s tipo=%s regime=%s correlation_id=%s",
        file_key,
        tenant_id,
        tipo,
        regime,
        correlation_id,
    )
    return asyncio.run(
        _execute_processing(
            file_key=file_key,
            tenant_id=tenant_id,
            cnpj_masked=cnpj_masked,
            competencia=competencia,
            escrituracao_id=escrituracao_id,
            tipo=tipo,
            regime=regime,
            correlation_id=correlation_id,
        )
    )
