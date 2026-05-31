FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Smoke-import de build: valida que a app importa. Usa ENVIRONMENT=test para não
# exigir JWT_SECRET nesta etapa — em runtime (CMD) o ambiente real é aplicado e a
# ausência de JWT_SECRET fora de teste impede o boot (fail-fast intencional).
RUN ENVIRONMENT=test python -c "from src.api.main import app; print('OK')"

RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
