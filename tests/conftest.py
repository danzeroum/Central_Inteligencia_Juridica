"""Configuração global da suíte de testes.

Define ``ENVIRONMENT=test`` ANTES de qualquer coleta/importação dos módulos de
teste. Isto é necessário porque ``src/api/auth.py`` exige ``JWT_SECRET`` (mín. 32
caracteres) em tempo de importação fora do ambiente de teste — e ``src/api/main``
passou a importar o ``AuthManager`` real. Sem este ajuste, rodar ``pytest``
localmente sem exportar ``ENVIRONMENT=test`` quebraria a coleta com
``RuntimeError``. O ``setdefault`` preserva um valor já definido pelo CI/ambiente.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
# Disable ChromaDB initialization during tests — the native HNSWLIB extension can
# crash with SIGILL on CI runners whose CPUs lack the required instruction sets.
# Setting this before any test module is imported ensures VectorMemory.__init__
# returns immediately (client=None) without touching the native library.
os.environ.setdefault("VECTOR_MEMORY_MODE", "none")
