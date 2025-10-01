# ADR-005: Execução Paralela de Consultas Multi-Tribunal

## Status
✅ Aceito (2025-09-29) - Onda 1 da Evolução Standard

## Contexto
O MVP processa tribunais de forma sequencial. Para consultas como "Status TJSP e TJMG", o sistema aguarda o TJSP terminar antes de iniciar o TJMG, resultando em latência acumulativa que prejudica a experiência do usuário.

Com a evolução para Standard, prevê-se um aumento no volume de consultas simultâneas e a necessidade de fornecer resultados agregados mais rapidamente.

## Decisão
Refatorar o `SupervisorAgent` para executar consultas a múltiplos tribunais **em paralelo** utilizando `asyncio.gather()`.

### Mudanças Técnicas
1. **Método `process_task` agora é `async`**
2. **Novo método `_identify_all_tribunals`** substitui `_identify_tribunal`
3. **Agregação de resultados** via `_aggregate_results`
4. **Backward compatibility** mantida para consultas single-tribunal

### Exemplo de Uso
```python
# Antes (sequencial):
result = supervisor.process_task("Status TJSP e TJMG")
# Tempo: ~1.5s (750ms + 750ms)

# Depois (paralelo):
result = await supervisor.process_task("Status TJSP e TJMG")
# Tempo: ~800ms (ambos em paralelo)
```

## Alternativas Consideradas
- **Threading:** Rejeitado devido ao GIL do Python e complexidade de sincronização
- **Celery/Task Queue:** Overhead desnecessário para o volume atual
- **AsyncIO:** ✅ Escolhido - nativo, eficiente, sem overhead

## Consequências
### Positivas ✅
- 50%+ redução de latência em consultas multi-tribunal
- Melhor UX - resultados mais rápidos
- Preparação para Standard - base para load balancing futuro
- Backward compatible - código antigo continua funcionando

### Negativas ⚠️
- Complexidade assíncrona - desenvolvedores devem entender async/await
- Debugging mais complexo - traces de erro menos lineares
- Maior uso de recursos - picos de memória ao executar N tarefas simultâneas

### Mitigações
- ✅ Testes emergentes cobrem comportamento paralelo
- ✅ Scripts de validação garantem performance
- ✅ Logs rastreiam tempo de execução individual
- ⚠️ Implementar rate limiting no futuro para controlar picos

## Métricas de Sucesso
- Speedup >1.5x em consultas com 3+ tribunais
- P95 mantido <800ms
- Cobertura de código >90%
- Zero regressões em testes existentes

## Próximos Passos
- Onda 2: Adicionar cache distribuído (Redis) para reduzir chamadas paralelas redundantes
- Onda 2: Implementar routing inteligente via LLM
- Onda 3: HITL para aprovação de consultas bulk
