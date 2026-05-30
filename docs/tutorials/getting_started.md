# Primeiros passos — Central de Inteligência Jurídica

Guia rápido para subir o projeto **localmente** e fazer sua primeira consulta.
Para um passeio por todas as funcionalidades da interface, veja o
[Manual do Estudante](../MANUAL_ESTUDANTE.md).

## 1. Pré-requisitos

- Python 3.11+ e `pip`
- Node 18+ e `npm` (apenas para (re)compilar o frontend)
- (Opcional) Docker, para subir Redis/Prometheus/Grafana

## 2. Instalação e execução

```bash
git clone https://github.com/danzeroum/Central_Inteligencia_Juridica.git
cd Central_Inteligencia_Juridica

pip install -r requirements.txt

# Frontend (gera o bundle servido pelo FastAPI em /app)
cd frontend && npm install && npm run build && cd ..

uvicorn src.api.main:app --reload --port 8000
```

Acesse:
- **Interface (SPA):** http://localhost:8000/app
- **Documentação da API (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

> **Sem chave de LLM?** Tudo funciona. Sem `OPENAI_API_KEY`, o classificador de
> intenção usa um fallback heurístico determinístico (palavras-chave + regex CNJ).

## 3. Sua primeira consulta

### Pela interface
1. Abra http://localhost:8000/app e clique em **Entrar como Usuário**.
2. Na tela **Assistente**, clique numa sugestão (ex.: *"Comparar jurisprudência
   sobre LGPD no STF e no TJSP"*) e observe a **intenção detectada**, os
   **tribunais** e o **roteamento**.

### Pela API
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Status do TJSP"}'
```

A resposta (`SuccessfulTaskResponse`) traz `supervisor_result`, `tribunals_used`,
`task_id`, `execution_time` e `timestamp`.

## 4. Para onde ir agora

- [Manual do Estudante](../MANUAL_ESTUDANTE.md) — todas as telas e funcionalidades.
- [Arquitetura (C4)](../ARCHITECTURE_C4.md) — visão de contexto → código.
- [Adicionar um novo domínio/tribunal](../ADICIONAR_NOVO_DOMINIO.md) — só editar YAML.
- [ADRs](../ADRs/README.md) — decisões arquiteturais.
- [Troubleshooting](../troubleshooting.md) — problemas comuns.
