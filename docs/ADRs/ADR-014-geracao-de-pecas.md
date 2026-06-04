# ADR-014 — Geração de Peças Processuais

## Status
Aceito (2026-06-04)

## Contexto

A Frente F.2 introduz a geração de peças (petição inicial, contestação,
procuração…). É uma capacidade de **alto risco** (responsabilidade profissional):
um rascunho mal controlado pode caracterizar exercício ilegal da advocacia ou
sair com elementos obrigatórios faltando.

## Decisão

Construir uma camada de documentos (`src/documents/`) com:

| Componente | Papel |
|---|---|
| `config/templates/pecas.yaml` | Registro externo de templates (nome, base legal, campos obrigatórios, texto com `{placeholders}`). Adicionar peça = editar YAML. |
| `templates.py` | Loader (YAML + `lru_cache`, padrão do `tribunal_identifier`). |
| `postcheck.py` | Validação pós-geração: campos obrigatórios presentes + nenhum placeholder vazio (rastreável à base legal, ex.: CPC art. 319). |
| `peca_service.py` | Orquestra: template → preenchimento → postcheck → HITL → disclaimer. |
| `schemas.py` | `PecaResult` / `PostcheckResult` (Pydantic). |

### Invariantes de risco (não-negociáveis)

1. **Disclaimer OAB obrigatório** em todo output (`DISCLAIMER_OAB`, Lei 8.906/94,
   art. 1º) — evita caracterizar exercício ilegal da advocacia.
2. **HITL obrigatório**: `requires_human_review=True` sempre; o serviço enfileira
   o rascunho no `HITLQueue` quando uma fila é injetada.
3. **CJ-001**: o LLM é um *hook opcional de redação* (`gerador`) que escreve **a
   partir dos dados fornecidos** — não inventa dados normativos (ver ADR-013/F4).

### Por que LLM como hook opcional
Sem `gerador`, o serviço preenche o template de forma **determinística** — testável
e sem rede. Com `gerador`, injeta-se a redação por LLM/ArchitectAgent. O postcheck
valida os **dados** (não a prosa), garantindo a estrutura legal independentemente
da origem do texto.

## Consequências

### Positivas
- Estrutura legal garantida (postcheck) + salvaguardas profissionais (OAB/HITL).
- Templates como dados; novas peças sem mudar código.

### Dívida / follow-ups
- Endpoint HTTP `POST /api/v1/peticoes` e wiring no SupervisorAgent.
- Conjunto completo das 7 peças do plano (hoje: inicial, contestação, procuração).
- Geração via LLM real (ArchitectAgent) e enriquecimento com jurisprudência
  (DataJud/ADR-013).

## Validação
- `tests/unit/test_peca_service.py` (11): templates, preenchimento, postcheck
  (campo ausente/vazio), disclaimer OAB, invariante HITL, hook LLM, tool MCP.

## Referências
- Plano Mestre §7.2; ADR-013 (DataJud); `docs/BPM-DMN.md` (DMN-01 futura).
