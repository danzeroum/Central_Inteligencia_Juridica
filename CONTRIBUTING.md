# Contribuindo

Obrigado por considerar contribuir com a Central de Inteligência Jurídica!

## Ambiente de desenvolvimento

```bash
pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
```

Veja o [guia de primeiros passos](docs/tutorials/getting_started.md) para subir a
aplicação.

## Fluxo de contribuição

1. Crie uma branch a partir de `master` (`feat/...`, `fix/...`, `docs/...`).
2. Faça suas mudanças com commits claros (ver convenção abaixo).
3. Garanta que a verificação local passa (ver seção *Qualidade*).
4. Abra um Pull Request descrevendo **o quê** e **por quê**.

## Qualidade (o que a CI valida)

```bash
# Testes
pytest tests/unit tests/integration -q

# Formatação e tipos
black --check src/ tests/
mypy src/ --ignore-missing-imports

# Segurança
bandit -r src/ -x tests/ --severity-level high

# Frontend (se alterado)
cd frontend && npm run build
```

A CI exige **cobertura mínima de 30%** e que o build Docker (`./Dockerfile`) e o
build do frontend passem.

## Convenção de commits

Use prefixos no estilo *Conventional Commits*: `feat:`, `fix:`, `docs:`,
`test:`, `refactor:`, `chore:`. Mensagens em português ou inglês.

## Estrutura do projeto

- `src/` — aplicação (agentes, API, HITL, roteamento…)
- `frontend/` — SPA React + Vite (build servido em `/app`)
- `tests/` — `unit/` e `integration/`
- `docs/` — ADRs, manual, arquitetura C4, tutoriais
- `config/`, `monitoring/`, `scripts/dev/`

## Decisões arquiteturais

Mudanças arquiteturais significativas devem registrar um
[ADR](docs/ADRs/README.md) usando o `ADR-Template.md`.
