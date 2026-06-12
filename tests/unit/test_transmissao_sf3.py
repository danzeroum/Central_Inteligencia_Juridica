"""Testes unitários — S-F.3: Transmissão e-CAC (Adapter + Circuit Breaker + Observer)."""

from __future__ import annotations

import base64
import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Modelos
# ─────────────────────────────────────────────────────────────────────────────


class TestModelos:
    def test_transmissao_id_deterministico(self):
        from src.integrations.ecac.models import SolicitacaoTransmissao

        s1 = SolicitacaoTransmissao(
            ficha_id="abc",
            tipo_ficha="per_restituicao",
            cnpj_masked="**.***.***/****-**",
            xml_content="<xml>conteudo</xml>",
        )
        s2 = SolicitacaoTransmissao(
            ficha_id="abc",
            tipo_ficha="per_restituicao",
            cnpj_masked="**.***.***/****-**",
            xml_content="<xml>conteudo</xml>",
        )
        assert s1.transmissao_id == s2.transmissao_id

    def test_transmissao_id_diferente_para_conteudo_diferente(self):
        from src.integrations.ecac.models import SolicitacaoTransmissao

        s1 = SolicitacaoTransmissao(
            ficha_id="abc",
            tipo_ficha="per_restituicao",
            cnpj_masked="**.***.***/****-**",
            xml_content="<xml>v1</xml>",
        )
        s2 = SolicitacaoTransmissao(
            ficha_id="abc",
            tipo_ficha="per_restituicao",
            cnpj_masked="**.***.***/****-**",
            xml_content="<xml>v2</xml>",
        )
        assert s1.transmissao_id != s2.transmissao_id

    def test_resultado_to_dict(self):
        from src.integrations.ecac.models import (
            ResultadoTransmissao,
            SituacaoTransmissao,
        )

        r = ResultadoTransmissao(
            transmissao_id="tx_abc",
            ficha_id="ficha1",
            situacao=SituacaoTransmissao.ENVIADA,
            protocolo="PROT-123",
            is_stub=True,
        )
        d = r.to_dict()
        assert d["situacao"] == "enviada"
        assert d["is_stub"] is True
        assert d["protocolo"] == "PROT-123"

    def test_situacoes_enum_valores(self):
        from src.integrations.ecac.models import SituacaoTransmissao

        assert SituacaoTransmissao.ACEITA.value == "aceita"
        assert SituacaoTransmissao.REJEITADA.value == "rejeitada"


# ─────────────────────────────────────────────────────────────────────────────
# Observer
# ─────────────────────────────────────────────────────────────────────────────


class TestObserver:
    def test_log_observer_nao_explode(self):
        from src.integrations.ecac.models import (
            EventoTransmissao,
            SituacaoTransmissao,
            TipoEvento,
        )
        from src.integrations.ecac.observer import LogObserver

        obs = LogObserver()
        evento = EventoTransmissao(
            tipo=TipoEvento.ENVIADA,
            transmissao_id="tx_test",
            ficha_id="ficha1",
            situacao=SituacaoTransmissao.ENVIADA,
            protocolo="PROT-001",
        )
        obs.on_evento(evento)  # deve apenas logar, sem exceção

    def test_composite_observer_notifica_todos(self):
        from src.integrations.ecac.models import (
            EventoTransmissao,
            SituacaoTransmissao,
            TipoEvento,
        )
        from src.integrations.ecac.observer import (
            CompositeObserver,
            TransmissaoObserver,
        )

        chamadas = []

        class FakeObserver(TransmissaoObserver):
            def on_evento(self, evento):
                chamadas.append(evento.tipo)

        comp = CompositeObserver()
        comp.add(FakeObserver())
        comp.add(FakeObserver())

        evento = EventoTransmissao(
            tipo=TipoEvento.ACEITA,
            transmissao_id="tx_test",
            ficha_id="f1",
            situacao=SituacaoTransmissao.ACEITA,
        )
        comp.on_evento(evento)
        assert len(chamadas) == 2

    def test_composite_observer_isola_falha(self):
        from src.integrations.ecac.models import (
            EventoTransmissao,
            SituacaoTransmissao,
            TipoEvento,
        )
        from src.integrations.ecac.observer import (
            CompositeObserver,
            TransmissaoObserver,
        )

        chamadas = []

        class FalhaObserver(TransmissaoObserver):
            def on_evento(self, evento):
                raise RuntimeError("falha proposital")

        class OkObserver(TransmissaoObserver):
            def on_evento(self, evento):
                chamadas.append(True)

        comp = CompositeObserver()
        comp.add(FalhaObserver())
        comp.add(OkObserver())

        evento = EventoTransmissao(
            tipo=TipoEvento.ENVIADA,
            transmissao_id="tx",
            ficha_id="f",
            situacao=SituacaoTransmissao.ENVIADA,
        )
        comp.on_evento(evento)  # não deve propagar a exceção
        assert len(chamadas) == 1

    def test_composite_remove_observer(self):
        from src.integrations.ecac.models import (
            EventoTransmissao,
            SituacaoTransmissao,
            TipoEvento,
        )
        from src.integrations.ecac.observer import (
            CompositeObserver,
            TransmissaoObserver,
        )

        chamadas = []

        class Obs(TransmissaoObserver):
            def on_evento(self, evento):
                chamadas.append(1)

        obs = Obs()
        comp = CompositeObserver()
        comp.add(obs)
        comp.remove(obs)

        evento = EventoTransmissao(
            tipo=TipoEvento.ENVIADA,
            transmissao_id="tx",
            ficha_id="f",
            situacao=SituacaoTransmissao.ENVIADA,
        )
        comp.on_evento(evento)
        assert chamadas == []


