FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS builder
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install --prefix=/install -e .

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY --from=builder /app/src /app/src
ENV PYTHONPATH=/app/src
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "curva_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]