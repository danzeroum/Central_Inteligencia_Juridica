"""Cobertura adicional do CacheManager (Frente C cont.): cifra, bytes, expiração."""

from __future__ import annotations

import time

from cryptography.fernet import Fernet

import src.utils.cache_manager as cm_mod
from src.utils.cache_manager import CacheManager


class _Fake:
    def __init__(self):
        self.storage = {}

    def ping(self):
        return True

    def set(self, *, name, value, ex=None):
        self.storage[name] = value
        return True

    def get(self, *, name):
        return self.storage.get(name)

    def delete(self, name):
        return 1 if self.storage.pop(name, None) is not None else 0


def test_redis_get_decodifica_bytes():
    fake = _Fake()
    cm = CacheManager(redis_client=fake)
    key = cm.make_key("TJSP", "status", "b")
    fake.storage[key] = b'{"v": 2}'  # Redis real devolve bytes
    assert cm.get_cached("TJSP", "status", identifier="b") == {"v": 2}


def test_make_key_deterministica():
    cm = CacheManager(redis_client=_Fake())
    assert cm.make_key("TJSP", "c", "id") == cm.make_key("TJSP", "c", "id")
    assert cm.make_key("TJSP", "c", "a") != cm.make_key("TJSP", "c", "b")


def test_memoria_expira(monkeypatch):
    monkeypatch.setattr(cm_mod, "create_redis_client", lambda **k: None)
    cm = CacheManager(redis_client=None)
    key = cm.make_key("X", "c")
    real_monotonic = time.monotonic  # captura antes de patchar (evita recursão)
    cm._write_memory(key, "v", ttl=1)
    monkeypatch.setattr(cm_mod.time, "monotonic", lambda: real_monotonic() + 100)
    assert cm._read_memory(key) is None


def test_build_cipher_desabilitado(monkeypatch):
    monkeypatch.delenv("CACHE_ENCRYPTION_ENABLED", raising=False)
    assert CacheManager._build_cipher() is None


def test_build_cipher_habilitado(monkeypatch):
    monkeypatch.setenv("CACHE_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("CACHE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert CacheManager._build_cipher() is not None


def test_build_cipher_habilitado_sem_chave(monkeypatch):
    monkeypatch.setenv("CACHE_ENCRYPTION_ENABLED", "1")
    monkeypatch.delenv("CACHE_ENCRYPTION_KEY", raising=False)
    assert CacheManager._build_cipher() is None


def test_serialize_deserialize_com_cifra():
    cm = CacheManager(redis_client=_Fake())
    cm._cipher = Fernet(Fernet.generate_key())
    encrypted = cm._serialize({"segredo": 1})
    assert encrypted != '{"segredo": 1}'
    assert cm._deserialize(encrypted) == {"segredo": 1}


def test_deserialize_valor_legado_sem_cifra():
    cm = CacheManager(redis_client=_Fake())
    cm._cipher = Fernet(Fernet.generate_key())
    # Texto puro (gravado antes da cifra) → InvalidToken → usa o valor cru.
    assert cm._deserialize('{"v": 9}') == {"v": 9}


def test_serialize_objeto_nao_serializavel_usa_default_str():
    cm = CacheManager(redis_client=_Fake())

    class _X:
        def __str__(self):
            return "X!"

    # json.dumps falha → fallback default=str (cobre o branch TypeError).
    assert "X!" in cm._serialize({"obj": _X()})
