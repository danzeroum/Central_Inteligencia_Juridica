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
