"""Exporta a especificação OpenAPI a partir do próprio app FastAPI.

Substitui o antigo ``docs/API/openapi.yaml`` escrito à mão (que ficava
defasado): aqui a fonte da verdade é o código. Em desenvolvimento, a spec
também está sempre disponível em http://localhost:8000/openapi.json e a UI
interativa em http://localhost:8000/docs.

Uso:
    python scripts/dev/export_openapi.py            # -> docs/API/openapi.json
    python scripts/dev/export_openapi.py caminho.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.api.main import app  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "API" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = len(spec.get("paths", {}))
    print(f"OpenAPI exportada para {out} ({paths} caminhos).")


if __name__ == "__main__":
    main()
