"""Cobertura do canal A2A em modo memória (Frente C cont.)."""

from __future__ import annotations

from src.protocols.a2a_channel import A2AChannel, A2AMessage, InMemoryChannel


def _memory_channel() -> A2AChannel:
    ch = A2AChannel()
    ch.using_redis = False
    ch.redis_client = None
    ch.memory_channel = InMemoryChannel()
    return ch


# ── A2AMessage ───────────────────────────────────────────────────────────────
def test_message_to_from_dict_roundtrip():
    msg = A2AMessage(
        message_id="m1",
        sender_id="a",
        receiver_id="b",
        message_type="ping",
        payload={"x": 1},
        priority=2,
    )
    restored = A2AMessage.from_dict(msg.to_dict())
    assert restored.message_id == "m1"
    assert restored.payload == {"x": 1}
    assert restored.priority == 2


# ── InMemoryChannel ──────────────────────────────────────────────────────────
async def test_inmemory_publish_dispara_handlers():
    ch = InMemoryChannel()
    recebidas = []

    async def _async_handler(m):
        recebidas.append(("async", m.message_id))

    def _sync_handler(m):
        recebidas.append(("sync", m.message_id))

    def _bad_handler(m):
        raise ValueError("erro de handler não derruba o publish")

    await ch.subscribe("b", _async_handler)
    await ch.subscribe("b", _sync_handler)
    await ch.subscribe("b", _bad_handler)

    msg = A2AMessage("m1", "a", "b", "ping", {})
    await ch.publish(msg)
    assert ("async", "m1") in recebidas
    assert ("sync", "m1") in recebidas


async def test_inmemory_history_trim():
    ch = InMemoryChannel(max_history=2)
    for i in range(3):
        await ch.publish(A2AMessage(f"m{i}", "a", "b", "ping", {}))
    assert len(ch.message_history) == 2


async def test_inmemory_get_messages_respeita_limite():
    ch = InMemoryChannel()
    for i in range(5):
        await ch.publish(A2AMessage(f"m{i}", "a", "b", "ping", {}))
    msgs = await ch.get_messages("b", limit=3)
    assert len(msgs) == 3


def test_inmemory_history_filtrado_por_agente():
    ch = InMemoryChannel()
    ch.message_history = [
        A2AMessage("m1", "a", "b", "ping", {}),
        A2AMessage("m2", "c", "d", "ping", {}),
    ]
    filtrado = ch.get_history(agent_id="a")
    assert [m.message_id for m in filtrado] == ["m1"]
    assert len(ch.get_history()) == 2


# ── A2AChannel (modo memória) ────────────────────────────────────────────────
async def test_send_e_receive_memoria():
    ch = _memory_channel()
    mid = await ch.send_message("a", "b", "ping", {"v": 1})
    assert mid
    msgs = await ch.receive_messages("b")
    assert len(msgs) == 1
    assert msgs[0].payload == {"v": 1}


async def test_request_response_recebe_resposta(monkeypatch):
    import src.protocols.a2a_channel as a2a_mod

    ch = _memory_channel()
    # Torna o correlation_id previsível para injetar a resposta correspondente.
    fixed = type("U", (), {"__str__": lambda self: "corr-fix", "hex": "corr-fix"})()
    monkeypatch.setattr(a2a_mod.uuid, "uuid4", lambda: fixed)
    resposta = A2AMessage(
        "r1", "b", "a", "pong", {"ok": True}, correlation_id="corr-fix"
    )
    await ch.memory_channel.publish(resposta)
    resultado = await ch.request_response("a", "b", "ping", {}, timeout=1.0)
    assert resultado == {"ok": True}


async def test_request_response_timeout():
    ch = _memory_channel()
    resultado = await ch.request_response("a", "b", "ping", {}, timeout=0.05)
    assert resultado is None


async def test_health_check_memoria():
    ch = _memory_channel()
    health = await ch.health_check()
    assert health["backend"] == "memory"
    assert health["status"] == "healthy"


async def test_subscribe_agent_memoria():
    ch = _memory_channel()
    recebidas = []
    await ch.subscribe_agent("b", lambda m: recebidas.append(m.message_id))
    await ch.send_message("a", "b", "ping", {})
    assert len(recebidas) == 1  # handler disparado uma vez


# ── A2AChannel (modo Redis, cliente async fake) ──────────────────────────────
class _FakeAsyncRedis:
    def __init__(self, fail_ping: bool = False) -> None:
        self.lists: dict = {}
        self.fail_ping = fail_ping

    async def publish(self, channel, message):
        return 1

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, start, end):
        return True

    async def rpop(self, key):
        lst = self.lists.get(key, [])
        return lst.pop() if lst else None

    async def ping(self):
        if self.fail_ping:
            raise RuntimeError("redis down")
        return True


def _redis_channel(**kw) -> A2AChannel:
    ch = A2AChannel()
    ch.using_redis = True
    ch.redis_client = _FakeAsyncRedis(**kw)
    return ch


async def test_a2a_redis_send_receive():
    ch = _redis_channel()
    await ch.send_message("a", "b", "ping", {"v": 1})
    msgs = await ch.receive_messages("b")
    assert len(msgs) == 1
    assert msgs[0].payload == {"v": 1}


async def test_a2a_redis_health_healthy():
    ch = _redis_channel()
    health = await ch.health_check()
    assert health["backend"] == "redis"
    assert health["status"] == "healthy"


async def test_a2a_redis_health_degraded():
    ch = _redis_channel(fail_ping=True)
    health = await ch.health_check()
    assert health["backend"] == "redis"
    assert health["status"] == "degraded"
    assert "error" in health
