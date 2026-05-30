# Como adicionar um novo domínio (tribunal/jurisdição)

A Central de Inteligência Jurídica passou a ter o **roteamento de domínio orientado a
configuração**. Antes, identificar um tribunal a partir do texto da tarefa dependia de
dicionários de palavras-chave **triplicados e hardcoded** dentro de `SupervisorAgent`
(violação do princípio OCP). Agora isso vive em um único arquivo de dados.

> **Resultado prático:** adicionar um novo tribunal/jurisdição é, na maioria dos casos,
> **editar um arquivo YAML** — sem alterar código de produção.

## Onde fica a configuração

`config/routing/tribunals.yaml`

```yaml
default_tribunal: TJSP

tribunals:
  TJSP:
    core: true
    keywords: [tjsp, "são paulo", "sao paulo", sp]
    aliases: [paulista]
    reasoning_keywords: [TJSP, "SÃO PAULO", "SAO PAULO"]
  # ... demais tribunais

regions:
  sudeste: [TJSP, TJMG, TJRJ]
  sul: [TJRS]
```

### Campos por tribunal

| Campo | Uso |
|---|---|
| `core` | `true` participa da identificação primária (delegação por aparição). `false` é tribunal "estendido", considerado apenas na sugestão de tribunais relevantes (ex.: STJ, TST). |
| `keywords` | Termos seguros para casamento por **substring** (códigos e nomes não-ambíguos). |
| `aliases` | Termos adicionais casados **apenas por palavra inteira** (regex word-boundary). Use para adjetivos regionais e termos curtos que dariam falso-positivo por substring (ex.: `sul` em "con**sul**ta"). |
| `reasoning_keywords` | Termos (em maiúsculas) usados ao extrair tribunais do raciocínio estruturado do `ArchitectAgent`. |

## Passo a passo

1. **Edite** `config/routing/tribunals.yaml` adicionando o novo bloco de tribunal e,
   se aplicável, incluindo-o em uma `region`.
2. **(Opcional) Mapeie palavras** no `ArchitectAgent` apenas se quiser que o
   chain-of-thought reconheça o novo tribunal explicitamente (`tribunal_map` em
   `src/agents/architect_agent.py`).
3. **Teste** com a propriedade de extensibilidade já existente — veja
   `tests/unit/test_tribunal_identifier.py::TestExtensibility::test_new_tribunal_via_config_only`,
   que adiciona um tribunal **só via config** e valida o roteamento. Copie esse padrão.

## Por que isso importa para o crescimento do negócio

* **Custo marginal baixo:** novos domínios entram por dados, não por código — menos risco de
  regressão e ciclo mais curto.
* **Fonte única de verdade:** a lógica de identificação fica em `TribunalIdentifier`
  (`src/routing/tribunal_identifier.py`), com paridade comportamental garantida por testes.
* **Hierarquia uniforme:** agentes especializados conformam-se a `BaseAgent`
  (`execute()`/`attach_memory()`), o que permite "plugar" novos agentes/domínios de forma
  consistente na orquestração.
