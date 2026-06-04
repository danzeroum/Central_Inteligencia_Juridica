"""Cobertura de utilitários e módulos pequenos antes descobertos (Frente C cont.).

Alvos: tool_utils, memory_utils, key_provider, hierarchical_planner,
resilient_chain, rate_limiter e o worker agente_jurisprudencia.
"""

from __future__ import annotations

import types

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from src.agents import agente_jurisprudencia as aj
from src.api.rate_limiter import RateLimiter
from src.chains.resilient_chain import ChainStep, ResilientPromptChain
from src.planning.hierarchical_planner import HierarchicalPlanner
from src.utils.key_provider import EnvKeyProvider, _normalise_to_fernet_key
from src.utils.memory_utils import MemoryStore
from src.utils.tool_utils import wrap_sync_tool


# ── tool_utils ───────────────────────────────────────────────────────────────
async def test_wrap_sync_tool_vira_async():
    async_tool = wrap_sync_tool(lambda s: s.upper())
    assert await async_tool("abc") == "ABC"


# ── memory_utils ─────────────────────────────────────────────────────────────
def test_memory_store_set_get_snapshot():
    store = MemoryStore()
    assert store.get("x") is None
    assert store.get("x", "default") == "default"
    store.set("x", 1)
    assert store.get("x") == 1
    snap = store.snapshot()
    assert snap == {"x": 1}
    snap["y"] = 2  # cópia não afeta o store
    assert "y" not in store.snapshot()


# ── key_provider ─────────────────────────────────────────────────────────────
def test_normalise_fernet_key_passthrough():
    key = Fernet.generate_key()
    assert _normalise_to_fernet_key(key.decode()) == key


def test_normalise_deriva_de_segredo_arbitrario():
    derived = _normalise_to_fernet_key("segredo-curto")
    # Deve ser uma chave Fernet válida (aceita pelo construtor).
    assert Fernet(derived) is not None


def test_env_key_provider(monkeypatch):
    monkeypatch.delenv("CACHE_ENCRYPTION_KEY", raising=False)
    assert EnvKeyProvider().get_encryption_key() is None
    monkeypatch.setenv("CACHE_ENCRYPTION_KEY", "um-segredo-qualquer")
    key = EnvKeyProvider().get_encryption_key()
    assert key is not None and Fernet(key) is not None


# ── hierarchical_planner ─────────────────────────────────────────────────────
def test_hierarchical_planner_cria_plano():
    planner = HierarchicalPlanner()
    plan = planner.create_plan("automatizar petição")
    assert plan["goal"] == "automatizar petição"
    assert plan["confidence"] == 0.8
    assert plan["steps"]
    step = plan["steps"][0]
    assert step["substeps"]
    assert len(step["alternatives"]) == 2


# ── resilient_chain ──────────────────────────────────────────────────────────
async def test_resilient_chain_sucesso_sequencial():
    chain = ResilientPromptChain(
        steps=[
            ChainStep(name="dobrar", execute=lambda x: x * 2),
            ChainStep(name="incrementar", execute=lambda x: x + 1),
        ]
    )
    assert await chain.execute_with_checkpoints(3) == 7


async def test_resilient_chain_retry_e_sucesso():
    tentativas = {"n": 0}

    def _flaky(x):
        tentativas["n"] += 1
        if tentativas["n"] < 2:
            raise ValueError("transitório")
        return x

    chain = ResilientPromptChain(steps=[ChainStep("flaky", _flaky)], max_retries=3)
    assert await chain.execute_with_checkpoints("ok") == "ok"
    assert tentativas["n"] == 2


async def test_resilient_chain_falha_apos_retries():
    def _sempre_falha(_x):
        raise ValueError("permanente")

    chain = ResilientPromptChain(steps=[ChainStep("x", _sempre_falha)], max_retries=2)
    with pytest.raises(RuntimeError, match="Falha na etapa x"):
        await chain.execute_with_checkpoints("in")


async def test_resilient_chain_step_assincrono():
    async def _async_step(x):
        return x + "!"

    chain = ResilientPromptChain(steps=[ChainStep("a", _async_step)])
    assert await chain.execute_with_checkpoints("oi") == "oi!"


# ── rate_limiter (backend memória) ───────────────────────────────────────────
def _fake_request(ip: str):
    return types.SimpleNamespace(client=types.SimpleNamespace(host=ip))


async def test_rate_limiter_bloqueia_acima_do_limite():
    limiter = RateLimiter(requests_per_minute=2, backend="memory")
    req = _fake_request("9.9.9.9")
    await limiter(req)
    await limiter(req)
    with pytest.raises(HTTPException) as exc:
        await limiter(req)
    assert exc.value.status_code == 429


async def test_rate_limiter_ips_independentes():
    limiter = RateLimiter(requests_per_minute=1, backend="memory")
    await limiter(_fake_request("1.1.1.1"))
    # IP diferente não é afetado pelo limite do primeiro.
    await limiter(_fake_request("2.2.2.2"))


# ── rate_limiter (backend redis, cliente fake) ───────────────────────────────
class _FakePipe:
    def __init__(self, count: int) -> None:
        self._count = count

    def zremrangebyscore(self, *a, **k):
        return self

    def zcard(self, *a, **k):
        return self

    def zadd(self, *a, **k):
        return self

    def expire(self, *a, **k):
        return self

    def execute(self):
        return [None, self._count]


class _FakeRedis:
    def __init__(self, count: int) -> None:
        self._count = count

    def pipeline(self):
        return _FakePipe(self._count)


async def test_rate_limiter_redis_backend_ok():
    limiter = RateLimiter(
        requests_per_minute=5, backend="redis", redis_client=_FakeRedis(count=0)
    )
    assert limiter.backend == "redis"
    await limiter(_fake_request("3.3.3.3"))  # count 0 < 5 → ok


async def test_rate_limiter_redis_backend_bloqueia():
    limiter = RateLimiter(
        requests_per_minute=2, backend="redis", redis_client=_FakeRedis(count=2)
    )
    with pytest.raises(HTTPException) as exc:
        await limiter(_fake_request("4.4.4.4"))
    assert exc.value.status_code == 429


def test_rate_limiter_redis_sem_cliente_cai_para_memoria(monkeypatch):
    # backend=redis mas sem cliente disponível → degrada para memória.
    import src.api.rate_limiter as rl

    monkeypatch.setattr(rl, "get_shared_redis_client", lambda **k: None)
    limiter = RateLimiter(requests_per_minute=1, backend="redis", redis_client=None)
    assert limiter.backend == "memory"


# ── agente_jurisprudencia (worker) ───────────────────────────────────────────
def test_processar_tarefa_retorna_concluido():
    resultado = aj.processar_tarefa({"id_tarefa": "t1", "descricao": "buscar STJ"})
    assert resultado["status"] == "concluido"
    assert resultado["id_tarefa"] == "t1"
    assert resultado["agente"] == "jurisprudencia"


def test_connect_to_redis_falha_retorna_none(monkeypatch):
    import redis

    def _boom(*a, **k):
        raise redis.exceptions.ConnectionError("sem redis")

    monkeypatch.setattr(aj.redis, "Redis", _boom)
    assert aj.connect_to_redis() is None
