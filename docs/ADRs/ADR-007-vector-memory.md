# ADR-007: Persistent Vector Memory for Tribunal Agent

## Contexto

A evolução da Onda 2.2 exige que o agente supervisor aprenda com execuções anteriores
para enriquecer prompts, reduzir latência e evitar trabalho duplicado. A plataforma já
opera com roteamento inteligente via LLM, execução paralela de tribunais e telemetria,
mas carecia de uma memória persistente acessível por múltiplas execuções.

## Decisão

- Adotar **ChromaDB 0.5.0** como banco vetorial dedicado, executado via Docker com
  volume persistente `chromadb_data`.
- Consumir embeddings **OpenAI text-embedding-3-small (1536 dimensões)** utilizando a
  `OpenAIEmbeddingFunction` oficial.
- Introduzir o módulo `VectorMemory` responsável por:
  - Conectar-se ao serviço HTTP do ChromaDB com retentativas e telemetria mínima.
  - Armazenar interações completas (tarefa, resultado, metadados) convertidas para
    embeddings.
  - Recuperar memórias semanticamente similares (`k=3`) antes da classificação de
    intenção.
  - Expor estatísticas operacionais para observabilidade.
- Integrar a memória ao `SupervisorAgent` para registrar `MEMORY_RECALLED` e
  `MEMORY_STORED` no ledger, expondo métricas de recall na resposta pública.
- Documentar e automatizar validações com testes de integração/emergentes e script
  `scripts/validate-wave2.2.sh`.

## Consequências

- **Persistência:** memórias sobrevivem a reinícios do container graças ao volume
  dedicado.
- **Latência Controlada:** testes de integração garantem consultas abaixo de 300 ms,
  alinhado com o objetivo da onda.
- **Dependências Adicionais:** o projeto passa a exigir `chromadb-client==0.5.0` e
  `openai==1.12.0`, além do serviço Docker correspondente.
- **Skips Conscientes:** testes detectam ausência de API key ou serviço Chroma e são
  ignorados de forma explícita para não quebrar pipelines sem o ambiente completo.
- **Base para Evoluções Futuras:** o design facilita enriquecer prompts do Intent
  Classifier e métricas de aprendizado contínuo em ondas subsequentes.
