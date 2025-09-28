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

# IMPORTANTE: Copia TODO o projeto para garantir que nada fique faltando
COPY . /app/

# DEBUG: Verifica estrutura copiada
RUN echo "=== Listando /app ===" && ls -la /app/ && \
    echo "=== Listando /app/src ===" && ls -la /app/src/ || echo "ERRO: src não existe" && \
    echo "=== Listando /app/src/api ===" && ls -la /app/src/api/ || echo "ERRO: src/api não existe" && \
    echo "=== Procurando __init__.py ===" && find /app -name "__init__.py" | head -20

# Define variáveis de ambiente ANTES de testar imports
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# DEBUG: Testa imports Python
RUN python -c "import sys; print('PYTHONPATH:', sys.path)" && \
    python -c "import os; print('Arquivos em /app:', os.listdir('/app'))" && \
    python -c "import os; print('Arquivos em /app/src:', os.listdir('/app/src') if os.path.exists('/app/src') else 'SRC NÃO EXISTE')" && \
    python -c "try: import src; print('✓ src importado'); except Exception as e: print('✗ Erro importando src:', e)" && \
    python -c "try: import src.api; print('✓ src.api importado'); except Exception as e: print('✗ Erro importando src.api:', e)" && \
    python -c "try: from src.api.main import app; print('✓ app importado de main.py'); except Exception as e: print('✗ Erro importando app:', e)"

# Cria usuário não-root
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app


# Muda para usuário não-root
USER appuser

# Define PYTHONPATH para encontrar módulos
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expõe porta
EXPOSE 8000


# Comando final

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
