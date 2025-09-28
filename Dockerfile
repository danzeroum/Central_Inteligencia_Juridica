FROM python:3.9-slim

# Define diretório de trabalho
WORKDIR /app

# Instala dependências do sistema se necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivos de requirements
COPY requirements*.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Copia TODO o código fonte
COPY . /app/

# Verifica que os arquivos foram copiados (DEBUG)
RUN echo "=== Verificando estrutura copiada ===" && \
    ls -la /app/ && \
    echo "=== Conteúdo de src ===" && \
    ls -la /app/src/ && \
    echo "=== Conteúdo de src/api ===" && \
    ls -la /app/src/api/ && \
    echo "=== Verificando __init__.py files ===" && \
    find /app -name "__init__.py" -type f

# Define variáveis de ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Testa que o import funciona (DEBUG)
RUN python -c "import sys; print('Python path:', sys.path)" && \
    python -c "import src; print('src importado OK')" && \
    python -c "import src.api; print('src.api importado OK')" && \
    python -c "from src.api.main import app; print('app importado OK')"

# Cria usuário não-root
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expõe porta
EXPOSE 8000

# Comando para iniciar
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
