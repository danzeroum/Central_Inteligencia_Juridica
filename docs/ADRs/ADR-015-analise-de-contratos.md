# ADR-015 — Análise de Contratos

## Status
Aceito (2026-06-04)

## Contexto

A Frente F.3 introduz a análise de contratos. O plano original previa um pipeline
PDF → VLM → LLM → XLSX, mas **essas engines não existem neste repositório** (eram
do projeto Z.AI; ver matriz de reconciliação do Plano Mestre). O escopo realista
e coerente com o DNA do projeto é analisar o **texto** do contrato (extração de
PDF fica fora deste repo) contra uma ontologia de risco.

## Decisão

Camada `src/contracts/` que recebe o texto, divide em cláusulas e as varre contra
um catálogo de risco externalizado, produzindo um relatório estruturado.

| Componente | Papel |
|---|---|
| `config/contracts/clausulas_risco.yaml` | Catálogo de regras (categoria, base legal, severidade, recomendação, padrões regex). Adicionar regra = editar YAML. |
| `rules.py` | Loader (YAML + `lru_cache`) com regex compilados. |
| `analyzer.py` | `ContractAnalyzer`: divide cláusulas, casa regras, calcula score + nível de risco; hook `detector` (LLM) opcional. |
| `schemas.py` | `Achado` / `ContractAnalysisResult`. |

Categorias cobertas: exoneração de responsabilidade (CDC 51,I), renúncia de
direitos, alteração unilateral (CDC 51,XIII), foro de eleição (CPC 63), cláusula
penal (CC 412/413), resilição imotivada (CC 473), dados pessoais (LGPD).

### Invariantes de risco (iguais à Frente F.2)
1. **Disclaimer OAB** obrigatório (reusa `DISCLAIMER_OAB`).
2. **HITL obrigatório** (`requires_human_review=True`).
3. A ferramenta **aponta** cláusulas + base legal; **não julga** sozinha — a
   decisão é do(a) advogado(a). Detecção determinística por padrão (testável);
   LLM é hook opcional.

## Consequências

### Positivas
- Surfacing de cláusulas de risco com base legal, score e nível — apoio real.
- Ontologia como dados; novas regras sem mudar código.

### Limites / follow-ups
- Extração de PDF/VLM e relatório DOCX/XLSX são fora de escopo (engines ausentes).
- Severidade "desproporcional" (ex.: multa excessiva) é sinalizada para revisão,
  não auto-decidida.
- Endpoint HTTP e geração via LLM real são follow-ups.

## Validação
- `tests/unit/test_contract_analysis.py` (9): regras, detecção (exoneração/foro),
  base legal, contrato limpo, disclaimer/HITL, contagem de cláusulas, hook LLM,
  YAML custom, tool MCP.

## Referências
- Plano Mestre §7.3; ADR-014 (peças); `docs/BPM-DMN.md` (regra CJ-001).
