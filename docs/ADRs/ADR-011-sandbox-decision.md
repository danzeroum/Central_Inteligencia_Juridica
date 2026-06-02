# ADR-011: Decisão sobre Sandbox de Segurança para MVP

## Status
Aceito (2025-09-30) — com ressalva de conformidade (2026-05)

> ⚠️ **Nota de conformidade (sync com o código — D02).** Os caminhos
> `experimental/security/...` citados nesta decisão e nas Referências **não
> existem**. O código de sandbox vive em `src/tools/sandbox/`
> (`docker_sandbox.py` → `DockerSandbox`; `secure_executor.py` →
> `SecureToolSandbox`), **não** foi movido para `experimental/`.
> `SecureToolSandbox` é referenciado por `src/orchestration/unified_orchestrator.py`,
> mas o `DockerSandbox` real só executa com o SDK `docker` disponível e não há
> fluxo de produção submetendo código a ele. Trate as referências a
> `experimental/security/...` abaixo como **desatualizadas**; o conteúdo conceitual
> da decisão (sandbox é over-engineering para o caminho atual, sem execução de
> código arbitrário) continua válido.

## Contexto
O projeto inclui componentes de sandbox (`src/tools/sandbox/secure_executor.py` e `docker_sandbox.py`) destinados a isolar a execução de código potencialmente perigoso. No entanto, o fluxo atual do sistema:

1. Recebe entrada textual do usuário
2. Sanitiza com `InputSanitizer` (proteção contra XSS, SQL injection, etc.)
3. Chama APIs HTTP de tribunais (via `TribunalAPIClient`)
4. Acessa cache Redis (via `CacheManager`)
5. Retorna dados estruturados

**Não há execução de código arbitrário ou dinâmico no caminho crítico do MVP.**

## Decisão
Para o **MVP (Foundation Level: Lite)**, o `SecureToolSandbox` é considerado **over-engineering**.

**Justificativas:**
- As chamadas são para APIs HTTP controladas, não código arbitrário
- `InputSanitizer` já mitiga os principais riscos de input malicioso
- Docker Sandbox requer configuração adicional e overhead operacional
- Não há uso de `eval()`, `exec()` ou similar no fluxo de produção

**Ação:**
- Mover código de sandbox para `experimental/security/` (preservado para referência futura)
- Documentar que para **Standard/Enterprise** levels, sandbox pode ser reativado se houver execução dinâmica de código

## Alternativas Consideradas
1. **Implementar Sandbox Completo:** Overhead desnecessário para MVP sem execução dinâmica
2. **Remover Completamente:** Perda de trabalho já feito; melhor preservar como experimental
3. **Decisão Atual:** Mover para experimental, documentar decisão

## Consequências
### Positivas
- Simplificação do deployment (sem necessidade de configuração Docker-in-Docker)
- Redução de complexidade operacional
- Foco em features core do MVP

### Negativas
- Se futuramente houver necessidade de execução dinâmica, será necessário reintegrar

### Mitigações
- Código preservado em `experimental/` para rápida reativação
- `InputSanitizer` + `GuardrailSystem` mantêm proteção adequada para MVP
- Documentação clara sobre quando reativar (ADR + README)

## Validação para Reativação Futura
O sandbox deve ser reativado se:
- [ ] Sistema passar a executar código Python/JavaScript submetido por usuários
- [ ] Integração com plugins de terceiros que executem código
- [ ] Foundation level evoluir para Standard/Enterprise com requisitos de isolamento

## Referências
- `experimental/security/sandbox/secure_executor.py`
- `experimental/security/sandbox/docker_sandbox.py`
- `src/safety/security_config.py` (guardrails mantidos)
- `src/utils/input_sanitizer.py` (proteção de input mantida)