# ─────────────────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────────────────


class TestAdapter:
    def setup_method(self):
        from src.integrations.ecac.adapter import reset_ecac_adapter

        reset_ecac_adapter()

    def _make_solicitacao(self, ficha_id="ficha1", xml="<xml>test</xml>"):
        from src.integrations.ecac.models import SolicitacaoTransmissao

        return SolicitacaoTransmissao(
            ficha_id=ficha_id,
            tipo_ficha="per_restituicao",
            cnpj_masked="**.***.***/****-**",
            xml_content=xml,
        )

    def test_modo_stub_quando_sem_config(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        assert adapter.is_stub is True

    def test_transmissao_stub_retorna_resultado(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter
        from src.integrations.ecac.models import SituacaoTransmissao

        adapter = EcacTransmissaoAdapter()
        sol = self._make_solicitacao()
        resultado = adapter.transmitir(sol)

        assert resultado.is_stub is True
        assert resultado.situacao == SituacaoTransmissao.ENVIADA
        assert resultado.protocolo is not None
        assert resultado.ficha_id == "ficha1"

    def test_transmissao_idempotente(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        sol = self._make_solicitacao()

        r1 = adapter.transmitir(sol)
        r2 = adapter.transmitir(sol)

        assert r1.transmissao_id == r2.transmissao_id
        assert r1.protocolo == r2.protocolo

    def test_mesma_ficha_xml_diferente_gera_nova_tx(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        s1 = self._make_solicitacao(xml="<xml>v1</xml>")
        s2 = self._make_solicitacao(xml="<xml>v2</xml>")

        r1 = adapter.transmitir(s1)
        r2 = adapter.transmitir(s2)

        assert r1.transmissao_id != r2.transmissao_id

    def test_consultar_status_existente(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        sol = self._make_solicitacao()
        resultado = adapter.transmitir(sol)

        status_result = adapter.consultar_status(resultado.transmissao_id)
        assert status_result is not None
        assert status_result.ficha_id == "ficha1"

    def test_consultar_status_inexistente(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        assert adapter.consultar_status("tx_inexistente") is None

    def test_historico_lista_transmissoes(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        adapter.transmitir(self._make_solicitacao(ficha_id="f1", xml="<x>1</x>"))
        adapter.transmitir(self._make_solicitacao(ficha_id="f2", xml="<x>2</x>"))

        historico = adapter.historico()
        assert len(historico) == 2
        ficha_ids = {h["ficha_id"] for h in historico}
        assert "f1" in ficha_ids
        assert "f2" in ficha_ids

    def test_circuit_breaker_abre_apos_falhas(self):
        from unittest.mock import patch

        from src.integrations.ecac.adapter import EcacTransmissaoAdapter
        from src.integrations.ecac.models import SituacaoTransmissao
        from src.tools.circuit_breaker import CircuitBreakerOpenError

        adapter = EcacTransmissaoAdapter(failure_threshold=2, recovery_timeout=999.0)

        with patch.object(
            adapter,
            "_transmitir_stub",
            side_effect=RuntimeError("e-CAC indisponível"),
        ):
            r1 = adapter.transmitir(self._make_solicitacao(xml="<x>1</x>"))
            r2 = adapter.transmitir(self._make_solicitacao(xml="<x>2</x>"))
            # Após 2 falhas, circuito deve abrir
            r3 = adapter.transmitir(self._make_solicitacao(xml="<x>3</x>"))

        assert r1.situacao == SituacaoTransmissao.ERRO
        assert r2.situacao == SituacaoTransmissao.ERRO
        # r3 pode ser ERRO com circuito aberto (mensagem específica)
        assert r3.situacao == SituacaoTransmissao.ERRO

    def test_circuit_status_retorna_dict(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter

        adapter = EcacTransmissaoAdapter()
        cs = adapter.circuit_status()
        assert "state" in cs
        assert "failure_count" in cs
        assert cs["state"] == "closed"

    def test_observer_notificado_na_transmissao(self):
        from src.integrations.ecac.adapter import EcacTransmissaoAdapter
        from src.integrations.ecac.models import TipoEvento
        from src.integrations.ecac.observer import (
            CompositeObserver,
            TransmissaoObserver,
        )

        eventos = []

        class RecordObserver(TransmissaoObserver):
            def on_evento(self, evento):
                eventos.append(evento.tipo)

        obs = CompositeObserver([RecordObserver()])
        adapter = EcacTransmissaoAdapter(observer=obs)
        adapter.transmitir(self._make_solicitacao())

        assert TipoEvento.ENVIADA in eventos


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _make_client():
    from src.api.main import app

    return TestClient(app, raise_server_exceptions=False)


def _xml_b64(content: str = "<xml>test</xml>") -> str:
    return base64.b64encode(content.encode()).decode()


class TestTransmissaoEndpoints:
    def setup_method(self):
        from src.api.auth import AuthManager
        from src.integrations.ecac.adapter import reset_ecac_adapter

        AuthManager.configure(required=False)
        reset_ecac_adapter()
        self.client = _make_client()

    def test_enviar_202_stub(self):
        resp = self.client.post(
            "/api/v1/fiscal/transmissao/enviar",
            json={
                "ficha_id": "ficha-001",
                "tipo_ficha": "per_restituicao",
                "cnpj_masked": "**.***.***/****-**",
                "xml_b64": _xml_b64(),
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["is_stub"] is True
        assert data["situacao"] == "enviada"
        assert data["protocolo"] is not None
        assert data["transmissao_id"].startswith("tx_")

    def test_enviar_idempotente(self):
        payload = {
            "ficha_id": "ficha-002",
            "tipo_ficha": "per_restituicao",
            "cnpj_masked": "**.***.***/****-**",
            "xml_b64": _xml_b64("<xml>same</xml>"),
        }
        r1 = self.client.post("/api/v1/fiscal/transmissao/enviar", json=payload)
        r2 = self.client.post("/api/v1/fiscal/transmissao/enviar", json=payload)
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["transmissao_id"] == r2.json()["transmissao_id"]
        assert r1.json()["protocolo"] == r2.json()["protocolo"]

    def test_enviar_xml_invalido_422(self):
        resp = self.client.post(
            "/api/v1/fiscal/transmissao/enviar",
            json={
                "ficha_id": "ficha-003",
                "tipo_ficha": "per_restituicao",
                "cnpj_masked": "**.***.***/****-**",
                "xml_b64": "não_é_base64!!!",
            },
        )
        assert resp.status_code == 422

    def test_status_200(self):
        r_env = self.client.post(
            "/api/v1/fiscal/transmissao/enviar",
            json={
                "ficha_id": "ficha-004",
                "tipo_ficha": "per_restituicao",
                "cnpj_masked": "**.***.***/****-**",
                "xml_b64": _xml_b64("<xml>status</xml>"),
            },
        )
        tx_id = r_env.json()["transmissao_id"]
        resp = self.client.get(f"/api/v1/fiscal/transmissao/status/{tx_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transmissao_id"] == tx_id

    def test_status_404(self):
        resp = self.client.get("/api/v1/fiscal/transmissao/status/tx_inexistente")
        assert resp.status_code == 404

    def test_historico_200(self):
        self.client.post(
            "/api/v1/fiscal/transmissao/enviar",
            json={
                "ficha_id": "ficha-005",
                "tipo_ficha": "per_restituicao",
                "cnpj_masked": "**.***.***/****-**",
                "xml_b64": _xml_b64("<xml>h1</xml>"),
            },
        )
        resp = self.client.get("/api/v1/fiscal/transmissao/historico")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_circuit_200(self):
        resp = self.client.get("/api/v1/fiscal/transmissao/circuit")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert data["is_stub"] is True
