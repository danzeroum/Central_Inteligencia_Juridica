FROM python:3.9-slim

# Define diretório de trabalho
WORKDIR /app

# Instala curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivos de requirements
COPY requirements*.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Copia TODO o projeto
COPY . /app/

# Define variáveis de ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Testa que o import funciona (versão simplificada)
RUN python -c "import sys; print('PYTHONPATH:', sys.path)" && \
    python -c "import src" && \
    python -c "import src.api" && \
    python -c "from src.api.main import app; print('App importado com sucesso!')"

# Cria usuário não-root
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando final
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
