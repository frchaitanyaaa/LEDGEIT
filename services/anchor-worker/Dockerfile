# Build context: repository root. Reuses the API image layers (same Python packages).
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEDGEIT_ROOT=/app
WORKDIR /app
COPY packages/proof-core/python packages/proof-core/python
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -e packages/proof-core/python -r apps/api/requirements.txt
COPY apps/api apps/api
COPY config config
COPY contracts/abi contracts/abi
COPY services/anchor-worker services/anchor-worker
RUN mkdir -p contracts/deployments && pip install --no-cache-dir -e apps/api
WORKDIR /app/services/anchor-worker
CMD ["python", "-m", "worker"]
