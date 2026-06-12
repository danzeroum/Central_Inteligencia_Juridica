"""Adapter e-CAC para transmissão PER/DCOMP (S-F.3).

Padrão Adapter: encapsula o webservice SOAP do e-CAC (Receita Federal) atrás de
uma interface Python limpa. Reusa o CircuitBreaker existente (src/tools/circuit_breaker.py).

Modo de operação:
  ECAC_HOMOLOGACAO_URL definida + certificado A1 disponível → modo real (SOAP)
  Caso contrário → modo stub (simula transmissão, is_stub=True)

Idempotência: cada SolicitacaoTransmissao tem um ``transmissao_id`` determinístico
(hash SHA-256 do ficha_id + conteúdo XML). Re-envio da mesma ficha retorna o
resultado já armazenado sem recontactar o e-CAC.

Circuit breaker:
  failure_threshold=3, recovery_timeout=120s
  Após 3 falhas consecutivas → OPEN → 503 com retry_after
  Após recovery_timeout → HALF_OPEN → tentativa de recuperação
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import Dict, Optional

from src.integrations.ecac.models import (
    EventoTransmissao,
    ResultadoTransmissao,
    SituacaoTransmissao,
    SolicitacaoTransmissao,
    TipoEvento,
)
from src.integrations.ecac.observer import CompositeObserver, _default_observer
from src.tools.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

_ECAC_URL_ENV = "ECAC_HOMOLOGACAO_URL"
_ECAC_CERT_ENV = "CERT_A1_PATH"

# TTL de idempotência em memória (segundos) — suficiente para testes e dev
_IDEM_STORE_MAX = 1000


class EcacTransmissaoAdapter:
    """Adapter para o webservice PER/DCOMP do e-CAC.

    Instanciar diretamente ou via ``get_ecac_adapter()``.
    """

    def __init__(
        self,
        observer: Optional[CompositeObserver] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 120.0,
    ) -> None:
        self._observer = observer or _default_observer()
        self._circuit = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout_seconds=recovery_timeout,
            name="ecac_perdcomp",
        )
        # Idempotency store: transmissao_id → ResultadoTransmissao
        self._idem: Dict[str, ResultadoTransmissao] = {}
        self._lock = threading.Lock()

    @property
    def is_stub(self) -> bool:
        url = os.environ.get(_ECAC_URL_ENV, "").strip()
        cert = os.environ.get(_ECAC_CERT_ENV, "").strip()
        return not (url and cert and os.path.isfile(cert))

    def transmitir(self, solicitacao: SolicitacaoTransmissao) -> ResultadoTransmissao:
        """Transmite a ficha PER/DCOMP ao e-CAC.

        Retorna o resultado existente se o ``transmissao_id`` já foi processado
        (idempotência). Levanta ``CircuitBreakerOpenError`` se o circuito estiver aberto.
        """
        # Idempotência: mesma ficha → mesmo resultado
        with self._lock:
            if solicitacao.transmissao_id in self._idem:
                logger.info(
                    "ecac idempotent: tx=%s já transmitida anteriormente",
                    solicitacao.transmissao_id,
                )
                return self._idem[solicitacao.transmissao_id]

        try:
            if self.is_stub:
                resultado = self._circuit.call(self._transmitir_stub, solicitacao)
            else:
                resultado = self._circuit.call(self._transmitir_real, solicitacao)
        except CircuitBreakerOpenError as exc:
            resultado = ResultadoTransmissao(
                transmissao_id=solicitacao.transmissao_id,
                ficha_id=solicitacao.ficha_id,
                situacao=SituacaoTransmissao.ERRO,
                mensagem=f"e-CAC indisponível (circuit aberto). Tente em {exc.retry_after:.0f}s.",
                is_stub=self.is_stub,
                detalhes={"circuit_state": "open", "retry_after": exc.retry_after},
            )
            self._emit(
                TipoEvento.CIRCUIT_ABERTO,
                resultado,
                mensagem=resultado.mensagem,
            )
            return resultado
        except Exception as exc:
            resultado = ResultadoTransmissao(
                transmissao_id=solicitacao.transmissao_id,
                ficha_id=solicitacao.ficha_id,
                situacao=SituacaoTransmissao.ERRO,
                mensagem=f"Erro na transmissão: {exc}",
                is_stub=self.is_stub,
            )
            self._emit(TipoEvento.ERRO, resultado, mensagem=str(exc))
            return resultado

        # Persistir no store idempotente
        with self._lock:
            if len(self._idem) >= _IDEM_STORE_MAX:
                # Remoção FIFO: descarta a entrada mais antiga
                oldest = next(iter(self._idem))
                del self._idem[oldest]
            self._idem[solicitacao.transmissao_id] = resultado

        self._emit(TipoEvento.ENVIADA, resultado)
        return resultado

    def consultar_status(self, transmissao_id: str) -> Optional[ResultadoTransmissao]:
        """Consulta o status de uma transmissão pelo ID."""
        with self._lock:
            resultado = self._idem.get(transmissao_id)

        if resultado is None:
            return None

        # Em modo stub, simula progressão de estado
        if resultado.is_stub and resultado.situacao == SituacaoTransmissao.ENVIADA:
            resultado.situacao = SituacaoTransmissao.PROCESSANDO
            self._emit(TipoEvento.STATUS_ATUALIZADO, resultado)

        return resultado

    def _transmitir_stub(
        self, solicitacao: SolicitacaoTransmissao
    ) -> ResultadoTransmissao:
        """Simulação de transmissão (sem e-CAC real)."""
        protocolo = f"STUB-{uuid.uuid4().hex[:12].upper()}"
        logger.warning(
            "ecac STUB transmissão: tx=%s ficha=%s protocolo=%s",
            solicitacao.transmissao_id,
            solicitacao.ficha_id,
            protocolo,
        )
        return ResultadoTransmissao(
            transmissao_id=solicitacao.transmissao_id,
            ficha_id=solicitacao.ficha_id,
            situacao=SituacaoTransmissao.ENVIADA,
            protocolo=protocolo,
            mensagem=(
                "Transmissão STUB — configure ECAC_HOMOLOGACAO_URL e CERT_A1_PATH "
                "para envio real ao e-CAC de homologação."
            ),
            is_stub=True,
        )

    def _transmitir_real(
        self, solicitacao: SolicitacaoTransmissao
    ) -> ResultadoTransmissao:
        """Transmissão real via SOAP ao e-CAC (homologação).

        Requer:
          - ECAC_HOMOLOGACAO_URL: URL do webservice SOAP
          - CERT_A1_PATH + CERT_A1_PASSPHRASE: certificado A1 montado em volume
        """
        import ssl

        import httpx

        url = os.environ[_ECAC_URL_ENV]
        cert_path = os.environ[_ECAC_CERT_ENV]
        passphrase = os.environ.get("CERT_A1_PASSPHRASE", "")

        # Envelope SOAP simplificado (leiaute PER/DCOMP Web)
        soap_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<soapenv:Envelope "
            'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:per="http://www.sped.fazenda.gov.br/perdcomp">'
            "<soapenv:Body>"
            f"<per:transmitirPERDCOMP>{solicitacao.xml_content}</per:transmitirPERDCOMP>"
            "</soapenv:Body>"
            "</soapenv:Envelope>"
        )

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_cert_chain(certfile=cert_path, password=passphrase or None)

        with httpx.Client(verify=ctx, timeout=30.0) as client:
            response = client.post(
                url,
                content=soap_body.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "transmitirPERDCOMP",
                },
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"e-CAC retornou HTTP {response.status_code}: {response.text[:200]}"
            )

        protocolo = self._extrair_protocolo(response.text)
        return ResultadoTransmissao(
            transmissao_id=solicitacao.transmissao_id,
            ficha_id=solicitacao.ficha_id,
            situacao=SituacaoTransmissao.ENVIADA,
            protocolo=protocolo,
            is_stub=False,
        )

    @staticmethod
    def _extrair_protocolo(soap_response: str) -> Optional[str]:
        """Extrai o número de protocolo da resposta SOAP do e-CAC."""
        import re

        match = re.search(r"<protocolo>([^<]+)</protocolo>", soap_response)
        return match.group(1) if match else None

    def _emit(
        self,
        tipo: TipoEvento,
        resultado: ResultadoTransmissao,
        mensagem: Optional[str] = None,
    ) -> None:
        evento = EventoTransmissao(
            tipo=tipo,
            transmissao_id=resultado.transmissao_id,
            ficha_id=resultado.ficha_id,
            situacao=resultado.situacao,
            protocolo=resultado.protocolo,
            mensagem=mensagem or resultado.mensagem,
        )
        self._observer.on_evento(evento)

    def circuit_status(self) -> Dict[str, object]:
        """Retorna o estado atual do circuit breaker."""
        return {
            "state": self._circuit.state.value,
            "failure_count": self._circuit._failure_count,
            "name": self._circuit.config.name,
        }

    def historico(self) -> list:
        """Retorna lista de todas as transmissões armazenadas."""
        with self._lock:
            return [r.to_dict() for r in self._idem.values()]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_adapter: Optional[EcacTransmissaoAdapter] = None
_adapter_lock = threading.Lock()


def get_ecac_adapter() -> EcacTransmissaoAdapter:
    global _adapter
    with _adapter_lock:
        if _adapter is None:
            _adapter = EcacTransmissaoAdapter()
    return _adapter


def reset_ecac_adapter() -> None:
    """Força recriação do adapter. Útil em testes."""
    global _adapter
    with _adapter_lock:
        _adapter = None
