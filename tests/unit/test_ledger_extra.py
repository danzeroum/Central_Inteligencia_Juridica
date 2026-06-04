"""Cobertura adicional do DecisionLedger (Frente C cont.).

Cobre o backend Redis (cliente fake), _build_store, refresh do backend
compartilhado, anonimização (LGPD) e export_report.
"""

from __future__ import annotations

import json

import src.utils.ledger as ledger_mod
from src.utils.ledger import DecisionLedger, RedisLedgerStore


class _LedgerPipe:
    def __init__(self, parent):
        self.parent = parent
        self._ops = []

    def delete(self, key):
        self._ops.append(("del", None))
        return self

    def rpush(self, key, *vals):
        self._ops.append(("rpush", vals))
        return self

    def execute(self):
        for op, vals in self._ops:
            if op == "del":
                self.parent.data = []
            else:
                self.parent.data.extend(vals)


class FakeRedisLedger:
    def __init__(self):
        self.data = []

    def rpush(self, key, value):
        self.data.append(value)

    def lrange(self, key, a, b):
        return list(self.data)

    def pipeline(self):
        return _LedgerPipe(self)


def test_redis_store_append_load_replace():
    store = RedisLedgerStore(FakeRedisLedger())
    assert store.shared is True
    store.append({"id": "1", "x": 1})
    assert store.load_all() == [{"id": "1", "x": 1}]
    store.replace_all([{"id": "2"}])
    assert store.load_all() == [{"id": "2"}]


def test_redis_store_load_all_decodifica_bytes():
    fake = FakeRedisLedger()
    fake.data = [json.dumps({"id": "b"}).encode("utf-8")]
    store = RedisLedgerStore(fake)
    assert store.load_all() == [{"id": "b"}]


def test_build_store_redis(monkeypatch):
    monkeypatch.setenv("LEDGER_BACKEND", "redis")
    monkeypatch.setattr(
        "src.utils.redis_client.get_shared_redis_client",
        lambda *a, **k: FakeRedisLedger(),
    )
    store = ledger_mod._build_store("logs/x.json")
    assert isinstance(store, RedisLedgerStore)


def test_build_store_redis_sem_cliente_cai_para_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv("LEDGER_BACKEND", "redis")
    monkeypatch.setattr(
        "src.utils.redis_client.get_shared_redis_client", lambda *a, **k: None
    )
    store = ledger_mod._build_store(str(tmp_path / "l.json"))
    assert store.shared is False  # FileLedgerStore


def test_refresh_de_backend_compartilhado(tmp_path):
    led = DecisionLedger(log_file=str(tmp_path / "l.json"))
    fake = FakeRedisLedger()
    led._store = RedisLedgerStore(fake)
    led.entries = []
    # Outra réplica gravou direto no backend compartilhado.
    fake.data = [json.dumps({"id": "x", "agent_type": "A", "decision_type": "D"})]
    # get_entries chama _refresh_if_shared → recarrega.
    entries = led.get_entries(decision_type="D")
    assert any(e["id"] == "x" for e in entries)


def test_anonymize_entries(tmp_path):
    led = DecisionLedger(log_file=str(tmp_path / "l.json"))
    led.log_decision("Agent", "DEC", {"subject_id": "joao", "outro": 1})
    afetadas = led.anonymize_entries(field_name="subject_id", value="joao")
    assert afetadas == 1
    assert led.entries[-1]["metadata"]["subject_id"] == "[ANONYMIZED]"


def test_export_report(tmp_path):
    led = DecisionLedger(log_file=str(tmp_path / "l.json"))
    led.log_decision("AgentA", "DEC1", {})
    led.log_decision("AgentB", "DEC2", {})
    out = tmp_path / "report.json"
    path = led.export_report(output_file=str(out))
    assert path == str(out)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["total_entries"] == 2
    assert "AgentA" in report["agents_summary"]
    assert "DEC1" in report["agents_summary"]["AgentA"]["decision_types"]
