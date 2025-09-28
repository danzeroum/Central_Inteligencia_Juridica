FROM python:3.9-slim

# Define diretório de trabalho
WORKDIR /app

# Cria usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copia e instala dependências primeiro (melhor cache)
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dev.txt

# Copia o código fonte
COPY src/ ./src/
COPY tests/ ./tests/

# Copia arquivos estáticos da API se existirem
COPY src/api/static ./src/api/static

# Define ownership correto
RUN chown -R appuser:appuser /app

# Muda para usuário não-root
USER appuser

# Define PYTHONPATH para encontrar módulos
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expõe porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

# Comando para iniciar a aplicação
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
