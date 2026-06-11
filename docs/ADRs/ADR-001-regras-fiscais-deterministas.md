# ADR-001 — Regras fiscais determinísticas sem `weighted_voting`

**Status:** Aceito  
**Data:** 2026-06-11  
**Sprint:** S-C.2

## Contexto

O Bloco C (S-C.1) implementou o `FiscalRulesEngine` com validações algébricas de
registros SPED. Em revisão do S-C.1 levantou-se se regras fiscais deveriam passar pelo
`weighted_voting` (consenso ponderado de múltiplos modelos), já presente para análise
jurídica (TJSP/STF).

Também foi questionado o adiamento do carregamento de regras via YAML por UF (DT-06).

## Decisões

### 1. Regras fiscais NÃO usam `weighted_voting`

As regras ICMS-001..005, PIS-001..002, COFINS-001..002 etc. são verificações
algébricas sem ambiguidade semântica:

- "Base de cálculo ICMS negativa" → erro determinístico (`vl_bc_icms < 0`)
- "Valor ICMS > base" → violação matemática (`vl_icms > vl_bc_icms`)

O `weighted_voting` é adequado para questões com interpretação jurídica subjetiva
(análise de risco de crédito, classificação de jurisprudência). Não agrega valor onde
a resposta é binária e derivável por aritmética simples.

**Motivação principal (CJ-001 — sem invenção de normas):** auditabilidade. Cada achado
deve ser rastreável a uma equação explícita no código-fonte, sem caixa-preta de
consenso de LLMs. Isso é requisito para uso em processo fiscal/tributário.

### 2. Carregamento de regras YAML por UF adiado (DT-06)

A interface `FiscalRule.check: Callable[[Dict], bool]` é compatível com um futuro
`RuleLoader` YAML. O adiamento se justifica porque:

- Nenhuma regra atual depende de UF
- Implementar YAML antes da necessidade adiciona complexidade sem benefício
- O gatilho é a **primeira regra dependente de UF** (estimado em S-C.3)

## Consequências

- `FiscalRulesEngine` permanece determinístico e auditável; cada regra tem ID, descrição
  e dica de correção rastreáveis em PR
- Novos tipos de análise jurídica sobre dados SPED (ex.: classificação de risco fiscal
  por jurisprudência) **podem** usar `weighted_voting`, mas são casos distintos das
  validações de conformidade
- A API pública de `FiscalRule` não mudará quando DT-06 for implementado; o `RuleLoader`
  YAML alimentará o mesmo `FiscalRulesEngine`

## Débito técnico relacionado

| ID | Descrição | Sprint-alvo |
|----|-----------|-------------|
| DT-06 | `RuleLoader` YAML por UF | S-C.3 (gatilho: 1ª regra estadual) |
