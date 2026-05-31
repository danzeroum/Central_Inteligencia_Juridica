# ADR-003 — Padrões de Design da API

## Status
Aceita (2025-09-25)

## Contexto
Para garantir consistência, DX e manutenção, a API da Central de Inteligência Jurídica deve seguir convenções REST claras com versionamento explícito e documentação de contrato.

## Decisão
- **URLs RESTful** com substantivos no plural (ex.: `/users`, `/orders`).
- **Versionamento obrigatório**: prefixo `/api/v1/` para **novos** endpoints.
- **Métodos HTTP semânticos**: GET (leitura), POST (criação), PUT/PATCH (atualização), DELETE (remoção).
- **Status HTTP consistentes** e **OpenAPI com exemplos** (request/response + erros `application/problem+json`).

> Nota de conformidade — exceções de versionamento (D12): alguns endpoints
> legados **não** seguem o prefixo `/api/v1` por compatibilidade retroativa:
> `POST /tasks`, `GET /consultar-projetos-lei/` e `POST /analise-legislativa/`.
> São exceções conhecidas e mantidas; **novos** endpoints devem nascer sob
> `/api/v1`.

## Alternativas Consideradas
- GraphQL (flexível, porém extrapola o MVP e complica os gates).
- API sem versionamento (risco de breaking changes em evolução).

## Consequências
- **Positivas:** menos ambiguidade, melhor DX, facilita automação dos gates.
- **Negativas:** exige validação contínua dos contratos em PRs.

## Validação
- A validação de qualidade antes do merge é feita pelo pipeline de CI em
  `.github/workflows/ci.yml` (Black, Bandit, pytest com cobertura, gitleaks,
  e — para a SPA — ESLint/Vitest/build).
- O schema OpenAPI pode ser exportado via `scripts/dev/export_openapi.py`.

> Nota de conformidade (D09/D10): a referência anterior a `scripts/gates-v6.sh`
> foi removida — esse script nunca existiu no repositório. A "qualidade antes do
> merge" é assegurada pelo CI do GitHub Actions descrito acima.

## Referências
- OpenAPI Specification
- REST API Design Rulebook
