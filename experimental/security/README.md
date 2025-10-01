# Experimental Security Components

## Sandbox de Segurança

**Status:** Experimental (não usado no MVP)

**Razão:** Conforme ADR-011, o sandbox não é necessário para o MVP atual pois não há execução de código arbitrário.

**Quando Reativar:**
- Execução dinâmica de código de usuários
- Plugins de terceiros
- Evolution para Foundation Level: Standard/Enterprise

**Arquivos:**
- `sandbox/secure_executor.py` - Executor seguro com validações
- `sandbox/docker_sandbox.py` - Isolamento via Docker

**Para Reintegrar:**
1. Mover de volta para `src/tools/sandbox/`
2. Atualizar imports em código que necessitar
3. Configurar Docker-in-Docker se necessário
4. Adicionar testes de integração
