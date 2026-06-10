"""Configuração de fontes de integração a partir de YAML + env.

Carrega `config/integrations/sources.yaml` com `@lru_cache`; variáveis de
ambiente `INTEGRATIONS_{SOURCE}_*` sobrescrevem o YAML (precedência env > YAML).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "integrations" / "sources.yaml"
)


@dataclass
class SourceSettings:
    """Configuração operacional de uma fonte de integração."""

    name: str
    enabled: bool = True
    mode: str = "real"  # real | mock
    timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 30
    cache_ttl_seconds: int = 900
    zone: str = "publica"
    data_type: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def is_mock(self) -> bool:
        return self.mode == "mock"

    def is_real(self) -> bool:
        return self.mode == "real"


@lru_cache(maxsize=1)
def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.warning("sources.yaml não encontrado em %s; usando defaults.", path)
        return {}


def _env_override(source_name: str, key: str, default: Any) -> Any:
    """Retorna valor de env INTEGRATIONS_{SOURCE}_{KEY} se definido."""
    env_key = f"INTEGRATIONS_{source_name.upper()}_{key.upper()}"
    val = os.getenv(env_key)
    if val is None:
        return default
    # Converte para o tipo do default
    if isinstance(default, bool):
        return val.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(val)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(val)
        except ValueError:
            return default
    return val


def load_source_settings(
    config_path: Optional[Path] = None,
) -> Dict[str, SourceSettings]:
    """Carrega configurações de todas as fontes com precedência env > YAML."""
    path = config_path or DEFAULT_CONFIG_PATH
    raw = _load_yaml(path)
    defaults = raw.get("defaults") or {}
    sources_raw = raw.get("sources") or {}

    result: Dict[str, SourceSettings] = {}
    for name, spec in sources_raw.items():
        spec = spec or {}
        merged = {**defaults, **spec}

        enabled = _env_override(name, "ENABLED", merged.get("enabled", True))
        mode = _env_override(name, "MODE", merged.get("mode", "real"))
        timeout = _env_override(
            name, "TIMEOUT_SECONDS", float(merged.get("timeout_seconds", 10.0))
        )
        rate_limit = _env_override(
            name, "RATE_LIMIT", int(merged.get("rate_limit_per_minute", 30))
        )
        cache_ttl = _env_override(
            name, "CACHE_TTL", int(merged.get("cache_ttl_seconds", 900))
        )
        zone = merged.get("zone", "publica")
        data_type = merged.get("data_type", "")

        result[name] = SourceSettings(
            name=name,
            enabled=enabled,
            mode=mode,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            cache_ttl_seconds=cache_ttl,
            zone=zone,
            data_type=data_type,
            extra={
                k: v
                for k, v in merged.items()
                if k
                not in {
                    "enabled",
                    "mode",
                    "timeout_seconds",
                    "rate_limit_per_minute",
                    "cache_ttl_seconds",
                    "zone",
                    "data_type",
                }
            },
        )

    return result


_SETTINGS_CACHE: Optional[Dict[str, SourceSettings]] = None


def get_source_settings(source: Optional[str] = None) -> Any:
    """Retorna settings de uma fonte específica ou dict completo."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is None:
        _SETTINGS_CACHE = load_source_settings()
    if source:
        return _SETTINGS_CACHE.get(source)
    return _SETTINGS_CACHE


def get_qsa_settings() -> Dict[str, Any]:
    """Retorna configurações de expansão QSA."""
    path = DEFAULT_CONFIG_PATH
    raw = _load_yaml(path)
    qsa_raw = raw.get("qsa_expansion") or {}
    enabled_env = os.getenv("INTEGRATIONS_QSA_EXPANSION_ENABLED")
    max_socios_env = os.getenv("INTEGRATIONS_QSA_MAX_SOCIOS")
    enabled = (
        enabled_env.strip().lower() in ("1", "true", "yes", "on")
        if enabled_env
        else bool(qsa_raw.get("enabled", True))
    )
    max_socios = (
        int(max_socios_env) if max_socios_env else int(qsa_raw.get("max_socios", 5))
    )
    return {"enabled": enabled, "max_socios": max_socios}


__all__ = [
    "SourceSettings",
    "load_source_settings",
    "get_source_settings",
    "get_qsa_settings",
]
