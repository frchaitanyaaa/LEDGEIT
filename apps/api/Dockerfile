# Build context: repository root (see infra/docker-compose.yml)
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEDGEIT_ROOT=/app
WORKDIR /app
COPY packages/proof-core/python packages/proof-core/python
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -e packages/proof-core/python -r apps/api/requirements.txt
COPY apps/api apps/api
COPY config config
COPY contracts/abi contracts/abi
RUN mkdir -p contracts/deployments && pip install --no-cache-dir -e apps/api
EXPOSE 8000
CMD ["sh", "-c", "python -m ledgeit_api.db.migrate && uvicorn ledgeit_api.main:app --host 0.0.0.0 --port 8000"]
